#!/usr/bin/env python3
"""
Armador de Carteras de Renta Fija.

Construye una propuesta de cartera de bonos soberanos, subsoberanos y ONs a
partir del universo consolidado, segun el perfil del cliente: monto, moneda,
horizonte, apetito de riesgo, objetivo de cobertura, o un mix de segmentos
definido a mano.

Logica 100% deterministica: reglas y umbrales configurables, sin IA. La
herramienta PROPONE; la decision final y el analisis crediticio son del usuario.

Spec: procesos-en-diseño/2026-07-busqueda-instrumentos-swap-carteras/06-spec-armador-cartera.md
Uso:
    python3 tools/armar_cartera.py --monto 100000
    python3 tools/armar_cartera.py --monto 50000 --perfil conservador --horizonte corto
    python3 tools/armar_cartera.py --monto 80000 --cobertura devaluacion
    python3 tools/armar_cartera.py --monto 80000 --mix "usd_hard=60,cer=40"
"""

import argparse
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cupones  # noqa: E402  (modulo local, despues de fijar el path)
import segmentos  # noqa: E402
from segmentos import (  # noqa: E402
    DESC_SEGMENTO,
    MONEDA_SEGMENTO,
    NATURALEZA_TASA,
    NOMBRE_NATURALEZA,
)

OUTPUT_DIR = segmentos.OUTPUT_DIR

# Cuanto rendimiento se tolera resignar para ganar un mes de cobro nuevo.
# 0.5pp es el mismo umbral con el que la mesa evalua un swap: por debajo de
# eso la diferencia de tasa no justifica mover nada, asi que ahi si conviene
# desempatar por calendario.
BANDA_RENDIMIENTO = 0.005

# Mix objetivo por objetivo de cobertura (% del total)
MIX_COBERTURA = {
    "devaluacion": {"usd_hard": 70, "dollar_linked": 30},
    "inflacion": {"cer": 100},
    "tasa-pesos": {"tasa_fija": 60, "badlar": 20, "tamar": 20},
    "mixta": {"usd_hard": 50, "cer": 25, "tasa_fija": 15, "dollar_linked": 10},
}

# El perfil no define el mix: define la calidad exigida a los candidatos.
# Sin ratings crediticios en la fuente, se usan proxies observables:
# tope de rendimiento (un rendimiento muy por encima de sus pares en USD es
# distress, no oportunidad), liquidez minima y concentracion maxima por emisor.
#
# max_emisor aplica a emisores CORPORATIVOS. El soberano tiene su propio tope
# (max_soberano): en el mercado argentino los segmentos en pesos (CER, tasa
# fija) son casi integramente soberanos, asi que exigirle el limite corporativo
# haria inviable cualquier cartera en pesos. El riesgo soberano se acota, pero
# como riesgo pais agregado, no como concentracion de credito corporativo.
#
# max_sector acota la exposicion a un sector economico (O&G, Financiera, Agro...).
# Es un limite mas laxo que el de emisor porque un sector agrupa varios emisores
# y en el mercado local O&G concentra el 40% de las ONs: un tope muy duro dejaria
# sin candidatos al segmento hard-dollar. Los sectores Soberano y Subsoberano
# quedan fuera de este limite: ya los acota max_soberano.
PERFILES = {
    "conservador": {"tope_rend_usd": 0.12, "percentil_liquidez": 50,
                    "max_emisor": 10, "max_soberano": 50, "max_sector": 30},
    "moderado":    {"tope_rend_usd": 0.15, "percentil_liquidez": 25,
                    "max_emisor": 15, "max_soberano": 65, "max_sector": 40},
    "agresivo":    {"tope_rend_usd": 0.20, "percentil_liquidez": 10,
                    "max_emisor": 20, "max_soberano": 80, "max_sector": 55},
}

# Sectores que no participan del limite sectorial: el riesgo soberano ya tiene
# su propio tope y meterlo tambien aca lo acotaria dos veces.
SECTORES_EXENTOS = {"Soberano", "Subsoberano"}

# Rango de duration (años) por horizonte. Los rangos se solapan a proposito:
# la frontera entre corto y mediano plazo no es rigida.
HORIZONTES = {
    "corto": (0.0, 2.0),
    "medio": (1.5, 5.0),
    "largo": (4.0, 99.0),
}


def resolver_mix(params, alertas):
    """Precedencia: --mix explicito > --cobertura > mix por defecto."""
    if params.mix:
        mix = {}
        for parte in params.mix.split(","):
            if "=" not in parte:
                print(f"ERROR: --mix mal formado en '{parte}'. Formato: 'usd_hard=60,cer=40'")
                sys.exit(1)
            seg, pct = parte.split("=", 1)
            seg = seg.strip()
            if seg not in MONEDA_SEGMENTO:
                print(f"ERROR: segmento desconocido '{seg}'. Validos: {', '.join(MONEDA_SEGMENTO)}")
                sys.exit(1)
            mix[seg] = float(pct)
        total = sum(mix.values())
        if abs(total - 100) > 0.01:
            alertas.append(f"El mix indicado suma {total:g}%, se normaliza a 100%.")
            mix = {k: v / total * 100 for k, v in mix.items()}
        return mix, "mix manual"

    if params.cobertura:
        return dict(MIX_COBERTURA[params.cobertura]), f"cobertura {params.cobertura}"

    return dict(MIX_COBERTURA["mixta"]), "mix balanceado (por defecto)"


