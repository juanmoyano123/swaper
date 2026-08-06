#!/usr/bin/env python3
"""
Motor de Deteccion de Swaps.

Recorre el universo consolidado (output de consolidar_universo.py) buscando
rotaciones: instrumentos de rendimiento bajo que puedan cambiarse por
alternativas de mayor TIR o mejor perfil (moneda de pago, ley, liquidez)
dentro del mismo segmento comparable.

Logica 100% deterministica: el motor PROPONE, la decision y el analisis
crediticio profundo son del usuario.

Spec: docs/historial/2026-07-diseno-wat/05-spec-motor-swaps.md
Uso:
    python3 tools/detectar_swaps.py                     # origenes = TIR negativa
    python3 tools/detectar_swaps.py --origen todos      # analiza todo el universo
    python3 tools/detectar_swaps.py --cartera data/cartera.csv
    python3 tools/detectar_swaps.py --min-dtir 0.3
    python3 tools/detectar_swaps.py --frecuencia-cupon mensual
    python3 tools/detectar_swaps.py --tope-distress "usd_hard=15,tamar=60"
"""

import argparse
import math
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cupones  # noqa: E402  (modulo local, despues de fijar el path)
import mercado  # noqa: E402
import segmentos  # noqa: E402

CARTERA_DEFAULT = os.path.join(segmentos.BASE_DIR, "data", "cartera.csv")
OUTPUT_DIR = segmentos.OUTPUT_DIR

# ---------------------------------------------------------------------------
# La segmentacion vive en tools/segmentos.py, compartida con el armador de
# carteras. Los swaps solo se proponen DENTRO de un segmento: cruces entre
# segmentos (ej. CER -> hard-dollar) son vision macro humana, no un swap.
# ---------------------------------------------------------------------------

# Tope de sanidad ("anti-distress"): un destino que rinde MUY por encima de sus
# pares no es una oportunidad, es un precio roto — el mercado le pide esa tasa
# porque duda del cobro (ej. TIR 245% en una ON hard-dollar). La mesa elige
# pares de calidad comparable, no el extremo de la curva.
#
# Estos son SOLO defaults; el numero lo fija el usuario con --tope-distress.
# Viene cargado unicamente usd_hard=15%, que es el valor calibrado con la mesa.
# Los segmentos en pesos quedan sin tope duro por default: ahi una TNA de 40%
# es tasa normal, no distress, y poner un numero inventado seria peor que no
# poner ninguno.
TOPE_DISTRESS_DEFAULT = {"usd_hard": 0.15}

# Señalamiento informativo (no descarta): destino que cae en la cola alta de su
# propio segmento. Se define por percentil y no por un multiplo de la mediana
# porque el multiplo ignora la dispersion: en hard-dollar la mediana es 6,3% y
# 1,5 veces esa mediana marcaba como sospechoso a cualquier corporativo de 10%,
# que es tasa normal para el credito corporativo local. El percentil se calibra
# solo contra la forma real de la curva de cada segmento.
PERCENTIL_DISTRESS_DEFAULT = 95
MIN_OPERABLES_PERCENTIL = 10  # con menos candidatos el percentil no dice nada

# Banda dentro de la cual dos destinos se consideran parejos en rendimiento.
# Mismo criterio que usa el armador para desempatar por calendario de cobros.
BANDA_RENDIMIENTO_PP = 0.5

# Escenarios de movimiento de TIR para la hoja de sensibilidad, en bps.
ESCENARIOS_TIR_DEFAULT = "-500,-400,-300,-200,-100,0,100,200"

# Tolerancia de duration para emparejar ley local contra ley extranjera (en años).
TOL_DURATION_LEY = 0.25

# La fuente publica dos leyes: Argentina y N.Y. En el archivo cargado a mano
# sobreviven cuatro tickers con "Extranjera" y "Ley Europea" de una carga previa;
# se los cuenta como extranjera porque para el tenedor el punto es la
# jurisdiccion (un default se litiga afuera), pero no se agrega ninguna
# categoria que la fuente no publique.
LEY_LOCAL = "Ley Argentina"
LEYES_EXTRANJERAS = {"Ley N.Y.", "Ley Europea", "Extranjera"}


def es_extranjera(ley):
    return str(ley) in LEYES_EXTRANJERAS


# Clases de activo para acotar el analisis. El swap se limita a la clase tanto
# en el origen como en el destino: pedir "solo ONs" es querer ver rotaciones
# entre corporativos, no de un corporativo a un soberano.
CLASES = {
    "on": "on_corporativo",
    "soberano": "bono_soberano",
    "subsoberano": "bono_subsoberano",
}


def categoria_credito(fila):
    """Soberano / subsoberano / corporativo.

    Al abrir la segmentacion a todo el universo, los segmentos en pesos dejaron
    de ser 100% soberanos: ahora conviven Tesoro, provincias y ONs dentro del
    mismo segmento, y un swap Nacion -> provincia -> ON tiene que quedar
    señalado como cambio de tipo de riesgo, no escondido bajo "distinto emisor".
    """
    return {
        "bono_soberano": "soberano",
        "bono_subsoberano": "subsoberano",
    }.get(fila["clase_activo"], "corporativo")


def preparar_universo(alertas):
    """Universo del motor de swaps: segmentacion compartida, sin deduplicar."""
    # dedup=False: los swaps de perfil (tipo B) rotan justamente entre especies
    # de la misma emision (MEP -> Cable, ej. TLCWO -> TLCMO). Deduplicar las
    # mataria.
    df, descartados = segmentos.cargar_universo(
        alertas, dedup=False, alerta_sin_segmento=False, devolver_descartados=True
    )

    if len(descartados):
        por_clase = descartados["clase_activo"].fillna("sin clasificar").value_counts()
        detalle = ", ".join(f"{c}={n}" for c, n in por_clase.items())
        alertas.append(
            f"{len(descartados)} tickers quedan fuera del motor por no tener tipo de "
            f"tasa de renta fija ({detalle}). Acciones, CEDEARs, FCI y opciones estan "
            "fuera de alcance por decision de diseño."
        )

    # Clave de "mismo emisor" para los swaps de perfil. Se usa la clave de riesgo
    # del armador (prefijo de ticker, con todo el Tesoro bajo SOBERANO_AR) en vez
    # del nombre del emisor, que solo viene cargado en la mitad de los casos: con
    # el nombre se perdian las rotaciones entre especies de todos los tickers sin
    # underlying. El Bopreal se separa porque lo emite el BCRA, no el Tesoro:
    # meterlo en SOBERANO_AR haria pasar un swap Tesoro -> Central como si no
    # cambiara de emisor.
    df["clave_emisor_swap"] = df["clave_riesgo"].where(df["tipo_tasa"] != "bopreal", "BCRA")

    # Nombre para mostrar: el soberano nunca trae underlying, pero llamarlo
    # "(sin identificar: AL3)" en el reporte no ayuda a nadie.
    sin_nombre = ~df["emisor_identificado"]
    df.loc[sin_nombre & (df["clave_emisor_swap"] == "SOBERANO_AR"), "emisor"] = "Gobierno Argentino"
    df.loc[sin_nombre & (df["clave_emisor_swap"] == "BCRA"), "emisor"] = "BCRA"
    return df


