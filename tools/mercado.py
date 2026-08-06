#!/usr/bin/env python3
"""
Puntas de mercado (bid/ask) desde data912.

Modulo compartido. No se ejecuta solo.

QUE APORTA
----------
Docta publica precio y volumen, pero no las puntas. Sin puntas, el costo de
rotar queda subestimado: el motor de swaps contaba solo el arancel (2 patas,
~1,5%) e ignoraba que la rotacion tambien paga el spread — se vende contra el
bid y se compra contra el ask, media punta en cada pata. Con un spread mediano
del 0,87% en el mercado local, ese olvido alarga el payback de una rotacion
cerca de un 60%.

data912.com es una API publica de terceros, sin token. No tiene relacion con el
monitor de mesa del usuario, con el que este proyecto NO se conecta.

QUE NO APORTA
-------------
Precios. Se verifico contra el universo: 572 de 576 tickers coinciden con Docta
con menos de 0,1% de diferencia y ninguno difiere mas de 1% — las dos fuentes
leen BYMA. Y donde Docta no publica precio, es porque el instrumento no opera:
de los 145 tickers que solo aparecen aca, apenas 6 registraron operaciones,
contra el 92% de los que Docta ya cubre. Recalcular una TIR sobre un precio que
nadie convalido seria inventar tasa, no medirla.
"""

import json
import urllib.error
import urllib.request

import pandas as pd

BASE_URL = "https://data912.com/live/{}"
# Renta fija unicamente: bonos soberanos/subsoberanos, ONs y letras. Las
# categorias de acciones y CEDEARs de la misma API estan fuera de alcance.
ENDPOINTS = ("arg_bonds", "arg_corp", "arg_notes")

# Relacion ask/bid por encima de la cual las dos puntas no describen un mismo
# mercado. Se observaron casos con bid 125 y ask 127.000: son escalas distintas,
# no un spread.
MAX_RELACION_PUNTAS = 3.0


def cargar_puntas(alertas, timeout=15):
    """Puntas del mercado por ticker.

    Devuelve un DataFrame con ticker, px_bid, px_ask, spread_pct y operaciones,
    o None si la API no responde. Nunca corta la corrida: sin puntas las dos
    herramientas siguen funcionando, con el costo de rotacion calculado solo
    sobre el arancel y avisando que quedo subestimado.
    """
    filas, fallaron = [], []
    for ep in ENDPOINTS:
        try:
            with urllib.request.urlopen(BASE_URL.format(ep), timeout=timeout) as r:
                filas.extend(json.load(r))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            fallaron.append(f"{ep} ({type(e).__name__})")

    if fallaron:
        alertas.append(
            f"No se pudieron traer las puntas de data912 para {', '.join(fallaron)}: "
            "el costo de rotar queda calculado solo sobre el arancel, sin el spread "
            "bid/ask. Es una subestimacion del costo real."
        )
    if not filas:
        return None

    df = pd.DataFrame(filas)
    faltan = [c for c in ("symbol", "px_bid", "px_ask") if c not in df.columns]
    if faltan:
        alertas.append(f"data912 respondio sin las columnas {faltan}: se ignoran las puntas.")
        return None

    df = df.rename(columns={"symbol": "ticker", "q_op": "operaciones"})
    for c in ("px_bid", "px_ask"):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Solo cuentan los mercados con las dos puntas vivas y en la misma escala.
    validas = (
        (df["px_bid"] > 0)
        & (df["px_ask"] > df["px_bid"])
        & (df["px_ask"] / df["px_bid"] < MAX_RELACION_PUNTAS)
    )
    df["spread_pct"] = ((df["px_ask"] - df["px_bid"]) / ((df["px_ask"] + df["px_bid"]) / 2)).where(validas)

    cols = ["ticker", "px_bid", "px_ask", "spread_pct"]
    if "operaciones" in df.columns:
        cols.append("operaciones")
    return df[cols].drop_duplicates(subset="ticker")


def anotar_puntas(universo, alertas, timeout=15):
    """Suma spread_pct al universo. Devuelve el universo (siempre con la columna)."""
    puntas = cargar_puntas(alertas, timeout=timeout)
    if puntas is None:
        universo["spread_pct"] = pd.NA
        return universo

    universo = universo.merge(
        puntas[["ticker", "spread_pct"]], on="ticker", how="left"
    )
    con_spread = int(universo["spread_pct"].notna().sum())
    alertas.append(
        f"Puntas de mercado (data912): spread bid/ask disponible en {con_spread} de "
        f"{len(universo)} instrumentos. Donde falta, el costo de rotar se calcula solo "
        "con el arancel y queda subestimado."
    )
    return universo


def costo_rotacion(arancel, spread_origen, spread_destino):
    """Costo total de una rotacion, como fraccion del capital.

    Dos patas de arancel, mas media punta de spread en cada pata: se vende
    contra el bid y se compra contra el ask, y en cada operacion se resigna la
    mitad del spread respecto del punto medio.

    Los spreads que faltan cuentan como cero — el costo devuelto es entonces un
    piso, no una estimacion completa. La columna de spread deja ver cuando pasa.
    """
    costo = 2.0 * arancel
    for s in (spread_origen, spread_destino):
        if pd.notna(s) and s > 0:
            costo += float(s) / 2.0
    return costo
