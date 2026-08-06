#!/usr/bin/env python3
"""
Segmentacion y carga del universo de renta fija.

Modulo compartido por los dos pilares del proyecto (armar_cartera.py y
detectar_swaps.py). No se ejecuta solo.

Antes cada pilar tenia su propia funcion de segmentacion y las dos no
coincidian: el motor de swaps exigia clase_activo == "bono_soberano" para los
segmentos en pesos y no contemplaba Tamar, con lo que descartaba en silencio
Tamar, ONs dollar-linked y subsoberanos no hard-dollar. Aca vive LA
segmentacion del proyecto, una sola, la del universo completo.

El consolidado incluye ademas acciones y CEDEARs. Esa frontera se aplica UNA
sola vez, aca: cargar_universo() devuelve renta fija y nada mas, asi que los
cuatro consumidores (armador, swaper, sectores y condiciones) quedan protegidos
sin tener que acordarse de filtrar. La renta variable se pide aparte y a
proposito, con cargar_renta_variable().

Que expone:
    asignar_segmento(fila)          -> nombre de segmento o None
    cargar_universo(...)            -> universo de RENTA FIJA enriquecido
                                       (segmento, rendimiento, duration_aprox,
                                       volumen_usd, emisor, clave_riesgo,
                                       sector, dato_sano)
    cargar_renta_variable(alertas)  -> acciones y CEDEARs con precio y volumen
    tipo_cambio_implicito(df, ...)  -> dolar del dia derivado del propio universo
    marcar_datos_sanos(df, alertas) -> descarta rendimientos que no pueden ser ciertos
    deduplicar_emisiones(df, alertas) -> colapsa especies O/D/C de una emision
    filtrar_operables(df)           -> lo que se puede proponer
"""

import os
import sys

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSOLIDADO_PATH = os.path.join(BASE_DIR, "data", "output", "universo_consolidado.xlsx")
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")

# Cuantos outputs con timestamp se conservan por tipo (carteras, swaps, logs).
# Sin poda el directorio crece sin techo: una sola tanda de regresiones dejo
# 200+ archivos que hubo que borrar a mano.
CONSERVAR_OUTPUTS = 10


def podar_outputs(prefijo, conservar=CONSERVAR_OUTPUTS):
    """Borra los archivos `prefijo*` mas viejos de OUTPUT_DIR, conservando los
    N mas recientes por fecha de modificacion. Solo toca lo que matchea el
    prefijo: el universo, el cashflow y el snapshot quedan afuera siempre."""
    if not os.path.isdir(OUTPUT_DIR):
        return
    rutas = [
        os.path.join(OUTPUT_DIR, f)
        for f in os.listdir(OUTPUT_DIR)
        if f.startswith(prefijo) and os.path.isfile(os.path.join(OUTPUT_DIR, f))
    ]
    rutas.sort(key=os.path.getmtime, reverse=True)
    for ruta in rutas[conservar:]:
        try:
            os.remove(ruta)
        except OSError:
            pass  # un archivo abierto en Excel no debe frenar la corrida


# ---------------------------------------------------------------------------
# Segmentos comparables. Cubren el universo completo de renta fija y se
# clasifican SOLO por tipo de tasa: la clase de activo (soberano, subsoberano,
# ON) es riesgo de credito, no naturaleza de tasa, y por lo tanto no define con
# quien es comparable un instrumento. Un Tamar provincial y un Tamar corporativo
# se miden con la misma vara; que uno sea mas riesgoso que el otro se resuelve
# despues, en los limites de concentracion y en las notas de riesgo.
# ---------------------------------------------------------------------------

# Clases del consolidado que NO son renta fija: sin TIR, sin duration y sin
# cashflow, no son comparables con un bono ni tienen segmento posible.
CLASES_RENTA_VARIABLE = ("accion", "cedear")