def anotar_frecuencia_cupon(df, cashflow, hoy, alertas):
    """Agrega frec_cupon (etiqueta) y frec_meses (para ordenar)."""
    frec = cupones.frecuencia_pagos(cashflow, hoy)
    if frec is None:
        df["frec_cupon"] = None
        df["frec_meses"] = cupones.MESES_DESCONOCIDO
        alertas.append(
            "Sin cashflow disponible: no se puede informar ni filtrar por frecuencia "
            "de cobro de cupones."
        )
        return df
    raices = df["ticker"].map(cupones.raiz_ticker)
    df["frec_cupon"] = raices.map(lambda r: frec.get(r, (None, None))[0])
    df["frec_meses"] = raices.map(
        lambda r: frec.get(r, (None, cupones.MESES_DESCONOCIDO))[1]
    ).fillna(cupones.MESES_DESCONOCIDO)
    sin_frec = int(df["frec_cupon"].isna().sum())
    if sin_frec:
        alertas.append(
            f"{sin_frec} de {len(df)} instrumentos sin frecuencia de cupon "
            "(no hay cashflow para su emision): quedan con la columna vacia."
        )
    return df


def parsear_topes(texto, alertas):
    """--tope-distress 'usd_hard=15,tamar=60' -> dict de fracciones.

    Se MERGEA sobre los defaults en vez de reemplazarlos, asi fijar un tope
    nuevo no borra el de usd_hard sin querer. 'segmento=none' quita el tope.
    """
    topes = dict(TOPE_DISTRESS_DEFAULT)
    if not texto:
        return topes
    for parte in texto.split(","):
        if "=" not in parte:
            print(f"ERROR: --tope-distress mal formado en '{parte}'. "
                  "Formato: 'usd_hard=15,tamar=60' (o 'usd_hard=none' para quitarlo)")
            sys.exit(1)
        seg, val = parte.split("=", 1)
        seg, val = seg.strip(), val.strip().lower()
        if seg not in segmentos.MONEDA_SEGMENTO:
            print(f"ERROR: segmento desconocido '{seg}'. "
                  f"Validos: {', '.join(segmentos.MONEDA_SEGMENTO)}")
            sys.exit(1)
        if val in ("none", "sin", ""):
            topes.pop(seg, None)
            continue
        try:
            topes[seg] = float(val) / 100.0
        except ValueError:
            print(f"ERROR: '{val}' no es un porcentaje valido en --tope-distress.")
            sys.exit(1)
    return topes


def parsear_escenarios(texto):
    """'-500,-100,0,100' (bps) -> [-0.05, -0.01, 0.0, 0.01]."""
    try:
        return [float(x.strip()) / 10000.0 for x in texto.split(",") if x.strip()]
    except ValueError:
        print(f"ERROR: --escenarios-tir mal formado: '{texto}'. Formato: '-500,-200,0,100' (bps)")
        sys.exit(1)


def cargar_cartera(ruta, universo, alertas):
    cartera = pd.read_csv(ruta, encoding="utf-8-sig", dtype=str)
    if "ticker" not in cartera.columns:
        print(f"ERROR: {ruta} no tiene columna 'ticker'.")
        sys.exit(1)
    cartera["ticker"] = cartera["ticker"].str.strip()
    en_universo = cartera["ticker"].isin(set(universo["ticker"]))
    for t in cartera.loc[~en_universo, "ticker"]:
        alertas.append(
            f"Ticker de cartera '{t}' no esta en el universo consolidado "
            "(¿falta cargar su categoria en data/raw/?). Se saltea."
        )
    cartera = cartera[en_universo].copy()
    if "monto" in cartera.columns:
        cartera["monto"] = pd.to_numeric(cartera["monto"], errors="coerce")
    return cartera


def tabla_spread_legislacion(universo, alertas):
    """Premio por legislacion: cuanto mas rinde un Ley Argentina que un bono de
    ley extranjera del MISMO EMISOR y duration comparable.

    La restriccion a mismo emisor es lo que hace que el numero signifique algo.
    Comparar una ON en distress al 55% contra un Global al 5% da un spread de
    5.000 bps que no es premio por ley: es riesgo de credito. Solo cuando el
    deudor es el mismo (AL30 contra GD30, los dos del Tesoro) y el plazo es
    parecido, lo unico que queda variando es la legislacion.

    Sirve como vara para leer los swaps que cambian de ley: si una rotacion
    resigna 138 bps por pasar a Ley N.Y. y la mediana de la curva es 86 bps,
    esa mejora de ley se esta pagando cara. Sin esta referencia, el numero
    suelto no dice nada.
    """
    op = segmentos.filtrar_operables(universo)
    op = op[op["duration_aprox"].notna()]
    arg = op[op["law"] == LEY_LOCAL]
    ny = op[op["law"].isin(LEYES_EXTRANJERAS)]
    filas = []
    for _, a in arg.iterrows():
        pares = ny[
            (ny["segmento"] == a["segmento"])
            & (ny["clave_emisor_swap"] == a["clave_emisor_swap"])
            & ((ny["duration_aprox"] - a["duration_aprox"]).abs() <= TOL_DURATION_LEY)
        ]
        if not len(pares):
            continue
        # El par mas comparable es el de duration mas parecida.
        d = pares.iloc[(pares["duration_aprox"] - a["duration_aprox"]).abs().argsort().iloc[0]]
        filas.append({
            "Segmento": segmentos.DESC_SEGMENTO[a["segmento"]],
            "Emisor": a["emisor"],
            "Ley ARG": a["ticker"], "Rinde ARG": a["rendimiento"],
            "Ley extranjera": d["ticker"], "Ley (cual)": d["law"],
            "Rinde extranjera": d["rendimiento"],
            "Duration (local/extranjera)": f"{a['duration_aprox']:.2f} / {d['duration_aprox']:.2f}",
            "Premio por ley ARG (bps)": round((a["rendimiento"] - d["rendimiento"]) * 10000),
        })
    if not filas:
        alertas.append(
            "No se pudo armar la tabla de premio por legislacion: no hay pares "
            "ley local / ley extranjera del mismo emisor y duration comparable con la ley "
            "cargada en data/condiciones_estaticas.csv."
        )
        return None, {}
    tabla = pd.DataFrame(filas).sort_values(["Segmento", "Premio por ley ARG (bps)"],
                                            ascending=[True, False])
    medianas = tabla.groupby("Segmento")["Premio por ley ARG (bps)"].median().to_dict()
    return tabla, medianas