def filtrar_por_moneda(mix, moneda, alertas):
    if moneda == "todas":
        return mix
    filtrado = {s: p for s, p in mix.items() if MONEDA_SEGMENTO[s] == moneda}
    if not filtrado:
        print(
            f"ERROR: el mix pedido no tiene ningun segmento en moneda '{moneda}'.\n"
            "Revisa --moneda o el mix/cobertura elegido."
        )
        sys.exit(1)
    descartados = set(mix) - set(filtrado)
    if descartados:
        alertas.append(
            f"Por --moneda {moneda} se descartaron segmentos: {', '.join(sorted(descartados))}. "
            "El resto se reescala a 100%."
        )
    total = sum(filtrado.values())
    return {k: v / total * 100 for k, v in filtrado.items()}


def candidatos_del_segmento(universo, segmento, perfil, params, alertas):
    """Aplica los filtros de calidad del perfil sobre un segmento."""
    c = universo[universo["segmento"] == segmento].copy()
    c = segmentos.filtrar_operables(c)

    dur_min, dur_max = HORIZONTES[params.horizonte]
    con_duration = c["duration"].notna()
    c = c[con_duration & c["duration"].between(dur_min, dur_max)]

    # Tope de rendimiento: solo tiene sentido en USD. En pesos, rendimientos
    # de 25-30% son normales (inflacion), no señal de distress.
    if MONEDA_SEGMENTO[segmento] == "usd":
        c = c[c["rendimiento"] <= perfil["tope_rend_usd"]]

    # Piso de rendimiento: no tiene sentido comprar rendimiento negativo
    c = c[c["rendimiento"] > params.min_rend / 100.0]

    # Liquidez: percentil calculado dentro del propio segmento, sobre el monto
    # operado llevado a dolares. Con el volumen crudo el percentil comparaba
    # pesos contra dolares (la misma emision muestra ~1.500x mas volumen en su
    # especie en pesos) y terminaba filtrando por moneda de cotizacion en vez de
    # por liquidez.
    if len(c) and c["volumen_usd"].notna().any():
        piso = c["volumen_usd"].quantile(perfil["percentil_liquidez"] / 100.0)
        c = c[c["volumen_usd"].fillna(0) >= piso]

    return c.sort_values("rendimiento", ascending=False)


def meses_de(fila, params):
    """Meses del calendario en los que este instrumento paga RENTA en los
    proximos 12 meses. Vacio si no hay cashflow para el ticker."""
    flujos = getattr(params, "_flujos", None)
    if flujos is None:
        return set()
    return cupones.meses_cubiertos(flujos, [fila["ticker"]], params._hoy)


def sector_computable(fila):
    """Sector que participa del limite sectorial, o None si no aplica.

    None cuando el dato falta (no se puede acotar lo que no se conoce) o
    cuando el sector ya esta acotado por el tope soberano."""
    s = fila.get("sector")
    if pd.isna(s) or s in SECTORES_EXENTOS:
        return None
    return s


def elegir_siguiente(cand, ya, peso_acumulado, peso_posicion, perfil, params,
                     meses_cubiertos, peso_sector):
    """Proximo instrumento del segmento.

    Recorre los candidatos ordenados por rendimiento y descarta los que rompen
    concentracion. Entre los que quedan, si el analisis de cupones esta activo,
    prefiere al que suma un mes de cobro nuevo — pero solo dentro de una banda
    de rendimiento cercana al mejor disponible, para no resignar tasa por
    ordenar el calendario.
    """
    elegidos_tk = {f["ticker"] for f in ya}
    viables = []
    for _, fila in cand.iterrows():
        if fila["ticker"] in elegidos_tk:
            continue
        g = fila["clave_riesgo"]
        tope = perfil["max_soberano"] if fila["es_soberano"] else perfil["max_emisor"]
        if peso_acumulado.get(g, 0) + peso_posicion > tope + 1e-9:
            continue
        sec = sector_computable(fila)
        if sec and peso_sector.get(sec, 0) + peso_posicion > perfil["max_sector"] + 1e-9:
            continue
        viables.append(fila)
    if not viables:
        return None

    if not getattr(params, "pago_mensual", True) or getattr(params, "_flujos", None) is None:
        return viables[0]

    # Banda de tolerancia: solo se desempata entre candidatos que rinden como
    # maximo BANDA_RENDIMIENTO por debajo del mejor. Fuera de esa banda manda
    # el rendimiento y el calendario no opina.
    mejor = viables[0]["rendimiento"]
    banda = [f for f in viables if f["rendimiento"] >= mejor - BANDA_RENDIMIENTO]
    aportan = [f for f in banda if meses_de(f, params) - meses_cubiertos]
    if not aportan:
        return viables[0]
    # Entre los que aportan meses nuevos, el que mas aporta; a igualdad, el que mas rinde.
    return max(aportan, key=lambda f: (len(meses_de(f, params) - meses_cubiertos), f["rendimiento"]))