def asignar_segmento(fila):
    tasa = fila["tipo_tasa"]
    if tasa in ("hard-dollar", "bopreal"):
        return "usd_hard"
    return {
        "cer": "cer",
        "tasa-fija": "tasa_fija",
        "dollar-linked": "dollar_linked",
        "badlar": "badlar",
        "tamar": "tamar",
    }.get(tasa)


# Que cubre cada segmento y en que moneda cobra el inversor
MONEDA_SEGMENTO = {
    "usd_hard": "usd",        # paga en dolares (MEP/Cable)
    "dollar_linked": "ars",   # paga en pesos, ajusta por tipo de cambio
    "cer": "ars",             # paga en pesos, ajusta por inflacion
    "tasa_fija": "ars",
    "badlar": "ars",
    "tamar": "ars",
}

# Naturaleza del rendimiento de cada segmento. Rendimientos de distinta
# naturaleza NO se promedian entre si: una TIR en dolares, una tasa real sobre
# CER y una TNA nominal en pesos son magnitudes de unidades distintas.
NATURALEZA_TASA = {
    "usd_hard": "tir_usd",
    "dollar_linked": "tir_dolar_linked",
    "cer": "tasa_real_cer",
    "tasa_fija": "tna_nominal_ars",
    "badlar": "tna_nominal_ars",
    "tamar": "tna_nominal_ars",
}

NOMBRE_NATURALEZA = {
    "tir_usd": "TIR en dolares (hard dollar)",
    "tir_dolar_linked": "Rendimiento dolar linked",
    "tasa_real_cer": "Tasa real sobre CER (por encima de inflacion)",
    "tna_nominal_ars": "TNA nominal en pesos",
}

DESC_SEGMENTO = {
    "usd_hard": "Hard dollar (Globales, Bonares, ONs y Bopreales en USD)",
    "dollar_linked": "Dolar linked (pesos ajustados por tipo de cambio)",
    "cer": "CER (pesos ajustados por inflacion)",
    "tasa_fija": "Tasa fija en pesos (LECAP/BONCAP y ONs)",
    "badlar": "Badlar (pesos, tasa variable)",
    "tamar": "Tamar (pesos, tasa variable)",
}


# ---------------------------------------------------------------------------
# Sanidad del dato. NO es criterio economico: es integridad. El tope
# anti-distress (que decide el usuario, en detectar_swaps.py) opera dentro del
# rango de lo posible; esto descarta lo que directamente no puede ser cierto.
#
# Capa 1 — coherencia entre especies del mismo bono. Un bono tiene UNA TIR: sus
# especies de liquidacion (O/D/C) tienen que declarar la misma, y en la practica
# lo hacen (MR46D 13,08% vs MR46O 13,10%; PQCTD 55,13% vs PQCTO 54,81%). Cuando
# una especie se despega del resto por mas de 100pp, esa especie tiene el precio
# mal escalado: VSCQD figura con 34.627.917% mientras VSCQO, el mismo bono,
# rinde 6,75%.
#
# El umbral es de 100pp y no menos porque hay discordancias legitimas: DICPD
# rinde 51pp mas que DICP y son datos validos.
DISCORDANCIA_ESPECIES = 1.0  # 100 pp

# Capa 2 — techo de lo posible, POR SEGMENTO y en la unidad de cada segmento.
# Un tope unico cruzaria naturalezas de tasa: 300% de TNA nominal en pesos y
# 300% de TIR en dolares no son la misma magnitud. Los numeros son holgados a
# proposito — tienen que dejar pasar el distress real. SNSBO rinde 245,5% en
# dolares y es dato correcto: bono a 80 dias cotizando al 78% de su valor
# tecnico, donde la TIR anualizada explota por el plazo corto.
TOPE_SANIDAD_SEGMENTO = {
    "usd_hard": 3.0,        # TIR en USD
    "dollar_linked": 3.0,   # rendimiento dolar linked
    "cer": 1.0,             # tasa REAL sobre CER
    "tasa_fija": 5.0,       # TNA nominal en pesos
    "badlar": 5.0,          # TNA nominal en pesos
    "tamar": 5.0,           # TNA nominal en pesos
}