def evaluar_par(origen, destino, params):
    """Evalua un par origen->destino. Devuelve dict de oportunidad o None."""
    d_rend = destino["rendimiento"] - origen["rendimiento"]

    d_dur = None
    if pd.notna(origen["duration_aprox"]) and pd.notna(destino["duration_aprox"]):
        d_dur = destino["duration_aprox"] - origen["duration_aprox"]
        if d_dur > params.max_mas_duration:
            return None  # estira demasiado la duration

    mismo_emisor = origen["clave_emisor_swap"] == destino["clave_emisor_swap"]
    pasa_a_cable = (
        str(origen.get("couponCurrency")) in ("MEP", "ARS")
        and str(destino.get("couponCurrency")) == "CCL"
    )
    mejora_ley = str(origen.get("law")) == LEY_LOCAL and es_extranjera(destino.get("law"))
    empeora_ley = es_extranjera(origen.get("law")) and str(destino.get("law")) == LEY_LOCAL
    # Volumen en NOMINALES operados, no en plata: el volumen crudo viene en la
    # moneda de cotizacion de cada especie, asi que rotar de una especie en
    # dolares a una en pesos marcaba "mucho mas volumen" por el tipo de cambio
    # y no porque el destino fuera mas liquido.
    vol_o, vol_d = origen.get("volumen_usd"), destino.get("volumen_usd")
    mejora_volumen = (
        pd.notna(vol_d) and vol_d > 0
        and (pd.isna(vol_o) or vol_o <= 0 or vol_d >= params.factor_volumen * vol_o)
    )

    # Tipo A: mejora de rendimiento franca
    if d_rend >= params.min_dtir:
        tipo = "A - mejora rendimiento"
    # Tipo B: mismo emisor, rendimiento neutro, mejora de perfil
    elif (
        mismo_emisor
        and d_rend >= params.umbral_neutro
        and (pasa_a_cable or mejora_ley or mejora_volumen)
    ):
        tipo = "B - mejora de perfil"
    else:
        return None

    # Costo real de rotar: arancel de las dos patas MAS el spread bid/ask que se
    # paga al vender contra el bid y comprar contra el ask. Contar solo el
    # arancel subestimaba el payback cerca de un 60% con los spreads actuales.
    spread_o, spread_d = origen.get("spread_pct"), destino.get("spread_pct")
    costo = mercado.costo_rotacion(params.arancel, spread_o, spread_d)
    payback_meses = round(costo / d_rend * 12, 1) if d_rend > 0 else None

    # Premio por legislacion: solo tiene sentido informarlo cuando la ley
    # efectivamente cambia. Positivo = se resigna tasa para ganar Ley N.Y.
    spread_ley_bps, spread_ley_vs_mediana = None, None
    if mejora_ley or empeora_ley:
        spread_ley_bps = round((origen["rendimiento"] - destino["rendimiento"]) * 10000)
        mediana = params._mediana_ley.get(segmentos.DESC_SEGMENTO[origen["segmento"]])
        if mediana is not None:
            referencia = mediana if mejora_ley else -mediana
            spread_ley_vs_mediana = round(spread_ley_bps - referencia)

    cat_o, cat_d = categoria_credito(origen), categoria_credito(destino)
    if mismo_emisor:
        riesgo = "mismo emisor — mismo riesgo crediticio"
    elif cat_o != cat_d:
        riesgo = f"cambia riesgo {cat_o} → {cat_d} — verificar"
    else:
        riesgo = f"distinto emisor ({cat_d}) — verificar calidad crediticia"
    # Cuando las dos calificaciones estan cargadas, el salto de rating se dice
    # explicito: es el dato mas directo para juzgar si el swap sube el riesgo.
    cal_o, cal_d = origen.get("calificacion"), destino.get("calificacion")
    if not mismo_emisor and pd.notna(cal_o) and pd.notna(cal_d) and str(cal_o) != str(cal_d):
        riesgo += f" [{cal_o} → {cal_d}]"
    if empeora_ley:
        riesgo += " | ATENCION: pasa de Ley N.Y. a Ley Argentina"

    # Cupon proximo del bono que se vende. No bloquea el swap: informa cuanto
    # se resigna por salir antes del pago, para poder decidir si conviene
    # esperar al cobro y recien despues rotar.
    cupon_nota, cupon_dias, cupon_pct = None, None, None
    prox = cupones.proximo_cupon(getattr(params, "_flujos", None), origen["ticker"], params._hoy)
    if prox and prox["pct_interes"] > 0:
        cupon_dias = prox["dias"]
        cupon_pct = prox["pct_interes"]
        if cupon_dias <= params.dias_cupon:
            cupon_nota = (
                f"paga cupon en {cupon_dias} dias ({prox['fecha']:%d/%m/%Y}): "
                f"se resigna {cupon_pct:.2%} del capital invertido. Conviene esperar al cobro."
            )

    return {
        "tipo": tipo,
        "origen": origen["ticker"], "emisor_origen": origen["emisor"],
        "rend_origen": origen["rendimiento"], "dur_origen": origen["duration_aprox"],
        "moneda_origen": origen.get("couponCurrency"), "ley_origen": origen.get("law"),
        "frec_origen": origen.get("frec_cupon"),
        "destino": destino["ticker"], "emisor_destino": destino["emisor"],
        "rend_destino": destino["rendimiento"], "dur_destino": destino["duration_aprox"],
        "moneda_destino": destino.get("couponCurrency"), "ley_destino": destino.get("law"),
        "frec_destino": destino.get("frec_cupon"),
        "frec_meses": destino.get("frec_meses", cupones.MESES_DESCONOCIDO),
        "calif_origen": cal_o, "calif_destino": cal_d,
        "lamina_origen": origen.get("lamina"), "lamina_destino": destino.get("lamina"),
        "d_rend_pp": round(d_rend * 100, 2),
        "d_duration": round(d_dur, 2) if d_dur is not None else None,
        "mismo_emisor": mismo_emisor, "pasa_a_cable": pasa_a_cable,
        "mejora_ley": mejora_ley, "empeora_ley": empeora_ley,
        "mejora_volumen": mejora_volumen,
        "spread_ley_bps": spread_ley_bps,
        "spread_ley_vs_mediana": spread_ley_vs_mediana,
        "vol_origen": vol_o, "vol_destino": vol_d,
        "costo_rotacion_pct": round(costo * 100, 2),
        "spread_origen": spread_o, "spread_destino": spread_d,
        "payback_comision_meses": payback_meses,
        "riesgo_nota": riesgo,
        "posible_distress": bool(destino.get("_distress", False)),
        "cupon_nota": cupon_nota,
        "cupon_dias": cupon_dias,
        "cupon_pct": cupon_pct,
        "segmento": origen["segmento"],
    }


