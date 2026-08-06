#!/usr/bin/env python3
"""
Aplica correcciones de sector sobre data/condiciones_estaticas.csv.

Los sectores se cargan por EMISOR, no por ticker: un emisor tiene varias
emisiones y todas comparten sector. La herramienta traduce emisor -> tickers
cruzando contra el universo consolidado, para no escribir un ticker que no
exista (antecedente: una vez se inventaron tickers para una whitelist de prueba).

Uso:
    python3 tools/aplicar_sectores.py --dry-run
    python3 tools/aplicar_sectores.py
"""

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import segmentos  # noqa: E402

CONDICIONES = os.path.join(segmentos.BASE_DIR, "data", "condiciones_estaticas.csv")

# Correcciones validadas con el usuario el 27/07/2026, sobre la propuesta de
# data/sectores_a_revisar.csv.
CORRECCIONES = {
    # Generadoras electricas: el riesgo es tarifario y regulado, no de precio
    # del crudo. Van con las distribuidoras, no con las petroleras.
    "Aes Argentina Generación S.A.": "Servicios",
    "Central Puerto": "Servicios",
    "Generacion Litoral S.A.": "Servicios",
    "Generacion Mediterranea S.A.": "Servicios",
    "YPF LUZ S.A": "Servicios",
    "Tango Energy": "Servicios",
    # Concesionaria de infraestructura aeroportuaria: riesgo de concesion y
    # trafico, no de obra.
    "Aeropuertos Argentina 2000 S.A.": "Infraestructura",
}

# Emisores que la fuente nombra de dos formas distintas. Se unifica el sector
# para que el limite de concentracion no los cuente como dos emisores.
ALIAS_EMISOR = {
    "Aluar Aluminio Argentino Saic": "Aluar",
}


def main():
    ap = argparse.ArgumentParser(description="Aplica correcciones de sector por emisor")
    ap.add_argument("--dry-run", action="store_true",
                    help="Muestra que cambiaria sin escribir el archivo")
    args = ap.parse_args()

    alertas = []
    universo = segmentos.cargar_universo(alertas, dedup=False)
    cond = pd.read_csv(CONDICIONES, encoding="utf-8")

    # emisor -> tickers, tomado del universo. Nunca de una lista escrita a mano.
    por_emisor = (
        universo[universo["underlying"].notna()]
        .groupby("underlying")["ticker"].apply(set).to_dict()
    )

    cambios, sin_encontrar = [], []
    for emisor, sector in CORRECCIONES.items():
        tickers = por_emisor.get(emisor)
        if not tickers:
            sin_encontrar.append(emisor)
            continue
        mask = cond["ticker"].isin(tickers)
        distintos = cond.loc[mask & (cond["sector"] != sector)]
        for _, f in distintos.iterrows():
            cambios.append((f["ticker"], emisor, f["sector"], sector))
        cond.loc[mask, "sector"] = sector

    # Unificacion de alias: el sector del nombre canonico manda.
    for alias, canonico in ALIAS_EMISOR.items():
        t_alias = por_emisor.get(alias, set())
        t_canon = por_emisor.get(canonico, set())
        if not t_alias or not t_canon:
            continue
        sec = cond.loc[cond["ticker"].isin(t_canon), "sector"].dropna()
        if not len(sec):
            continue
        sec = sec.mode().iloc[0]
        mask = cond["ticker"].isin(t_alias) & (cond["sector"] != sec)
        for _, f in cond.loc[mask].iterrows():
            cambios.append((f["ticker"], f"{alias} (alias de {canonico})", f["sector"], sec))
        cond.loc[cond["ticker"].isin(t_alias), "sector"] = sec

    if sin_encontrar:
        print("AVISO: emisores sin tickers en el universo (no se tocan):")
        for e in sin_encontrar:
            print(f"  - {e}")

    if not cambios:
        print("Sin cambios: los sectores ya estaban como corresponde.")
        return

    print(f"{len(cambios)} tickers cambian de sector:\n")
    for tk, emisor, antes, ahora in sorted(cambios, key=lambda c: (c[1], c[0])):
        print(f"  {tk:7} {emisor[:42]:44} {antes:16} -> {ahora}")

    if args.dry_run:
        print("\n--dry-run: no se escribio nada.")
        return

    cond.to_csv(CONDICIONES, index=False, encoding="utf-8")
    print(f"\nEscrito: {CONDICIONES}")
    print("Correr ahora: python3 tools/consolidar_universo.py")


if __name__ == "__main__":
    main()