def raiz_emision(tickers):
    """MR46O / MR46D / MR46C -> MR46. Las tres especies del mismo bono."""
    return [
        tk[:-1] if (len(tk) >= 4 and tk[-1] in ("O", "D", "C")) else tk
        for tk in tickers.astype(str)
    ]


# Minimo de pares para confiar en el dolar implicito. Con menos, la mediana la
# puede mover un solo precio raro.
MIN_PARES_FX = 20


def tipo_cambio_implicito(df, alertas):
    """Dolar implicito del dia, derivado del propio universo.

    La misma emision cotiza en pesos (especie O) y en dolares (especies D/C), y
    el cociente entre esos dos precios ES el tipo de cambio al que opera el
    mercado. No hace falta ninguna fuente externa: el dato ya esta adentro.

    Se toma la mediana sobre todas las emisiones que cotizan en las dos puntas,
    asi un precio desactualizado no mueve el resultado. Devuelve None si no hay
    pares suficientes, y en ese caso el volumen no se normaliza.
    """
    precio = pd.to_numeric(df["lastPrice"], errors="coerce")
    tmp = pd.DataFrame({
        "raiz": raiz_emision(df["ticker"]),
        "sufijo": [t[-1] if (len(t) >= 4 and t[-1] in ("D", "C")) else "O"
                   for t in df["ticker"].astype(str)],
        "precio": precio,
    }).dropna(subset=["precio"])

    ratios = []
    for _, grupo in tmp[tmp["precio"] > 0].groupby("raiz"):
        ars = grupo.loc[grupo["sufijo"] == "O", "precio"]
        # Se usa la especie D (MEP) como referencia y solo se cae a la C (Cable)
        # si no hay MEP: MEP y Cable son dos tipos de cambio distintos (los
        # separa el canje, ~3,5%) y mezclarlos ensuciaria la mediana.
        usd = grupo.loc[grupo["sufijo"] == "D", "precio"]
        if not len(usd):
            usd = grupo.loc[grupo["sufijo"] == "C", "precio"]
        if len(ars) != 1 or len(usd) != 1:
            continue
        r = float(ars.iloc[0]) / float(usd.iloc[0])
        # Un cociente fuera de este rango no es un tipo de cambio: es una de las
        # dos puntas con el precio mal cargado.
        if 500 < r < 5000:
            ratios.append(r)

    if len(ratios) < MIN_PARES_FX:
        alertas.append(
            f"Solo {len(ratios)} emisiones cotizan a la vez en pesos y en dolares: no "
            "alcanza para derivar el tipo de cambio del dia. El volumen queda sin "
            "normalizar y las comparaciones de liquidez entre especies de distinta "
            "moneda no son confiables en esta corrida."
        )
        return None

    s = pd.Series(ratios)
    fx = float(s.median())
    dispersion = (s.quantile(0.75) - s.quantile(0.25)) / fx
    if dispersion > 0.05:
        alertas.append(
            f"El tipo de cambio implicito tiene dispersion alta ({dispersion:.1%} entre "
            f"{len(ratios)} emisiones): hay precios desactualizados en alguna punta. "
            "Las comparaciones de liquidez pierden precision."
        )
    return fx