def _orden_destinos(r):
    """Mejor rendimiento primero; entre destinos parejos, el que paga mas seguido.

    La banda de 0.5pp es la misma con la que la mesa evalua si una diferencia de
    tasa justifica mover: por debajo de eso el rendimiento no decide, y ahi si
    conviene quedarse con el que ordena mejor el calendario de cobros.
    """
    banda = -math.floor(r["d_rend_pp"] / BANDA_RENDIMIENTO_PP)
    return (banda, r["frec_meses"], -r["d_rend_pp"])


def detectar(universo, origenes, params, alertas):
    oportunidades = []
    destinos_ok = segmentos.filtrar_operables(universo).copy()

    # Piso de rendimiento: no se propone rotar hacia una TIR negativa (o bajo
    # el piso que fije el usuario). Mismo criterio y unidad que el armador:
    # el piso se aplica en la unidad propia de cada segmento.
    antes = len(destinos_ok)
    destinos_ok = destinos_ok[destinos_ok["rendimiento"] > params.min_rend / 100.0]
    if len(destinos_ok) < antes:
        alertas.append(
            f"--min-rend {params.min_rend:g}: {antes - len(destinos_ok)} instrumentos "
            "quedan excluidos como destino por rendimiento bajo el piso."
        )

    # Piso de liquidez POR SEGMENTO, sobre el volumen operado en USD (la misma
    # formula del armador). Un destino sin volumen no se puede ejecutar y su
    # rendimiento suele ser un precio viejo, no una oportunidad. Solo filtra
    # destinos: una posicion iliquida del cliente se analiza igual como origen.
    if 0 < params.percentil_liquidez < 100 and destinos_ok["volumen_usd"].notna().any():
        excluidos, chicos = {}, []
        for seg, grupo in destinos_ok.groupby("segmento"):
            if len(grupo) < MIN_OPERABLES_PERCENTIL:
                chicos.append(f"{seg} ({len(grupo)})")
                continue  # con pocos candidatos el percentil no dice nada
            piso = grupo["volumen_usd"].quantile(params.percentil_liquidez / 100.0)
            fuera = grupo[grupo["volumen_usd"].fillna(0) < piso]
            if len(fuera):
                excluidos[seg] = len(fuera)
                destinos_ok = destinos_ok.drop(fuera.index)
        if excluidos:
            detalle = ", ".join(f"{s}: {n}" for s, n in sorted(excluidos.items()))
            alertas.append(
                f"--percentil-liquidez {params.percentil_liquidez:g}: destinos excluidos "
                f"por volumen operado bajo el piso de su segmento ({detalle})."
            )
        if chicos:
            alertas.append(
                f"Segmentos con menos de {MIN_OPERABLES_PERCENTIL} candidatos, donde el "
                f"percentil de liquidez no aplica ({', '.join(sorted(chicos))}): revisar "
                "a mano el volumen del destino antes de operar."
            )

    if params.frecuencia_cupon:
        antes = len(destinos_ok)
        destinos_ok = destinos_ok[destinos_ok["frec_cupon"] == params.frecuencia_cupon]
        alertas.append(
            f"--frecuencia-cupon {params.frecuencia_cupon}: de {antes} destinos posibles "
            f"quedan {len(destinos_ok)} que pagan renta con esa frecuencia."
        )

    # Marcador informativo de distress, relativo al nivel de tasas de cada
    # segmento. No descarta nada: señala.
    destinos_ok["_distress"] = False
    if 0 < params.percentil_distress < 100:
        for seg, grupo in destinos_ok.groupby("segmento"):
            if len(grupo) < MIN_OPERABLES_PERCENTIL:
                continue
            umbral = grupo["rendimiento"].quantile(params.percentil_distress / 100.0)
            destinos_ok.loc[grupo.index, "_distress"] = grupo["rendimiento"] > umbral

    sin_tope = set()
    for _, origen in origenes.iterrows():
        if pd.isna(origen["rendimiento"]):
            alertas.append(f"{origen['ticker']}: sin rendimiento parseable, se saltea como origen.")
            continue
        candidatos = destinos_ok[
            (destinos_ok["segmento"] == origen["segmento"])
            & (destinos_ok["ticker"] != origen["ticker"])
        ]
        tope = params.max_rend_destino if params.max_rend_destino is not None \
            else params._topes.get(origen["segmento"])
        if tope is not None:
            candidatos = candidatos[candidatos["rendimiento"] <= tope]
        else:
            sin_tope.add(origen["segmento"])
        filas = []
        for _, destino in candidatos.iterrows():
            r = evaluar_par(origen, destino, params)
            if r:
                filas.append(r)
        # top_n POR TIPO: las ideas de perfil (B, mismo emisor) no compiten por
        # cupo con las de rendimiento (A) — son propuestas distintas.
        for tipo in ("A - mejora rendimiento", "B - mejora de perfil"):
            del_tipo = [f for f in filas if f["tipo"] == tipo]
            del_tipo.sort(key=_orden_destinos)
            oportunidades.extend(del_tipo[: params.top_n])

    if sin_tope:
        alertas.append(
            f"Segmentos sin tope anti-distress: {', '.join(sorted(sin_tope))}. "
            "Los destinos que rindan muy por encima de sus pares entran igual, marcados "
            "como 'posible distress'. Para excluirlos, fijar el numero con "
            "--tope-distress (ej: --tope-distress \"tamar=60\")."
        )
    return oportunidades


