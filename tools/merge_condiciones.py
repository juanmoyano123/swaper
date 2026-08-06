#!/usr/bin/env python3
"""
Mergea condiciones de emision de una fuente externa a condiciones_estaticas.csv.

La API de Docta no expone ley, moneda de pago, lamina minima ni calificacion.
Este script toma un CSV con esos datos y los incorpora SIN pisar lo que ya
estaba cargado a mano, salvo --forzar.

QUE SE PROPAGA A LAS TRES ESPECIES
----------------------------------
Ley, moneda de pago, lamina y calificacion son atributos de la EMISION: valen
igual para MR46O, MR46D y MR46C, y por eso se replican en las tres especies.

La moneda de pago no es la especie de liquidacion: es donde paga el bono. Se
verifico sobre el export de 216 ONs, todas especie D (MEP): 160 pagan en MEP y
56 en Cable. Si fuera un atributo de la especie, las 216 serian MEP.

Uso:
    python3 tools/merge_condiciones.py --origen data/condiciones_monitor.csv --dry-run
    python3 tools/merge_condiciones.py --origen data/condiciones_monitor.csv
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import segmentos  # noqa: E402

CONDICIONES = os.path.join(segmentos.BASE_DIR, "data", "condiciones_estaticas.csv")
CONFLICTOS = os.path.join(segmentos.BASE_DIR, "data", "conflictos_condiciones.csv")

# Vocabulario de la fuente -> el del proyecto. Cualquier valor que no este aca
# se reporta y no se carga: es preferible un hueco a un dato mal traducido.
# La fuente solo publica ARG o NY. Cualquier otro codigo se reporta y NO se
# carga: traducirlo seria inventar una categoria que el proyecto no maneja.
MAPA_LEY = {
    "ARG": "Ley Argentina",
    "NY": "Ley N.Y.",
}
# Las unicas dos leyes que la fuente publica. Cualquier otro valor que quede en
# el archivo (de cargas a mano anteriores) se vacia y se manda a revisar: puede
# ser correcto, pero no hay con que confirmarlo y un dato sin respaldo no se usa.
LEYES_VALIDAS = {"Ley Argentina", "Ley N.Y."}

MAPA_MONEDA = {
    "MEP": "MEP",
    "CABLE": "CCL",
    "CCL": "CCL",
    "ARS": "ARS",
    "PESOS": "ARS",
}

# Atributos de la emision: se replican en las tres especies.
POR_EMISION = {"ley": "leg", "moneda_pago": "moneda",
               "lamina": "lamina", "calificacion": "calif"}

COLUMNAS_NUEVAS = ["lamina", "calificacion"]


def expandir_especies(origen, alertas):
    """Una fila por ticker. La fuente trae el mapeo ars/mep/cable de cada emision."""
    filas, sin_traducir = [], set()
    for _, r in origen.iterrows():
        base = {}
        for destino, col in POR_EMISION.items():
            v = r.get(col)
            if pd.isna(v) or str(v).strip() == "":
                continue
            if destino in ("ley", "moneda_pago"):
                mapa = MAPA_LEY if destino == "ley" else MAPA_MONEDA
                clave = str(v).strip().upper()
                if clave not in mapa:
                    sin_traducir.add(f"{destino}={v}")
                    continue
                v = mapa[clave]
            base[destino] = v

        especies = [r.get(c) for c in ("sym_ars", "sym_mep", "sym_cable")]
        especies = [e for e in especies if pd.notna(e) and str(e).strip()]
        if not especies:
            especies = [r["ticker"]]

        for tk in especies:
            fila = dict(base)
            fila["ticker"] = str(tk).strip()
            if len(fila) > 1:  # algo mas que el ticker
                filas.append(fila)

    if sin_traducir:
        alertas.append(
            "Valores que la fuente trae y el proyecto no tiene traducidos "
            f"({', '.join(sorted(sin_traducir))}): quedan sin cargar."
        )
    if not filas:
        return pd.DataFrame(columns=["ticker"])
    return pd.DataFrame(filas).drop_duplicates(subset="ticker", keep="first")


def main():
    ap = argparse.ArgumentParser(description="Mergea condiciones de emision externas")
    ap.add_argument("--origen", required=True, help="CSV con las condiciones a incorporar")
    ap.add_argument("--dry-run", action="store_true", help="Muestra el impacto sin escribir")
    ap.add_argument("--forzar", action="store_true",
                    help="Pisa los valores ya cargados a mano en vez de solo completar huecos")
    args = ap.parse_args()

    if not os.path.exists(args.origen):
        print(f"ERROR: no existe {args.origen}")
        sys.exit(1)

    alertas = []
    origen = pd.read_csv(args.origen, encoding="utf-8-sig")
    if "ticker" not in origen.columns:
        print(f"ERROR: {args.origen} no tiene columna 'ticker'.")
        sys.exit(1)

    nuevo = expandir_especies(origen, alertas)
    cond = pd.read_csv(CONDICIONES, encoding="utf-8-sig")
    universo = segmentos.cargar_universo([], dedup=False)
    en_universo = set(universo["ticker"])

    # Un ticker que no existe en el universo no se carga: el archivo describe
    # instrumentos reales, no una lista de deseos.
    fuera = nuevo[~nuevo["ticker"].isin(en_universo)]
    if len(fuera):
        alertas.append(
            f"{len(fuera)} tickers de la fuente no estan en el universo consolidado "
            f"({', '.join(fuera['ticker'].head(8))}): no se cargan."
        )
    nuevo = nuevo[nuevo["ticker"].isin(en_universo)]

    for c in COLUMNAS_NUEVAS:
        if c not in cond.columns:
            cond[c] = pd.NA

    # Las filas nuevas se agregan de una sola vez: ir insertando fila por fila
    # sobre el DataFrame dispara la deprecacion de concat con filas all-NA.
    agregados = sorted(set(nuevo["ticker"]) - set(cond["ticker"]))
    if agregados:
        vacias = pd.DataFrame({"ticker": agregados})
        cond = pd.concat([cond, vacias.reindex(columns=cond.columns)], ignore_index=True)

    cond = cond.set_index("ticker")
    completados, pisados = {}, {}

    for _, fila in nuevo.iterrows():
        tk = fila["ticker"]
        for col in [c for c in fila.index if c != "ticker"]:
            valor = fila[col]
            if pd.isna(valor):
                continue
            actual = cond.at[tk, col] if col in cond.columns else pd.NA
            vacio = pd.isna(actual) or str(actual).strip() == ""
            if vacio:
                cond.at[tk, col] = valor
                completados[col] = completados.get(col, 0) + 1
            elif args.forzar and str(actual) != str(valor):
                cond.at[tk, col] = valor
                pisados[col] = pisados.get(col, 0) + 1

    cond = cond.reset_index()

    # Un bono tiene UNA ley y UNA moneda de pago: si sus especies quedan con
    # valores distintos, alguna de las dos fuentes esta equivocada. No se elige
    # por cuenta propia cual — se reporta para que lo resuelva el usuario.
    cond["_raiz"] = [tk[:-1] if (len(str(tk)) >= 4 and str(tk)[-1] in "ODC") else tk
                     for tk in cond["ticker"].astype(str)]
    conflictos, filas_conflicto = [], []
    for col in ("ley", "moneda_pago", "lamina", "calificacion"):
        if col not in cond.columns:
            continue
        n = cond[cond[col].notna()].groupby("_raiz")[col].nunique()
        for raiz in n[n > 1].index:
            mask = (cond["_raiz"] == raiz) & cond[col].notna()
            g = cond[mask]
            conflictos.append((col, raiz, dict(zip(g["ticker"], g[col]))))
            for _, f in g.iterrows():
                filas_conflicto.append({
                    "campo": col, "emision": raiz, "ticker": f["ticker"],
                    "valor_en_conflicto": f[col],
                    "otros_valores": " | ".join(
                        f"{t2}={v2}" for t2, v2 in zip(g["ticker"], g[col])
                        if t2 != f["ticker"]
                    ),
                })
            # Un dato contradictorio no es dato: se vacia y queda para revisar a
            # mano. Elegir una de las dos fuentes por cuenta propia seria decidir
            # cual esta bien sin tener con que probarlo.
            cond.loc[mask, col] = pd.NA

    # Leyes fuera del vocabulario, aunque no entren en conflicto con nada.
    if "ley" in cond.columns:
        huerfanas = cond["ley"].notna() & ~cond["ley"].isin(LEYES_VALIDAS)
        for _, f in cond[huerfanas].iterrows():
            filas_conflicto.append({
                "campo": "ley", "emision": f["_raiz"], "ticker": f["ticker"],
                "valor_en_conflicto": f["ley"],
                "otros_valores": "(fuera del vocabulario: la fuente solo publica "
                                 "Ley Argentina y Ley N.Y.)",
            })
        if huerfanas.any():
            conflictos.append(("ley (fuera de vocabulario)", "-",
                               dict(zip(cond.loc[huerfanas, "ticker"],
                                        cond.loc[huerfanas, "ley"]))))
            cond.loc[huerfanas, "ley"] = pd.NA
    cond = cond.drop(columns=["_raiz"])

    print(f"Fuente: {args.origen} ({len(origen)} filas -> {len(nuevo)} tickers del universo)")
    print(f"\nTickers nuevos agregados al archivo: {len(agregados)}")
    if agregados:
        print("  " + ", ".join(sorted(agregados)))
    print("\nHuecos completados:")
    for col, n in sorted(completados.items()) or [("(ninguno)", 0)]:
        print(f"  {col:14} {n}")
    if pisados:
        print("\nValores PISADOS (--forzar):")
        for col, n in sorted(pisados.items()):
            print(f"  {col:14} {n}")
    elif not args.forzar:
        print("\n(los valores ya cargados no se tocaron; usar --forzar para pisarlos)")

    if conflictos:
        print(f"\n⚠ {len(conflictos)} CONTRADICCIONES entre especies del mismo bono.")
        print("  Un bono tiene una sola ley y una sola moneda de pago: alguna fuente esta mal.")
        print("  Se VACIAN los valores en conflicto (un dato contradictorio no es dato)")
        print(f"  y quedan listados en {os.path.relpath(CONFLICTOS, segmentos.BASE_DIR)} para revisar:\n")
        for col, raiz, valores in conflictos:
            detalle = ", ".join(f"{tk}={v}" for tk, v in sorted(valores.items()))
            print(f"  {col:14} {raiz:6} -> {detalle}")

    for a in alertas:
        print(f"\n! {a}")

    if args.dry_run:
        print("\n--dry-run: no se escribio nada.")
        return

    cond.to_csv(CONDICIONES, index=False, encoding="utf-8")
    if filas_conflicto:
        nuevo_conf = pd.DataFrame(filas_conflicto)
        # Se ACUMULA con lo ya registrado: una vez que un valor en conflicto se
        # vacia, la corrida siguiente ya no lo detecta, y pisar el archivo
        # borraria justo lo que quedaba por investigar.
        if os.path.exists(CONFLICTOS):
            previo = pd.read_csv(CONFLICTOS, encoding="utf-8-sig")
            nuevo_conf = pd.concat([previo, nuevo_conf], ignore_index=True)
        nuevo_conf = (nuevo_conf.drop_duplicates(subset=["campo", "ticker", "valor_en_conflicto"])
                                .sort_values(["campo", "emision", "ticker"]))
        nuevo_conf.to_csv(CONFLICTOS, index=False, encoding="utf-8")
        print(f"\nConflictos a revisar: {CONFLICTOS} ({len(nuevo_conf)} filas)")
    print(f"\nEscrito: {CONDICIONES}")
    print("Correr ahora: python3 tools/consolidar_universo.py")


if __name__ == "__main__":
    main()