def armar(universo, mix, perfil, params, alertas):
    """Selecciona instrumentos segmento por segmento, pero controlando la
    concentracion por emisor de forma GLOBAL sobre la cartera.

    El control tiene que ser global: un emisor puede aparecer en varios
    segmentos a la vez (el soberano cotiza en hard-dollar, CER y tasa fija),
    asi que limitarlo dentro de cada segmento por separado no acota nada.

    Si hay cashflow disponible, ante candidatos de rendimiento parejo se
    prioriza al que paga en un mes todavia sin cobros. La previsibilidad del
    ingreso mensual es criterio de armado, no un reporte posterior.
    """
    partes = []
    peso_acumulado = {}  # clave_riesgo -> % de cartera ya comprometido
    peso_sector = {}     # sector -> % de cartera ya comprometido
    meses_ya_cubiertos = set()  # meses del año con al menos un cobro de renta

    # Los segmentos mas chicos se resuelven primero: son los que tienen menos
    # candidatos disponibles, asi no se quedan sin lugar por el limite global.
    for segmento, pct in sorted(mix.items(), key=lambda kv: kv[1]):
        n_objetivo = max(1, round(params.n_total * pct / 100))
        cand = candidatos_del_segmento(universo, segmento, perfil, params, alertas)
        if not len(cand):
            alertas.append(
                f"Segmento {segmento} ({pct:g}%): sin candidatos que cumplan los filtros "
                "del perfil y el horizonte. Su peso se redistribuye en el resto."
            )
            continue

        peso_posicion = pct / n_objetivo
        elegidos = []
        for _ in range(n_objetivo):
            fila = elegir_siguiente(
                cand, elegidos, peso_acumulado, peso_posicion, perfil,
                params, meses_ya_cubiertos, peso_sector,
            )
            if fila is None:
                break
            elegidos.append(fila)
            g = fila["clave_riesgo"]
            peso_acumulado[g] = peso_acumulado.get(g, 0) + peso_posicion
            sec = sector_computable(fila)
            if sec:
                peso_sector[sec] = peso_sector.get(sec, 0) + peso_posicion
            meses_ya_cubiertos |= meses_de(fila, params)

        if not elegidos:
            alertas.append(
                f"Segmento {segmento} ({pct:g}%): habia candidatos pero ninguno entra sin "
                "romper los limites de concentracion. Su peso se redistribuye en el resto."
            )
            continue
        if len(elegidos) < n_objetivo:
            alertas.append(
                f"Segmento {segmento}: se buscaban {n_objetivo} posiciones y entraron "
                f"{len(elegidos)} sin romper los limites de concentracion. El segmento queda "
                f"en {peso_posicion * len(elegidos):.1f}% en vez de {pct:g}%; el resto se "
                "redistribuye proporcionalmente."
            )
        sel = pd.DataFrame(elegidos)
        # Cada posicion conserva el peso con el que se valido contra los topes.
        # Repartir el pct completo del segmento entre menos posiciones inflaria
        # cada una por encima del limite que el motor ya habia verificado.
        sel["pct_cartera"] = peso_posicion
        partes.append(sel)

    if not partes:
        print("\nNo se pudo armar ninguna posicion con los filtros indicados.")
        for a in alertas:
            print(f"  ! {a}")
        print("\nProba relajar: --perfil agresivo, otro --horizonte, o --min-rend mas bajo.")
        sys.exit(1)

    cartera = pd.concat(partes, ignore_index=True)

    # Si algun segmento quedo vacio, el total no llega a 100%: se reescala
    total_pct = cartera["pct_cartera"].sum()
    if abs(total_pct - 100) > 0.01:
        alertas.append(
            f"Los segmentos cubiertos suman {total_pct:.1f}%: se reescala la cartera a "
            "100% con lo disponible."
        )
        cartera["pct_cartera"] = cartera["pct_cartera"] / total_pct * 100

    verificar_concentracion(cartera, perfil, alertas)
    cartera["monto"] = cartera["pct_cartera"] / 100 * params.monto
    return cartera