def hoja_sensibilidad(df_op, universo, cashflow, params, alertas):
    """Cuanto se movería el precio de cada instrumento propuesto si su TIR
    comprime o se abre. Repricing completo del cashflow, no aproximacion."""
    if not len(df_op):
        return None
    roles = {}
    for _, r in df_op.iterrows():
        roles.setdefault(r["origen"], set()).add("SALE")
        roles.setdefault(r["destino"], set()).add("ENTRA")

    idx = universo.set_index("ticker")
    filas, sin_datos = [], 0
    for ticker, rol in roles.items():
        if ticker not in idx.index:
            continue
        act = idx.loc[ticker]
        if isinstance(act, pd.DataFrame):
            act = act.iloc[0]
        r = cupones.retorno_por_tir(
            cashflow, ticker, act["rendimiento"], params._escenarios, params._hoy
        )
        if r is None:
            sin_datos += 1
            continue
        fila = {
            "Ticker": ticker,
            "Rol": " / ".join(sorted(rol)),
            "Segmento": segmentos.DESC_SEGMENTO[act["segmento"]],
            "TIR actual": act["rendimiento"],
            "Duration (años)": round(act["duration_aprox"], 2) if pd.notna(act["duration_aprox"]) else None,
        }
        for d in params._escenarios:
            fila[f"{d * 10000:+.0f} bps"] = r.get(d)
        filas.append(fila)

    if sin_datos:
        alertas.append(
            f"{sin_datos} instrumentos propuestos sin cashflow o sin TIR: quedan fuera "
            "de la hoja de sensibilidad (no se estima un precio sin sus flujos)."
        )
    if not filas:
        return None
    return pd.DataFrame(filas).sort_values(["Segmento", "TIR actual"], ascending=[True, False])


