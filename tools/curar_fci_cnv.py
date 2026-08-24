#!/usr/bin/env python3
"""Curación de una vez: fondo padre de CAFCI -> id interno de la CNV, para linkear desde la ficha
de un FCI a la "COMPOSICIÓN DE CARTERA" pública que la CNV publica semanalmente (artículo 34).

Puente para el enlace CNV en la ficha de FCI (F-057/F-046). La página destino funciona sin query
params — `https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/{id}` (verificado en
vivo el 23/08/2026, HTTP 200 con sección "COMPOSICIÓN DE CARTERA")— pero el `{id}` es un
identificador interno de la CNV que ninguna fuente que ya consumimos declara: ni la planilla de
CAFCI (que trae `codigo_cnv`, el número de *registro*, no este id) ni `condiciones_emision.csv`.
Se resuelve una sola vez, a mano y verificado, y no en cada request (regla 11 del dominio).

**Fuente del listado de la CNV**: `POST /SitioWeb/FondosComunesInversion/GetFCIPorTipo` con
`tipo=1` — devuelve un único JSON con los 1.677 fondos activos (`{"Text": " NOMBRE", "Value": "id"}`
por fondo), sin paginar. Se probó también el listado HTML paginado
(`POST .../Busqueda?pagina=N`, ~56 páginas) que trae denominación, gerente y depositaria además del
id, pero el JSON alcanza para lo que necesita esta curación (matching sólo por nombre) y es un
único pedido en vez de 56: se usa el JSON.

**Fuente de los fondos padre**: la planilla diaria de CAFCI (mismo XLSX que consume
`app/ingesta/cafci/parser.py`), agrupada por `codigo_cnv` (columna S) — un fondo padre puede tener
varias clases (columna A: "Fondo X - Clase A", "Fondo X - Clase B"...) y todas comparten
`codigo_cnv`.

**Matching**: nombre normalizado (NFD sin diacríticos, minúsculas, sin "- Clase X" ni sufijos
legales de forma societaria del fondo — "F.C.I.", "FCI", "Fondo Común de Inversión (Abierto)" y
variantes cerradas—, sólo [a-z0-9]). Conservador: sólo entra a `data/fci_cnv_ids.csv` un
`codigo_cnv` cuyo nombre normalizado matchea un único id en el listado de la CNV. Cero matches o
más de uno van a `data/fci_cnv_pendientes.csv` para revisión humana — nunca se elige "el más
parecido" (mismo criterio que `tools/curar_emisores_cuit.py`).

Uso (con acceso a red, sin backend local necesario — las dos fuentes son públicas):
    python3 tools/curar_fci_cnv.py --dry-run
    python3 tools/curar_fci_cnv.py
"""

import argparse
import csv
import io
import os
import re
import sys
import unicodedata
from datetime import date

import httpx
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FCI_CNV_CSV = os.path.join(BASE_DIR, "data", "fci_cnv_ids.csv")
PENDIENTES_CSV = os.path.join(BASE_DIR, "data", "fci_cnv_pendientes.csv")

CNV_LISTADO_URL = "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/GetFCIPorTipo"
CAFCI_URL = "https://api.pub.cafci.org.ar/pb_get"
USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"

# Columnas 1-indexadas de la planilla de CAFCI, tal como las declara
# `app/ingesta/cafci/parser.py` (verificadas de nuevo contra el archivo real el 23/08/2026).
FILA_INICIO_DATOS = 10
COL_FONDO = 1
COL_MONEDA = 2
COL_CODIGO_CNV = 19
COL_GERENTE = 24

# Sufijos de forma societaria/estado del fondo que las dos fuentes escriben distinto y que no
# aportan nada para identificar el fondo. Se sacan sólo para comparar, nunca para lo que se
# guarda en el CSV final (`denominacion_cnv` y el nombre de CAFCI viajan tal como los trae cada
# fuente).
_PATRON_CLASE = re.compile(r"-?\s*clase\s+[a-z0-9ivx]+\b")
_PATRON_ESTADO = re.compile(
    r"\(\s*(en proceso de liquidaci[oó]n|valor final de liquidaci[oó]n)\s*\)"
)
_PATRONES_FORMA_LEGAL = (
    re.compile(r"\bfondo\s+comun\s+de\s+inversion\s+cerrado\s+agropecuario\b"),
    re.compile(r"\bfondo\s+comun\s+de\s+inversion\s+cerrado\s+inmobiliario\b"),
    re.compile(r"\bfondo\s+comun\s+de\s+inversion\s+abierto\b"),
    re.compile(r"\bfondo\s+comun\s+de\s+inversion\b"),
    re.compile(r"\bf\.?\s*c\.?\s*i\.?\b"),
)


def normalizar(nombre: str) -> str:
    """NFD sin diacríticos, minúsculas, sin clase ni forma legal del fondo, sólo [a-z0-9]."""
    sin_tildes = unicodedata.normalize("NFD", nombre)
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    s = sin_tildes.lower()
    s = _PATRON_ESTADO.sub(" ", s)
    s = _PATRON_CLASE.sub(" ", s)
    for patron in _PATRONES_FORMA_LEGAL:
        s = patron.sub(" ", s)
    return re.sub(r"[^a-z0-9]", "", s)