def verificar_concentracion(cartera, perfil, alertas):
    """Chequeo post-hoc: la reponderacion final puede empujar a un emisor por
    encima de su tope. Si pasa, se avisa explicitamente en vez de silenciarlo."""
    real = cartera.groupby("clave_riesgo").agg(
        pct=("pct_cartera", "sum"),
        soberano=("es_soberano", "any"),
        nombre=("emisor", "first"),
    )
    for clave, f in real.iterrows():
        tope = perfil["max_soberano"] if f["soberano"] else perfil["max_emisor"]
        if f["pct"] > tope + 0.01:
            que = "Riesgo soberano argentino (todas las emisiones del Tesoro)" if f["soberano"] else f["nombre"]
            alertas.append(
                f"Concentracion: {que} quedo en {f['pct']:.1f}%, por encima del tope "
                f"de {tope:g}%. Ocurre al reponderar cuando otros segmentos quedaron sin "
                "candidatos. Revisar antes de proponer la cartera."
            )

    computable = cartera[cartera.apply(sector_computable, axis=1).notna()]
    if len(computable):
        por_sector = computable.groupby("sector")["pct_cartera"].sum()
        for sec, pct in por_sector.items():
            if pct > perfil["max_sector"] + 0.01:
                alertas.append(
                    f"Concentracion sectorial: {sec} quedo en {pct:.1f}%, por encima del "
                    f"tope de {perfil['max_sector']:g}%. Revisar antes de proponer la cartera."
                )


def resumir(cartera, params):
    """Metricas ponderadas por peso en la cartera.

    El rendimiento se reporta SEPARADO POR NATURALEZA DE TASA: promediar una TIR
    en dolares con una tasa real sobre CER y con una TNA nominal en pesos daria
    un numero sin significado economico. La duration si se puede ver agregada,
    porque mide sensibilidad temporal en la misma unidad (años).
    """
    cartera = cartera.copy()
    cartera["naturaleza"] = cartera["segmento"].map(NATURALEZA_TASA)

    por_naturaleza = []
    for naturaleza, grupo in cartera.groupby("naturaleza"):
        peso = grupo["pct_cartera"].sum()
        w = grupo["pct_cartera"] / peso
        por_naturaleza.append({
            "naturaleza": naturaleza,
            "pct": peso,
            "posiciones": len(grupo),
            "rendimiento_pond": (grupo["rendimiento"] * w).sum(),
            "duration_pond": (grupo["duration"] * w).sum(),
        })
    por_naturaleza = pd.DataFrame(por_naturaleza).sort_values("pct", ascending=False)

    # Duration agregada de toda la cartera (si es comparable en unidad temporal)
    dur_pond = (cartera["duration"] * cartera["pct_cartera"] / 100).sum()

    por_segmento = (
        cartera.groupby("segmento")
        .agg(posiciones=("ticker", "size"), pct=("pct_cartera", "sum"), monto=("monto", "sum"))
        .reset_index()
        .sort_values("pct", ascending=False)
    )
    por_segmento["rendimiento_prom"] = [
        (cartera.loc[cartera.segmento == s, "rendimiento"]
         * cartera.loc[cartera.segmento == s, "pct_cartera"]).sum()
        / cartera.loc[cartera.segmento == s, "pct_cartera"].sum()
        for s in por_segmento["segmento"]
    ]
    por_emisor = (
        cartera.groupby("emisor")
        .agg(posiciones=("ticker", "size"), pct=("pct_cartera", "sum"), monto=("monto", "sum"))
        .reset_index()
        .sort_values("pct", ascending=False)
    )
    por_sector = (
        cartera.dropna(subset=["sector"])
        .groupby("sector")
        .agg(posiciones=("ticker", "size"), pct=("pct_cartera", "sum"), monto=("monto", "sum"))
        .reset_index()
        .sort_values("pct", ascending=False)
    )
    return por_naturaleza, dur_pond, por_segmento, por_emisor, por_sector