def exportar_excel(df_op, params, ruta_out, sens, spread_ley):
    """Arma el Excel de salida orientado a lectura rapida:

    - "Oportunidades": una fila por swap, con bloque SALE (lo que rinde mal),
      bloque ENTRA (lo que rinde mejor) y una frase-resumen tipo mesa.
    - "Sensibilidad": upside de cada instrumento si la TIR se mueve.
    - "Premio por legislacion": vara para leer los swaps que cambian de ley.
    - "Leyenda": diccionario de cada columna.
    - "Detalle tecnico": columnas crudas para filtrar/auditar.
    - "Parametros": umbrales usados en la corrida.
    """
    def beneficios(r):
        partes = []
        if r["mismo_emisor"]:
            partes.append("mismo emisor")
        if r["pasa_a_cable"]:
            partes.append("pasa a cobrar en Cable")
        if r["mejora_ley"]:
            partes.append("pasa a Ley NY")
        if r["mejora_volumen"]:
            partes.append("mucho más volumen")
        return ", ".join(partes)

    def frase(r):
        base = (f"Rotar {r['origen']} (rinde {r['rend_origen']:.1%}) hacia "
                f"{r['destino']} (rinde {r['rend_destino']:.1%})")
        extra = beneficios(r)
        payback = (f"; cuesta {r['costo_rotacion_pct']:.2f}% y lo recuperás en "
                   f"{r['payback_comision_meses']:.1f} meses"
                   if pd.notna(r["payback_comision_meses"]) else "")
        return base + (f" — {extra}" if extra else "") + payback

    claro = pd.DataFrame({
        "Idea del swap": df_op.apply(frase, axis=1),
        "SALE - Ticker": df_op["origen"],
        "SALE - Emisor": df_op["emisor_origen"],
        "SALE - Rinde": df_op["rend_origen"],
        "SALE - Duration (años)": df_op["dur_origen"].round(1),
        "SALE - Cobra en": df_op["moneda_origen"],
        "SALE - Ley": df_op["ley_origen"],
        "SALE - Calificación": df_op["calif_origen"],
        "SALE - Lámina mínima": df_op["lamina_origen"],
        "SALE - Paga renta": df_op["frec_origen"],
        "ENTRA - Ticker": df_op["destino"],
        "ENTRA - Emisor": df_op["emisor_destino"],
        "ENTRA - Rinde": df_op["rend_destino"],
        "ENTRA - Duration (años)": df_op["dur_destino"].round(1),
        "ENTRA - Cobra en": df_op["moneda_destino"],
        "ENTRA - Ley": df_op["ley_destino"],
        "ENTRA - Calificación": df_op["calif_destino"],
        "ENTRA - Lámina mínima": df_op["lamina_destino"],
        "ENTRA - Paga renta": df_op["frec_destino"],
        "Gana rendimiento (pp)": df_op["d_rend_pp"],
        "Estira duration (años)": df_op["d_duration"],
        "Costo de rotar (%)": df_op["costo_rotacion_pct"],
        "Recupera el costo en (meses)": df_op["payback_comision_meses"],
        "SALE - Spread bid/ask": df_op["spread_origen"],
        "ENTRA - Spread bid/ask": df_op["spread_destino"],
        "Premio por ley que resigna (bps)": df_op["spread_ley_bps"],
        "vs. mediana de la curva (bps)": df_op["spread_ley_vs_mediana"],
        "Beneficios extra": df_op.apply(beneficios, axis=1),
        "Riesgo a verificar": df_op["riesgo_nota"],
        "Posible distress": df_op["posible_distress"].map({True: "sí", False: ""}),
        "Cupón próximo (aviso)": df_op["cupon_nota"],
        "SALE - Días al cupón": df_op["cupon_dias"],
        "SALE - Cupón que resigna": df_op["cupon_pct"],
        "Tipo": df_op["tipo"],
    }).sort_values(["SALE - Ticker", "Gana rendimiento (pp)"],
                   ascending=[True, False])

    leyenda = pd.DataFrame([
        ("Idea del swap", "La propuesta en una frase, como la publica la mesa."),
        ("SALE - ...", "El instrumento que RINDE MAL y conviene vender: su rendimiento actual (TIR anual; TNA en tasa fija en pesos), duration, en qué moneda paga cupones (MEP/CCL=Cable/ARS) y bajo qué ley está emitido."),
        ("ENTRA - ...", "El instrumento que PUEDE RENDIR MEJOR y se propone comprar, con los mismos datos para comparar lado a lado."),
        ("... - Paga renta", "Cada cuánto cobra cupón de interés: mensual, bimestral, trimestral, semestral, anual, o 'al vencimiento' cuando le queda un solo cobro. Se mide sobre los pagos FUTUROS (lo que efectivamente cobra quien compra hoy). Vacío = no hay cashflow para esa emisión."),
        ("Gana rendimiento (pp)", "Cuántos puntos porcentuales MÁS rinde el que entra vs. el que sale. +8.2 = el nuevo rinde 8,2 puntos más por año."),
        ("Estira duration (años)", "Cuánto se alarga (+) o acorta (-) el plazo/sensibilidad de la posición con el cambio. Vacío si alguno no tiene duration."),
        ("Costo de rotar (%)", "Lo que cuesta la rotación completa: las 2 patas de arancel MÁS el spread bid/ask que se paga al vender contra el bid y comprar contra el ask (media punta en cada pata). Si falta el spread de alguna punta, el número es un piso, no el costo completo."),
        ("Recupera el costo en (meses)", "En cuántos meses la mejora de rendimiento paga ese costo total. Menos meses = swap más obvio."),
        ("... - Calificación", "Calificación crediticia de la emisión, de data/condiciones_estaticas.csv. Cuando el swap cambia de emisor y las dos están cargadas, el salto de rating aparece también en 'Riesgo a verificar'. Vacío = no cargada; la herramienta no la estima."),
        ("... - Lámina mínima", "Valor nominal mínimo operable. El monto de la propuesta NO está ajustado a lámina: verificar al operar que la posición sea múltiplo de este número."),
        ("... - Spread bid/ask", "Distancia entre la punta compradora y la vendedora, sobre el punto medio. Es liquidez directa: cuánto cuesta entrar y salir. Un spread ancho encarece la rotación y avisa que el papel se opera poco. Fuente: data912 (API pública). Vacío = no hay dos puntas vivas para ese ticker."),
        ("Premio por ley que resigna (bps)", "Solo aparece cuando el swap CAMBIA de legislación. Positivo = cuánta tasa se resigna por pasar de Ley Argentina a Ley N.Y. Negativo = se gana tasa Y mejor ley (swap redondo). En un cambio N.Y. -> Argentina el signo se lee al revés: es lo que se cobra por aceptar ley local."),
        ("vs. mediana de la curva (bps)", "Ese premio comparado con lo que paga hoy el resto del segmento (hoja 'Premio por legislacion'). Positivo = estás pagando la ley MÁS CARO que el mercado. Negativo = la estás comprando barata."),
        ("Beneficios extra", "Mejoras además del rendimiento: mismo emisor (sin cambio de riesgo), pasa a cobrar en Cable, pasa a Ley NY, o mucho más volumen (más fácil comprar/vender)."),
        ("Riesgo a verificar", "'mismo emisor' = swap limpio. Cualquier otra nota = falta TU análisis crediticio antes de proponerlo. Distingue soberano / subsoberano (provincias) / corporativo: cambiar de categoría cambia el tipo de riesgo, no solo el nombre del deudor. Avisa también si el destino baja de Ley N.Y. a Ley Argentina."),
        ("Posible distress", "El destino queda en la cola alta de rendimiento de su propio segmento (por encima del percentil configurado). Una tasa muy alta contra sus pares no suele ser una oportunidad: es el mercado pidiendo prima porque duda del cobro. NO se descarta el swap, se señala. Ver 'Tope anti-distress' en Parametros."),
        ("Cupón próximo (aviso)", "Aparece cuando el bono que SALE cobra cupón pronto. Vender antes del pago resigna ese cobro: compará el % que se resigna contra la mejora de rendimiento antes de rotar. El swap no se descarta, se señala."),
        ("SALE - Días al cupón / Cupón que resigna", "Días hasta el próximo cupón del bono a vender y cuánto representa ese cupón sobre el capital invertido hoy. Vacío = no hay cashflow para ese ticker o no quedan cupones."),
        ("Tipo", "A = gana rendimiento a duration similar. B = mismo rendimiento pero mejor perfil (moneda/ley/liquidez), siempre dentro del mismo emisor."),
        ("", ""),
        ("Hoja Sensibilidad", "Cuánto se movería el precio de cada instrumento propuesto si SU TIR comprimiera o se abriera (en bps). Se recalcula descontando todos los flujos contractuales a la tasa nueva, no por aproximación de duration. Es un movimiento instantáneo de precio: no incluye el cupón que se cobra en el camino."),
        ("Hoja Premio por legislacion", "Cuánto más rinde hoy un Ley Argentina que un Ley N.Y. de duration comparable, dentro del mismo segmento. Es la vara para saber si una mejora de ley se está pagando cara o barata."),
        ("", ""),
        ("Nota", "Los rendimientos están en formato porcentaje. El motor PROPONE con datos duros: la decisión final, el riesgo crediticio y el costo del canje MEP/Cable del día los evaluás vos."),
    ], columns=["Columna", "Qué significa"])

    # Solo los parametros de la corrida: los atributos internos (cashflow,
    # flujos) son estructuras de datos, no configuracion, y volcarlos aca
    # llenaba una celda con el dump entero de un DataFrame.
    visibles = [(k, str(v)) for k, v in vars(params).items() if not k.startswith("_")]
    visibles.append((
        "tope_distress_efectivo",
        ", ".join(f"{s}={v:.1%}" for s, v in sorted(params._topes.items())) or "(ninguno)",
    ))
    visibles.append((
        "escenarios_tir_bps",
        ", ".join(f"{d * 10000:+.0f}" for d in params._escenarios),
    ))
    parametros = pd.DataFrame(visibles, columns=["parametro", "valor"])

    with pd.ExcelWriter(ruta_out, engine="openpyxl") as writer:
        claro.to_excel(writer, sheet_name="Oportunidades", index=False)
        if sens is not None:
            sens.to_excel(writer, sheet_name="Sensibilidad", index=False)
        if spread_ley is not None:
            spread_ley.to_excel(writer, sheet_name="Premio por legislacion", index=False)
        leyenda.to_excel(writer, sheet_name="Leyenda", index=False)
        df_op.to_excel(writer, sheet_name="Detalle tecnico", index=False)
        parametros.to_excel(writer, sheet_name="Parametros", index=False)

        # Formato: porcentajes legibles, anchos de columna y primera fila fija
        ws = writer.sheets["Oportunidades"]
        ws.freeze_panes = "B2"
        for idx, col in enumerate(claro.columns, start=1):
            letra = ws.cell(row=1, column=idx).column_letter
            if col in ("SALE - Rinde", "ENTRA - Rinde", "SALE - Cupón que resigna",
                       "SALE - Spread bid/ask", "ENTRA - Spread bid/ask"):
                for celda in ws[letra][1:]:
                    celda.number_format = "0.00%"
            ancho = 60 if col == "Idea del swap" else max(12, len(col) + 2)
            ws.column_dimensions[letra].width = ancho
        if sens is not None:
            ws3 = writer.sheets["Sensibilidad"]
            ws3.freeze_panes = "B2"
            for idx, col in enumerate(sens.columns, start=1):
                letra = ws3.cell(row=1, column=idx).column_letter
                if col == "TIR actual" or col.endswith("bps"):
                    for celda in ws3[letra][1:]:
                        celda.number_format = "0.00%"
                ws3.column_dimensions[letra].width = max(12, len(col) + 2)
        if spread_ley is not None:
            ws4 = writer.sheets["Premio por legislacion"]
            for idx, col in enumerate(spread_ley.columns, start=1):
                letra = ws4.cell(row=1, column=idx).column_letter
                if col.startswith("Rinde"):
                    for celda in ws4[letra][1:]:
                        celda.number_format = "0.00%"
                ws4.column_dimensions[letra].width = max(14, len(col) + 2)
        writer.sheets["Leyenda"].column_dimensions["A"].width = 32
        writer.sheets["Leyenda"].column_dimensions["B"].width = 110
        writer.sheets["Parametros"].column_dimensions["A"].width = 26
        writer.sheets["Parametros"].column_dimensions["B"].width = 60