def marcar_datos_sanos(df, alertas):
    """Marca `dato_sano`: si el rendimiento declarado puede ser cierto.

    No corrige ni estima nada — el instrumento queda en el universo para poder
    auditarlo, pero `filtrar_operables` no lo propone. Un swap hacia un ticker
    que figura rindiendo 34 millones por ciento no es una oportunidad, es un
    error de datos disfrazado de oportunidad.
    """
    df["raiz_emision"] = raiz_emision(df["ticker"])
    con_rend = df["rendimiento"].notna()

    grupo = df.groupby("raiz_emision")["rendimiento"]
    discordante = (
        con_rend
        & (grupo.transform("count") > 1)
        & ((df["rendimiento"] - grupo.transform("min")) > DISCORDANCIA_ESPECIES)
    )

    tope = df["segmento"].map(TOPE_SANIDAD_SEGMENTO)
    fuera_de_rango = con_rend & tope.notna() & (df["rendimiento"] > tope)

    df["dato_sano"] = ~(discordante | fuera_de_rango)

    if discordante.any():
        detalle = ", ".join(df.loc[discordante, "ticker"].head(6))
        alertas.append(
            f"{int(discordante.sum())} especies con rendimiento incoherente contra las "
            f"otras especies del mismo bono ({detalle}): su precio esta mal escalado en "
            "la fuente. No se proponen; el resto de las especies de esas emisiones sigue "
            "disponible."
        )
    solo_tope = fuera_de_rango & ~discordante
    if solo_tope.any():
        detalle = ", ".join(
            f"{t} ({r:.0%} en {s})"
            for t, r, s in zip(df.loc[solo_tope, "ticker"], df.loc[solo_tope, "rendimiento"],
                               df.loc[solo_tope, "segmento"])
        )
        n = int(solo_tope.sum())
        alertas.append(
            f"Rendimiento fuera del techo de lo posible para su segmento en "
            f"{n} instrumento{'s' if n > 1 else ''} ({detalle}): se trata como dato roto, "
            "no como oportunidad. No se propone."
        )
    return df