def exportar(cartera, resumen_tuple, mix, origen_mix, params, perfil, alertas, ruta, cal, tot):
    por_naturaleza, dur_pond, por_segmento, por_emisor, por_sector = resumen_tuple

    detalle = pd.DataFrame({
        "Ticker": cartera["ticker"],
        "Emisor": cartera["emisor"],
        "Sector": cartera["sector"],
        "Segmento": cartera["segmento"].map(DESC_SEGMENTO),
        "Rinde": cartera["rendimiento"],
        "Duration (años)": cartera["duration"].round(2),
        "Vencimiento": cartera["maturity"],
        "Ley": cartera["law"],
        "Cobra en": cartera["couponCurrency"],
        "Calificación": cartera["calificacion"],
        "Lámina mínima": cartera["lamina"],
        "Paridad": cartera["paridad"],
        "Valor residual": cartera["residualValue"],
        "% Cartera": cartera["pct_cartera"].round(2),
        f"Monto ({params.moneda_label})": cartera["monto"].round(2),
        "Emisor identificado": cartera["emisor_identificado"].map({True: "si", False: "no"}),
    }).sort_values(["Segmento", "% Cartera"], ascending=[True, False])

    filas_resumen = [
        ("Monto total", f"{params.monto:,.2f} {params.moneda_label}"),
        ("Posiciones", len(cartera)),
        ("Duration promedio ponderada", f"{dur_pond:.2f} años"),
        ("Emisores distintos", cartera["emisor"].nunique()),
        ("Maxima concentracion en un emisor", f"{por_emisor['pct'].max():.1f}%"),
        ("Riesgo soberano agregado", f"{cartera.loc[cartera['es_soberano'], 'pct_cartera'].sum():.1f}%"),
        ("Sectores distintos", len(por_sector)),
    ]
    if tot is not None:
        filas_resumen += [
            ("Renta esperada 12 meses", f"{tot['renta_anual']:,.2f} {params.moneda_label} "
                                        f"({tot['renta_anual'] / params.monto:.2%} del capital)"),
            ("Renta mensual promedio", f"{tot['renta_mensual_promedio']:,.2f} {params.moneda_label}"),
            ("Meses sin cobro de renta", tot["meses_sin_renta"]),
        ]
    filas_resumen += [
        ("", ""),
        ("RENDIMIENTO POR NATURALEZA DE TASA", "(no se promedian entre si: son tasas de distinta unidad)"),
    ]
    for _, m in por_naturaleza.iterrows():
        filas_resumen.append((
            f"  {NOMBRE_NATURALEZA.get(m['naturaleza'], m['naturaleza'])}",
            f"{m['rendimiento_pond']:.2%} · {m['pct']:.1f}% de la cartera · "
            f"duration {m['duration_pond']:.2f} años",
        ))
    filas_resumen += [
        ("", ""),
        ("Perfil", params.perfil),
        ("Horizonte", f"{params.horizonte} (duration {HORIZONTES[params.horizonte][0]}-{HORIZONTES[params.horizonte][1]} años)"),
        ("Origen del mix", origen_mix),
        ("Moneda", params.moneda),
        ("Tope por emisor corporativo", f"{perfil['max_emisor']:g}%"),
        ("Tope riesgo soberano", f"{perfil['max_soberano']:g}%"),
    ]
    resumen_general = pd.DataFrame(filas_resumen, columns=["Concepto", "Valor"])

    seg_out = pd.DataFrame({
        "Segmento": por_segmento["segmento"].map(DESC_SEGMENTO),
        "Posiciones": por_segmento["posiciones"],
        "% Cartera": por_segmento["pct"].round(2),
        f"Monto ({params.moneda_label})": por_segmento["monto"].round(2),
        "Rendimiento promedio": por_segmento["rendimiento_prom"],
    })
    emi_out = pd.DataFrame({
        "Emisor": por_emisor["emisor"],
        "Posiciones": por_emisor["posiciones"],
        "% Cartera": por_emisor["pct"].round(2),
        f"Monto ({params.moneda_label})": por_emisor["monto"].round(2),
    })
    sec_out = pd.DataFrame({
        "Sector": por_sector["sector"],
        "Posiciones": por_sector["posiciones"],
        "% Cartera": por_sector["pct"].round(2),
        f"Monto ({params.moneda_label})": por_sector["monto"].round(2),
    })

    leyenda = pd.DataFrame([
        ("Rinde", "TIR anual del instrumento. En tasa fija en pesos (LECAP/BONCAP) es TNA."),
        ("Duration", "Plazo promedio ponderado de los flujos: a mayor duration, mas sensible el precio a cambios de tasa."),
        ("% Cartera", "Peso de la posicion. Dentro de cada segmento las posiciones van equiponderadas."),
        ("Monto", "Plata a asignar a esa posicion. NO son nominales: convertir a nominales requiere el precio de operacion en la moneda de inversion y la lamina minima del bono, que se verifican al operar."),
        ("Emisor", "Agrupado por prefijo del ticker (3 letras), criterio validado contra los emisores conocidos. Cuando el nombre no viene en la fuente se muestra '(sin identificar)', pero el limite de concentracion igual se aplica sobre el grupo."),
        ("Emisor identificado", "'no' = el nombre del emisor no viene en la fuente. La concentracion igual esta controlada por el prefijo del ticker."),
        ("Ley / Cobra en", "Ley de emision y moneda de pago del cupon. Vacio = el dato no esta en data/condiciones_estaticas.csv para ese ticker."),
        ("Calificacion", "Calificacion crediticia de la emision, de data/condiciones_estaticas.csv. Vacio = no cargada. La herramienta NO la estima ni la usa como filtro: el analisis crediticio sigue siendo tuyo."),
        ("Lamina minima", "Valor nominal minimo operable. El monto propuesto NO esta ajustado a lamina: verificar al operar que la posicion sea multiplo de este numero."),
        ("Valor residual", "Cuanto del capital original queda vivo. Menos de 100 = el bono ya amortizo parte."),
        ("", ""),
        ("Rendimiento por naturaleza de tasa", "En el Resumen el rendimiento va abierto en 4 categorias que NO se promedian entre si: TIR en dolares, rendimiento dolar linked, tasa REAL sobre CER (por encima de la inflacion) y TNA NOMINAL en pesos. Un promedio unico entre ellas no tiene significado economico."),
        ("Sector", "Sector economico del emisor, de data/condiciones_estaticas.csv. Se propaga dentro del grupo de emisor (mismo prefijo de ticker = mismo emisor = mismo sector). Vacio = no cargado; esas posiciones quedan fuera del limite sectorial. Soberano y Subsoberano estan exentos del limite: ya los acota el tope de riesgo soberano."),
        ("Riesgo soberano agregado", "Suma de TODAS las emisiones del Tesoro, sin importar el prefijo del ticker (GD, AE, DIC, TZX, TY3... son el mismo riesgo de credito). Si supera el tope del perfil aparece alertado."),
        ("", ""),
        ("Hoja Calendario", "Cobros proyectados de los proximos 12 meses, separando RENTA (cupon de interes) de AMORTIZACION (devolucion de capital). Solo la renta es rendimiento; la amortizacion es capital que vuelve y hay que reinvertir. Se calcula sobre el cashflow contractual de cada bono a precio de hoy."),
        ("Que NO contempla", "Calificacion crediticia (no esta en la fuente: el analisis crediticio es del usuario), lamina minima. El calendario asume que los pagos se cumplen en fecha y, en bonos ajustables (CER, dolar linked, Badlar, Tamar), que el coeficiente de ajuste es el de hoy: el monto nominal futuro va a diferir."),
    ], columns=["Columna", "Que significa"])

    parametros = pd.DataFrame(
        [(k, str(v)) for k, v in vars(params).items()] + [("perfil_" + k, v) for k, v in perfil.items()],
        columns=["parametro", "valor"],
    )
    alertas_df = pd.DataFrame({"Alertas de esta corrida": alertas or ["Sin alertas."]})

    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        detalle.to_excel(writer, sheet_name="Cartera", index=False)
        resumen_general.to_excel(writer, sheet_name="Resumen", index=False)
        seg_out.to_excel(writer, sheet_name="Resumen", index=False, startrow=len(resumen_general) + 3)
        emi_out.to_excel(writer, sheet_name="Resumen", index=False,
                         startrow=len(resumen_general) + len(seg_out) + 7)
        sec_out.to_excel(writer, sheet_name="Resumen", index=False,
                         startrow=len(resumen_general) + len(seg_out) + len(emi_out) + 11)
        if cal is not None:
            cal_out = pd.DataFrame({
                "Mes": cal["Mes"],
                f"Renta ({params.moneda_label})": cal["renta"].round(2),
                f"Amortizacion ({params.moneda_label})": cal["amortizacion"].round(2),
                f"Total ({params.moneda_label})": cal["total"].round(2),
                "Posiciones que pagan": cal["posiciones"].astype(int),
            })
            cal_out.to_excel(writer, sheet_name="Calendario", index=False)
            tot_out = pd.DataFrame([
                ("Renta 12 meses", f"{tot['renta_anual']:,.2f} {params.moneda_label}"),
                ("Renta sobre el capital", f"{tot['renta_anual'] / params.monto:.2%}"),
                ("Renta mensual promedio", f"{tot['renta_mensual_promedio']:,.2f} {params.moneda_label}"),
                ("Amortizacion 12 meses", f"{tot['amortizacion_anual']:,.2f} {params.moneda_label}"),
                ("Cobro total 12 meses", f"{tot['cobro_total']:,.2f} {params.moneda_label}"),
                ("Meses sin cobro de renta", tot["meses_sin_renta"]),
                ("Mes de mayor renta", tot["mes_mas_fuerte"]),
                ("Mes de menor renta", tot["mes_mas_flaco"]),
            ], columns=["Concepto", "Valor"])
            tot_out.to_excel(writer, sheet_name="Calendario", index=False,
                             startrow=len(cal_out) + 3)

        alertas_df.to_excel(writer, sheet_name="Alertas", index=False)
        leyenda.to_excel(writer, sheet_name="Leyenda", index=False)
        parametros.to_excel(writer, sheet_name="Parametros", index=False)

        ws = writer.sheets["Cartera"]
        ws.freeze_panes = "A2"
        for idx, col in enumerate(detalle.columns, start=1):
            letra = ws.cell(row=1, column=idx).column_letter
            if col in ("Rinde", "Paridad"):
                for celda in ws[letra][1:]:
                    celda.number_format = "0.00%"
            ws.column_dimensions[letra].width = max(12, len(col) + 3)
        ws2 = writer.sheets["Resumen"]
        ws2.column_dimensions["A"].width = 42
        ws2.column_dimensions["B"].width = 26
        writer.sheets["Leyenda"].column_dimensions["A"].width = 22
        writer.sheets["Leyenda"].column_dimensions["B"].width = 115
        writer.sheets["Alertas"].column_dimensions["A"].width = 120