def main():
    ap = argparse.ArgumentParser(description="Motor de deteccion de swaps")
    ap.add_argument("--min-dtir", type=float, default=0.5,
                    help="Mejora minima de rendimiento en puntos porcentuales (default 0.5)")
    ap.add_argument("--max-mas-duration", type=float, default=1.5,
                    help="Maximo estiramiento de duration en años (default 1.5)")
    ap.add_argument("--umbral-origen", type=float, default=0.0,
                    help="TIR (en %%) bajo la cual un instrumento es 'origen' (default 0 = negativa)")
    ap.add_argument("--umbral-neutro", type=float, default=-0.3,
                    help="Perdida max de rendimiento (pp) tolerada en swaps de perfil (default -0.3)")
    ap.add_argument("--arancel", type=float, default=0.75,
                    help="Arancel por pata en %% (default 0.75)")
    ap.add_argument("--factor-volumen", type=float, default=3.0,
                    help="Veces de volumen extra para contar 'mejora de volumen' (default 3)")
    ap.add_argument("--max-rend-destino", type=float, default=None,
                    help="Tope de rendimiento (%%) para TODOS los destinos. Anula los topes "
                         "por segmento de --tope-distress")
    ap.add_argument("--tope-distress", default=None,
                    help="Tope de rendimiento por segmento, ej: 'usd_hard=15,tamar=60'. "
                         "Los destinos por encima se excluyen por sospecha de distress. "
                         "Se suma a los defaults (usd_hard=15%%); usar 'usd_hard=none' para quitarlo")
    ap.add_argument("--percentil-distress", type=float, default=PERCENTIL_DISTRESS_DEFAULT,
                    help="Marca como 'posible distress' al destino que queda por encima de este "
                         f"percentil de rendimiento de su segmento (default {PERCENTIL_DISTRESS_DEFAULT}; "
                         "0 o 100 lo desactivan). Solo señala, no descarta")
    ap.add_argument("--percentil-liquidez", type=float, default=25.0,
                    help="Excluye como destino a los instrumentos bajo este percentil de "
                         "volumen operado (en USD) dentro de su segmento (default 25, el "
                         "mismo del perfil moderado del armador; 0 lo desactiva). Un destino "
                         "sin volumen no tiene contraparte para ejecutar el swap y su TIR "
                         "suele ser precio viejo. Solo filtra destinos, nunca origenes")
    ap.add_argument("--min-rend", type=float, default=0.0,
                    help="Rendimiento minimo en %% para proponer un destino (default: 0), "
                         "en la unidad de cada segmento — mismo criterio que el armador. "
                         "Evita rotar hacia una TIR negativa")
    ap.add_argument("--frecuencia-cupon", choices=["mensual", "bimestral", "trimestral",
                                                   "semestral", "anual"], default=None,
                    help="Solo propone destinos que paguen renta con esa frecuencia. "
                         "Sin este flag, entre destinos de rendimiento parejo se prioriza "
                         "al que paga mas seguido")
    ap.add_argument("--escenarios-tir", default=ESCENARIOS_TIR_DEFAULT,
                    help=f"Movimientos de TIR en bps para la hoja de sensibilidad "
                         f"(default '{ESCENARIOS_TIR_DEFAULT}')")
    ap.add_argument("--dias-cupon", type=int, default=45,
                    help="Avisa si el bono a vender cobra cupon dentro de estos dias (default: 45). "
                         "No bloquea el swap, solo lo señala")
    ap.add_argument("--top-n", type=int, default=3,
                    help="Maximo de destinos propuestos por origen (default 3)")
    ap.add_argument("--clase", choices=list(CLASES) + ["todas"], default="todas",
                    help="Acota el analisis a una clase de activo, en origen y en destino "
                         "(on = obligaciones negociables corporativas)")
    ap.add_argument("--origen", choices=["tir-baja", "todos"], default="tir-baja")
    ap.add_argument("--cartera", default=None,
                    help="CSV de tenencias (columna ticker; opcional monto). "
                         "Si existe data/cartera.csv se usa solo, salvo --sin-cartera.")
    ap.add_argument("--sin-cartera", action="store_true",
                    help="Ignorar data/cartera.csv aunque exista")
    ap.add_argument("--sin-spread", action="store_true",
                    help="No consultar las puntas bid/ask de data912. El costo de rotar "
                         "queda calculado solo sobre el arancel (subestimado)")
    params = ap.parse_args()
    # Umbrales expresados en pp -> fracciones
    params.min_dtir /= 100.0
    params.umbral_neutro /= 100.0
    params.umbral_origen /= 100.0
    params.arancel /= 100.0
    if params.max_rend_destino is not None:
        params.max_rend_destino /= 100.0

    alertas = []
    params._topes = parsear_topes(params.tope_distress, alertas)
    params._escenarios = parsear_escenarios(params.escenarios_tir)
    universo = preparar_universo(alertas)

    # Cupones: si el cashflow no esta, el motor sigue proponiendo swaps sin el
    # chequeo de cupon proximo ni frecuencia, en vez de cortar.
    params._hoy = pd.Timestamp.now().normalize()
    cashflow = cupones.cargar_cashflow(alertas)
    params._cashflow = cashflow
    params._flujos = cupones.flujos_por_peso(universo, cashflow, params._hoy, alertas)
    universo = anotar_frecuencia_cupon(universo, cashflow, params._hoy, alertas)
    if not params.sin_spread:
        universo = mercado.anotar_puntas(universo, alertas)
    else:
        universo["spread_pct"] = pd.NA

    if params.clase != "todas":
        clase = CLASES[params.clase]
        antes = len(universo)
        universo = universo[universo["clase_activo"] == clase].copy()
        alertas.append(
            f"--clase {params.clase}: de {antes} instrumentos quedan {len(universo)} "
            f"de clase {clase}. Los swaps se buscan solo dentro de esa clase."
        )

    spread_ley, params._mediana_ley = tabla_spread_legislacion(universo, alertas)

    ruta_cartera = params.cartera or (
        CARTERA_DEFAULT if os.path.exists(CARTERA_DEFAULT) and not params.sin_cartera else None
    )
    if ruta_cartera:
        cartera = cargar_cartera(ruta_cartera, universo, alertas)
        origenes = universo[universo["ticker"].isin(set(cartera["ticker"]))]
        modo = f"cartera ({os.path.basename(ruta_cartera)}, {len(origenes)} tenencias en universo)"
    elif params.origen == "todos":
        origenes = universo
        modo = "todo el universo"
    else:
        origenes = universo[universo["rendimiento"] < params.umbral_origen]
        modo = f"rendimiento < {params.umbral_origen:.2%}"

    oportunidades = detectar(universo, origenes, params, alertas)

    # --- Reporte ---
    ahora = datetime.now()
    print("=" * 70)
    print(f"MOTOR DE SWAPS — corrida {ahora:%d/%m/%Y %H:%M}")
    print(f"Origenes analizados: {len(origenes)} ({modo})")
    seg_counts = universo["segmento"].value_counts()
    print("Universo por segmento: "
          + " · ".join(f"{s}={n}" for s, n in seg_counts.items()))
    print("=" * 70)

    if not oportunidades:
        print(
            "\nSin oportunidades con los umbrales actuales "
            f"(min Δrend {params.min_dtir:.2%}, max +duration {params.max_mas_duration} años).\n"
            "Proba relajar umbrales (--min-dtir, --max-mas-duration) o --origen todos."
        )
    else:
        df_op = pd.DataFrame(oportunidades)
        for origen_t, grupo in df_op.groupby("origen", sort=False):
            o = grupo.iloc[0]
            print(f"\n♻ {origen_t} (rend {o.rend_origen:.2%}, dur {o.dur_origen:.1f} años, "
                  f"{o.moneda_origen or 's/d'}) — {len(grupo)} alternativa(s):")
            if o.cupon_nota:
                print(f"   ⚠ {origen_t} {o.cupon_nota}")
            for _, r in grupo.iterrows():
                extras = [e for e, v in [
                    ("→Cable", r.pasa_a_cable), ("→Ley NY", r.mejora_ley),
                    ("+volumen", r.mejora_volumen), ("mismo emisor", r.mismo_emisor),
                ] if v]
                if r.frec_destino:
                    extras.append(f"paga {r.frec_destino}")
                payback = (f", cuesta {r.costo_rotacion_pct:.2f}% y se recupera en "
                           f"{r.payback_comision_meses} meses"
                           if pd.notna(r.payback_comision_meses) else "")
                print(f"   → {r.destino} ({r.emisor_destino}): rend {r.rend_destino:.2%} "
                      f"(Δ{r.d_rend_pp:+.2f}pp), dur {r.dur_destino:.1f}"
                      f"{payback} [{r.tipo}]"
                      f"{' | ' + ', '.join(extras) if extras else ''}")
                print(f"      riesgo: {r.riesgo_nota}")
                if pd.notna(r.spread_ley_bps):
                    vs = (f", {abs(r.spread_ley_vs_mediana):.0f} bps "
                          f"{'por encima' if r.spread_ley_vs_mediana > 0 else 'por debajo'} de la mediana"
                          if pd.notna(r.spread_ley_vs_mediana) else "")
                    print(f"      premio por ley: {r.spread_ley_bps:+.0f} bps{vs}")
                if r.posible_distress:
                    print("      ⚠ posible distress: rinde muy por encima de la mediana de su segmento")

        sens = hoja_sensibilidad(df_op, universo, cashflow, params, alertas)

        # Excel de salida
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        ruta_out = os.path.join(OUTPUT_DIR, f"swaps_{ahora:%Y-%m-%d}.xlsx")
        exportar_excel(df_op, params, ruta_out, sens, spread_ley)
        segmentos.podar_outputs("swaps_")
        print(f"\nOutput: {ruta_out}")

    if alertas:
        print("\n⚠ ALERTAS:")
        for a in alertas:
            print(f"  ! {a}")


if __name__ == "__main__":
    main()