def cargar_universo(alertas, dedup, alerta_sin_segmento=True,
                    devolver_descartados=False):
    """Carga el universo consolidado y lo enriquece para ambos pilares.

    dedup es OBLIGATORIO y sin default a proposito. El armador necesita
    deduplicar (comprar MR46O y MR46D es comprar el mismo bono dos veces
    creyendo que se diversifica); el motor de swaps necesita lo contrario, las
    especies vivas, porque los swaps de perfil rotan justamente entre especies
    de la misma emision (MEP -> Cable). Un default silencioso romperia uno de
    los dos.
    """
    if not os.path.exists(CONSOLIDADO_PATH):
        print(
            "ERROR: no existe data/output/universo_consolidado.xlsx.\n"
            "Corre primero: python3 tools/consolidar_universo.py"
        )
        sys.exit(1)
    df = pd.read_excel(CONSOLIDADO_PATH, sheet_name="Resumen")

    # La renta variable sale antes de segmentar. Si se la dejara caer por el
    # camino de "sin segmento" la alerta diria 750+ instrumentos todas las
    # corridas y taparia el caso que esa alerta existe para mostrar: un bono
    # cuyo tipo de tasa no se reconocio.
    df = df[~df["clase_activo"].isin(CLASES_RENTA_VARIABLE)].copy()

    df["segmento"] = df.apply(asignar_segmento, axis=1)

    descartados = df[df["segmento"].isna()].copy()
    if alerta_sin_segmento and len(descartados):
        alertas.append(
            f"{len(descartados)} instrumentos sin segmento asignable (tipo de tasa "
            "desconocido): quedan fuera del armado."
        )
    df = df[df["segmento"].notna()].copy()

    # Rendimiento unificado: TIR, salvo tasa fija que cotiza por TNA
    df["rendimiento"] = df["tir"]
    mask_tf = df["segmento"] == "tasa_fija"
    df.loc[mask_tf, "rendimiento"] = df.loc[mask_tf, "tna"]

    # Duration: la tasa fija no trae duration -> no comparable en años exactos,
    # pero dtm no esta en el Resumen; se usa el vencimiento como proxy.
    hoy = pd.Timestamp.now().normalize()
    df["duration_aprox"] = df["duration"]
    sin_dur = df["duration_aprox"].isna() & df["maturity"].notna()
    df.loc[sin_dur, "duration_aprox"] = (
        (pd.to_datetime(df.loc[sin_dur, "maturity"]) - hoy).dt.days / 365.25
    )

    # Liquidez comparable. `effectiveVolume` es MONTO OPERADO en la moneda de
    # cotizacion de cada especie, igual que `lastPrice`: la especie en pesos de
    # un bono muestra un volumen ~1.500x mayor que su especie en dolares por el
    # tipo de cambio, no por operarse mas. Con esos numeros crudos el filtro de
    # liquidez descartaba sistematicamente las especies en dolares.
    #
    # Se lleva todo a dolares, no a nominales: liquidez es cuanta PLATA se puede
    # mover sin correr el precio. Medirla en laminas seria otra distorsion — una
    # lamina de DICP vale 33 veces una de TX31, y los dos cotizan en pesos.
    df["moneda_cotizacion"] = [
        "usd" if (len(t) >= 4 and t[-1] in ("D", "C")) else "ars"
        for t in df["ticker"].astype(str)
    ]
    fx = tipo_cambio_implicito(df, alertas)
    df["fx_implicito"] = fx
    if fx:
        df["volumen_usd"] = df["effectiveVolume"].where(
            df["moneda_cotizacion"] == "usd",
            df["effectiveVolume"] / fx,
        )
    else:
        df["volumen_usd"] = df["effectiveVolume"]

    # Grupo de emisor para el limite de concentracion.
    # El nombre del emisor (underlying) viene solo en ~49% de los casos, pero
    # el prefijo de 3 letras del ticker identifica al emisor de forma confiable
    # (validado sobre los casos con nombre: 119 grupos, sin colisiones reales).
    # Se usa como clave de agrupacion; el nombre, cuando existe, solo se muestra.
    df["grupo_emisor"] = df["ticker"].astype(str).str[:3]
    nombres = (
        df[df["underlying"].notna()]
        .groupby("grupo_emisor")["underlying"]
        .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
    )
    df["emisor"] = df["grupo_emisor"].map(nombres)
    df["emisor_identificado"] = df["emisor"].notna()
    df["emisor"] = df["emisor"].fillna("(sin identificar: " + df["grupo_emisor"] + ")")
    df["es_soberano"] = df["clase_activo"] == "bono_soberano"

    # El sector viene de condiciones_estaticas.csv, que no cubre todo el
    # universo. Se propaga dentro del grupo de emisor: si un ticker del grupo
    # tiene sector, los demas son del mismo emisor y por lo tanto del mismo
    # sector. No inventa nada — extiende un dato ya cargado.
    if "sector" not in df.columns:
        df["sector"] = None
    sectores = (
        df[df["sector"].notna()]
        .groupby("grupo_emisor")["sector"]
        .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
    )
    df["sector"] = df["sector"].fillna(df["grupo_emisor"].map(sectores))

    # Clave para controlar concentracion. El prefijo del ticker sirve para
    # corporativos y provincias, pero NO para el soberano: el Tesoro emite bajo
    # muchos prefijos distintos (GD, AE, DIC, TZX, TY3...) y todos son el MISMO
    # riesgo de credito. Agruparlos por prefijo dejaria pasar una cartera
    # integramente soberana como si estuviera diversificada.
    df["clave_riesgo"] = df["grupo_emisor"].where(~df["es_soberano"], "SOBERANO_AR")

    df = marcar_datos_sanos(df, alertas)

    if dedup:
        df = deduplicar_emisiones(df, alertas)
    if devolver_descartados:
        return df, descartados
    return df