def main():
    ap = argparse.ArgumentParser(description="Armador de carteras de renta fija")
    ap.add_argument("--monto", type=float, required=True, help="Monto total a invertir")
    ap.add_argument("--moneda", choices=["usd", "ars", "todas"], default="todas",
                    help="Restringe a segmentos que cobran en esa moneda (default: todas)")
    ap.add_argument("--horizonte", choices=list(HORIZONTES), default="medio",
                    help="Define el rango de duration objetivo (default: medio)")
    ap.add_argument("--perfil", choices=list(PERFILES), default="moderado",
                    help="Exigencia de calidad: tope de rendimiento, liquidez y concentracion (default: moderado)")
    ap.add_argument("--cobertura", choices=list(MIX_COBERTURA), default=None,
                    help="Objetivo de cobertura: define el mix de segmentos")
    ap.add_argument("--mix", default=None,
                    help="Mix manual por segmento, ej: 'usd_hard=60,cer=40'. Tiene prioridad sobre --cobertura")
    ap.add_argument("--n-total", type=int, default=15,
                    help="Cantidad objetivo de posiciones en la cartera (default: 15)")
    ap.add_argument("--max-emisor", type=float, default=None,
                    help="Maximo %% de la cartera por emisor corporativo. Default segun perfil")
    ap.add_argument("--max-sector", type=float, default=None,
                    help="Maximo %% de la cartera en un sector economico. Default segun perfil")
    ap.add_argument("--max-soberano", type=float, default=None,
                    help="Maximo %% de la cartera en riesgo soberano argentino. Default segun perfil")
    ap.add_argument("--min-rend", type=float, default=0.0,
                    help="Rendimiento minimo en %% para considerar un instrumento (default: 0)")
    ap.add_argument("--sin-pago-mensual", dest="pago_mensual", action="store_false",
                    help="No prioriza cubrir los 12 meses de cobro: elige solo por rendimiento")
    params = ap.parse_args()

    alertas = []
    perfil = dict(PERFILES[params.perfil])
    if params.max_emisor is not None:
        perfil["max_emisor"] = params.max_emisor
    if params.max_soberano is not None:
        perfil["max_soberano"] = params.max_soberano
    if params.max_sector is not None:
        perfil["max_sector"] = params.max_sector
    params.moneda_label = {"usd": "USD", "ars": "ARS", "todas": "moneda de inversion"}[params.moneda]

    # dedup=True: comprar dos especies de la misma emision (MR46O y MR46D) es
    # comprar el mismo bono dos veces creyendo que se diversifica.
    universo = segmentos.cargar_universo(alertas, dedup=True)

    # Cupones: si el cashflow no esta, el armador sigue funcionando sin
    # calendario en vez de cortar.
    params._hoy = pd.Timestamp.now().normalize()
    cashflow = cupones.cargar_cashflow(alertas)
    params._flujos = cupones.flujos_por_peso(universo, cashflow, params._hoy, alertas)
    if params._flujos is None and params.pago_mensual:
        alertas.append("Sin cashflow disponible: no se pudo priorizar la cobertura mensual de cobros.")

    mix, origen_mix = resolver_mix(params, alertas)
    mix = filtrar_por_moneda(mix, params.moneda, alertas)
    cartera = armar(universo, mix, perfil, params, alertas)
    resumen_tuple = resumir(cartera, params)
    por_naturaleza, dur_pond, por_segmento, por_emisor, por_sector = resumen_tuple

    # Alertas de honestidad sobre los limites del dato disponible
    sin_emisor = int((~cartera["emisor_identificado"]).sum())
    if sin_emisor:
        alertas.append(
            f"{sin_emisor} de {len(cartera)} posiciones no traen el nombre del emisor en la fuente. "
            "La concentracion igual se controlo agrupando por prefijo de ticker."
        )
    sin_sector = int(cartera["sector"].isna().sum())
    if sin_sector:
        alertas.append(
            f"{sin_sector} de {len(cartera)} posiciones sin sector cargado en "
            "data/condiciones_estaticas.csv: quedan fuera del limite de concentracion "
            "sectorial (no se acota lo que no se conoce)."
        )
    alertas.append(
        "Los montos por posicion no estan ajustados a lamina minima (dato no disponible): "
        "verificar al operar."
    )
    # El motor reparte el monto entre n_total posiciones sin mirar si cada tramo
    # es operable. Con montos chicos arma carteras de tickets irrisorios.
    min_ticket = cartera["monto"].min()
    if min_ticket < 1000:
        sugeridas = max(1, int(params.monto // 5000))
        alertas.append(
            f"Monto por posicion demasiado chico: la menor queda en "
            f"{min_ticket:,.0f} {params.moneda_label}. Con {params.monto:,.0f} conviene "
            f"bajar --n-total (hoy {params.n_total}) a "
            f"{sugeridas} posicion{'es' if sugeridas > 1 else ''}."
        )

    ahora = datetime.now()
    print("=" * 70)
    print(f"ARMADOR DE CARTERA — {ahora:%d/%m/%Y %H:%M}")
    print(f"{params.monto:,.0f} {params.moneda_label} | perfil {params.perfil} | "
          f"horizonte {params.horizonte} | {origen_mix}")
    print("=" * 70)

    for _, s in por_segmento.iterrows():
        print(f"\n▸ {DESC_SEGMENTO[s['segmento']]}")
        print(f"   {s['pct']:.1f}% ({s['monto']:,.0f}) · {s['posiciones']} posiciones · "
              f"rendimiento promedio {s['rendimiento_prom']:.2%}")
        sub = cartera[cartera.segmento == s["segmento"]].sort_values("pct_cartera", ascending=False)
        for _, f in sub.iterrows():
            venc = f["maturity"].strftime("%m/%Y") if pd.notna(f["maturity"]) else "s/d"
            print(f"     {f['ticker']:7} {f['emisor'][:34]:36} {f['rendimiento']:6.2%}  "
                  f"dur {f['duration']:4.1f}  vto {venc}  {f['pct_cartera']:5.2f}%  "
                  f"{f['monto']:>10,.0f}")

    print("\n" + "-" * 70)
    print(f"TOTAL: {len(cartera)} posiciones · duration ponderada {dur_pond:.2f} años")
    print("Rendimiento por naturaleza de tasa (no se promedian entre si):")
    for _, m in por_naturaleza.iterrows():
        print(f"   {NOMBRE_NATURALEZA.get(m['naturaleza'], m['naturaleza']):48} "
              f"{m['rendimiento_pond']:6.2%}  sobre {m['pct']:.1f}% de la cartera")
    print(f"Emisores distintos: {cartera['emisor'].nunique()} · "
          f"maxima concentracion: {por_emisor['pct'].max():.1f}% ({por_emisor.iloc[0]['emisor'][:40]})")
    print(f"Riesgo soberano agregado: {cartera.loc[cartera['es_soberano'], 'pct_cartera'].sum():.1f}% "
          f"(tope del perfil: {perfil['max_soberano']:g}%)")
    if len(por_sector):
        sin_sec = int(cartera["sector"].isna().sum())
        detalle = f" · {sin_sec} sin sector cargado" if sin_sec else ""
        # El tope solo aplica a sectores no exentos: mostrar el maximo global
        # contra el tope seria comparar contra algo que no lo rige.
        acotables = por_sector[~por_sector["sector"].isin(SECTORES_EXENTOS)]
        if len(acotables):
            top = acotables.iloc[0]
            print(f"Sectores: {len(por_sector)} · mayor sector acotable {top['pct']:.1f}% "
                  f"({top['sector']}, tope {perfil['max_sector']:g}%){detalle}")
        else:
            print(f"Sectores: {len(por_sector)} · sin sectores sujetos al tope{detalle}")

    cal, tot = cupones.calendario(cartera, params._flujos, params._hoy)
    if cal is not None:
        print("\n" + "-" * 70)
        print("CALENDARIO DE COBROS — proximos 12 meses")
        print(f"{'Mes':10}{'Renta':>12}{'Amortizacion':>15}{'Total':>13}{'Pagan':>8}")
        for _, m in cal.iterrows():
            marca = "  <- sin renta" if m["renta"] <= 0 else ""
            print(f"{m['Mes']:10}{m['renta']:>12,.0f}{m['amortizacion']:>15,.0f}"
                  f"{m['total']:>13,.0f}{int(m['posiciones']):>8}{marca}")
        print(f"\nRenta 12 meses: {tot['renta_anual']:,.0f} {params.moneda_label} "
              f"({tot['renta_anual'] / params.monto:.2%} del capital) · "
              f"promedio mensual {tot['renta_mensual_promedio']:,.0f}")
        if tot["meses_sin_renta"]:
            print(f"⚠ {tot['meses_sin_renta']} mes(es) sin cobro de renta.")
        else:
            print("✓ Los 12 meses tienen cobro de renta.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # El perfil y los segundos van en el nombre: dos corridas del mismo minuto
    # con parametros distintos se pisaban entre si.
    ruta = os.path.join(
        OUTPUT_DIR,
        f"cartera_{params.perfil}_{params.horizonte}_{ahora:%Y-%m-%d_%H%M%S}.xlsx",
    )
    exportar(cartera, resumen_tuple, mix, origen_mix, params, perfil, alertas, ruta, cal, tot)
    segmentos.podar_outputs("cartera_")
    print(f"\nOutput: {ruta}")

    if alertas:
        print("\n⚠ ALERTAS:")
        for a in alertas:
            print(f"  ! {a}")


if __name__ == "__main__":
    main()