def listado_cnv(cliente: httpx.Client) -> list[tuple[str, str]]:
    """`[(id, denominacion), ...]` de los 1.677 fondos activos que declara la CNV."""
    respuesta = cliente.post(
        CNV_LISTADO_URL,
        data={"tipo": "1"},
        headers={"User-Agent": USER_AGENT},
    )
    respuesta.raise_for_status()
    datos = respuesta.json()
    return [(str(item["Value"]), str(item["Text"]).strip()) for item in datos]


def fondos_padre_cafci(cliente: httpx.Client) -> dict[str, tuple[str, str | None]]:
    """`{codigo_cnv: (nombre_representativo, gerente)}`, un fondo padre por `codigo_cnv` — la
    planilla trae una fila por clase y todas comparten `codigo_cnv`."""
    respuesta = cliente.get(CAFCI_URL, headers={"User-Agent": USER_AGENT})
    respuesta.raise_for_status()
    libro = openpyxl.load_workbook(io.BytesIO(respuesta.content), data_only=True)
    ws = libro.worksheets[0]

    padres: dict[str, tuple[str, str | None]] = {}
    for fila in range(FILA_INICIO_DATOS, ws.max_row + 1):
        fondo = ws.cell(row=fila, column=COL_FONDO).value
        if fondo is None:
            continue
        moneda = ws.cell(row=fila, column=COL_MONEDA).value
        if moneda is None:
            continue  # fila de sección, no de datos
        codigo_cnv = ws.cell(row=fila, column=COL_CODIGO_CNV).value
        if codigo_cnv is None:
            continue
        codigo_cnv = str(codigo_cnv).strip()
        if codigo_cnv in padres:
            continue
        gerente = ws.cell(row=fila, column=COL_GERENTE).value
        padres[codigo_cnv] = (str(fondo).strip(), str(gerente).strip() if gerente else None)
    return padres


def main() -> None:
    ap = argparse.ArgumentParser(description="Curación fondo padre CAFCI -> id interno CNV")
    ap.add_argument("--dry-run", action="store_true", help="Muestra el resultado sin escribir nada")
    args = ap.parse_args()

    with httpx.Client(timeout=30.0, follow_redirects=True) as cliente:
        print("Descargando listado de fondos de la CNV...")
        cnv = listado_cnv(cliente)
        print(f"  {len(cnv)} fondos en el listado de la CNV.\n")

        print("Descargando planilla diaria de CAFCI...")
        padres = fondos_padre_cafci(cliente)
        print(f"  {len(padres)} fondos padre distintos (por codigo_cnv) en la planilla.\n")

    indice_cnv: dict[str, list[tuple[str, str]]] = {}
    for id_cnv, denominacion in cnv:
        indice_cnv.setdefault(normalizar(denominacion), []).append((id_cnv, denominacion))

    confirmados: list[tuple[str, str, str, str]] = []  # (codigo_cnv, id, denominacion, verificado_por)
    pendientes: list[tuple[str, str, str]] = []  # (codigo_cnv, nombre_cafci, candidatos)

    for codigo_cnv, (nombre_cafci, _gerente) in sorted(padres.items(), key=lambda kv: kv[0]):
        objetivo = normalizar(nombre_cafci)
        candidatos = indice_cnv.get(objetivo, [])
        ids_distintos = {c for c, _ in candidatos}

        if len(ids_distintos) == 1:
            id_cnv, denominacion = candidatos[0]
            confirmados.append((codigo_cnv, id_cnv, denominacion, "nombre"))
        elif len(ids_distintos) > 1:
            detalle = "; ".join(f"{d!r} (id {i})" for i, d in candidatos)
            pendientes.append((codigo_cnv, nombre_cafci, f"ambiguo: {detalle}"))
        else:
            pendientes.append((codigo_cnv, nombre_cafci, "sin candidatos"))

    total = len(padres)
    print(
        f"{len(confirmados)}/{total} fondos padre matchean único "
        f"({len(confirmados) / total:.0%}), {len(pendientes)} a revisar a mano.\n"
    )

    if args.dry_run:
        print("--dry-run: no se escribió nada.")
        return

    hoy = date.today().isoformat()
    with open(FCI_CNV_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo_cnv", "id_detalle_cnv", "denominacion_cnv", "verificado_por", "curado_en"])
        for codigo_cnv, id_cnv, denominacion, verificado_por in confirmados:
            w.writerow([codigo_cnv, id_cnv, denominacion, verificado_por, hoy])
    print(f"Escrito: {FCI_CNV_CSV}")

    with open(PENDIENTES_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo_cnv", "fondo_cafci", "candidatos"])
        for codigo_cnv, nombre_cafci, detalle in pendientes:
            w.writerow([codigo_cnv, nombre_cafci, detalle])
    print(f"Escrito: {PENDIENTES_CSV} (revisión manual, no se usa en runtime)")


if __name__ == "__main__":
    main()