def deduplicar_emisiones(df, alertas):
    """Colapsa las especies de liquidacion de una misma emision.

    En el mercado argentino la misma emision cotiza en varias especies segun
    la moneda de liquidacion, con sufijo O / D / C sobre la misma raiz de
    ticker (ej. MR46O, MR46D, MR46C son el mismo bono). Tomarlas como
    instrumentos distintos infla la diversificacion: la cartera compraria el
    mismo bono varias veces creyendo que se diversifica.

    Se agrupa por raiz y se conserva una sola especie por emision: la de datos
    mas completos (vencimiento, ley, moneda de pago), desempatando por volumen.
    Como chequeo de sanidad, solo se colapsan grupos cuyas durations coinciden
    (mismo bono => misma duration); si difieren, no son la misma emision.
    """
    df = df.copy()
    if "raiz_emision" not in df.columns:
        df["raiz_emision"] = raiz_emision(df["ticker"])

    conservar, colapsadas = [], 0
    for raiz, grupo in df.groupby("raiz_emision"):
        if len(grupo) == 1:
            conservar.append(grupo.index[0])
            continue
        durs = grupo["duration"].dropna()
        # Sanidad: la misma emision tiene la misma duration. Si difieren mas de
        # un 5%, son emisiones distintas que comparten raiz: no se colapsan.
        if len(durs) > 1 and (durs.max() - durs.min()) / max(durs.max(), 1e-9) > 0.05:
            conservar.extend(grupo.index)
            continue
        # Se prefiere la especie de datos mas completos y, a igualdad, la mas
        # operada. El desempate va en NOMINALES: con el volumen crudo siempre
        # ganaba la especie en pesos por el tipo de cambio, no por liquidez.
        completitud = grupo[["maturity", "law", "couponCurrency", "underlying"]].notna().sum(axis=1)
        # Un dato roto nunca puede ser el representante de la emision.
        sano = grupo["dato_sano"].astype(int) if "dato_sano" in grupo.columns else 1
        volumen = grupo["volumen_usd"].fillna(0)
        mejor = (sano * 1e24 + completitud * 1e12 + volumen).idxmax()
        conservar.append(mejor)
        colapsadas += len(grupo) - 1

    if colapsadas:
        alertas.append(
            f"{colapsadas} especies de liquidacion colapsadas (mismo bono cotizando en "
            "MEP/Cable/CCL): se conserva una por emision para no duplicar posiciones."
        )
    return df.loc[conservar].copy()


def cargar_renta_variable(alertas):
    """Acciones locales y CEDEARs del consolidado, con precio y volumen.

    Contraparte explicita de cargar_universo(): quien necesite renta variable
    la pide por su nombre. No trae rendimiento, duration ni segmento porque
    esos conceptos no aplican, y por eso mismo nunca se la puede pasar por
    error a una funcion que espera un bono.
    """
    if not os.path.exists(CONSOLIDADO_PATH):
        alertas.append(
            "No existe data/output/universo_consolidado.xlsx: no hay precios de "
            "acciones ni CEDEARs. Correr tools/consolidar_universo.py."
        )
        return None
    df = pd.read_excel(CONSOLIDADO_PATH, sheet_name="Resumen")
    rv = df[df["clase_activo"].isin(CLASES_RENTA_VARIABLE)].copy()
    if not len(rv):
        alertas.append(
            "El universo consolidado no trae acciones ni CEDEARs: se genero con "
            "una version anterior del consolidador, hay que volver a correrlo."
        )
        return None
    sin_precio = int(rv["lastPrice"].isna().sum())
    if sin_precio:
        alertas.append(
            f"{sin_precio} de {len(rv)} acciones/CEDEARs sin precio en esta corrida: "
            "aparecen sin valuar, no se les estima un precio."
        )
    return rv[["ticker", "clase_activo", "lastPrice", "effectiveVolume"]]


def filtrar_operables(df):
    """Instrumentos que se pueden proponer: con rendimiento, con precio, sin el
    flag de revision manual y con el dato en un rango posible."""
    ok = (
        df["rendimiento"].notna()
        & df["lastPrice"].notna()
        & (df["revisar"] != True)  # noqa: E712 (la columna puede venir como object)
    )
    if "dato_sano" in df.columns:
        ok &= df["dato_sano"]
    return df[ok]
