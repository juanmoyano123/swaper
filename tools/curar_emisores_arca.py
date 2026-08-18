#!/usr/bin/env python3
"""Curación de una vez: raíz de emisión -> CUIT del emisor, desde la tabla de valuación de ARCA.

Segundo puente de F-072, y el más fuerte de los dos. `curar_emisores_cuit.py` va del **nombre** del
emisor a su CUIT contra la CNV, y por eso no puede hacer nada con las 89 emisiones ON que no traen
emisor declarado en ninguna fuente: sin nombre no hay de dónde agarrarse. ARCA publica todos los
años, para Bienes Personales, la valuación de las obligaciones negociables al 31/12, y esa tabla
trae **código de especie, CUIT del emisor y denominación en la misma fila** — un puente directo
ticker -> CUIT que saltea el nombre por completo.

**La fuente** (verificada el 18/08/2026, período fiscal 2025):
`afip.gob.ar/gananciasYBienes/bienes-personales/valuaciones/periodo-fiscal-2025.asp`, sección
"Obligaciones negociables". Ojo con la URL: los `href` de esa página son relativos al directorio
`.../valuaciones/`, no a `/gananciasYBienes/` — armarla con la segunda 404ea. El ZIP trae **un ODS**
(OpenDocument), no un XLSX: openpyxl no lo lee y no hay lector de ODS en el venv, así que se parsea
con la stdlib (un ODS es un ZIP con `content.xml` adentro). Una copia del artefacto crudo queda
versionada en `data/fuentes/` para que la curación se pueda auditar contra lo que la fuente dijo.

**El criterio de match es el ticker exacto, y nada más.** El código de especie de ARCA es el mismo
de BYMA (`TLC8O`, `CS34O`), así que el cruce es por clave, no por parecido de nombres. Confirmado
sobre el artefacto 2025: 606 códigos distintos, ninguno con más de un CUIT. Cuando un código de
ARCA matchea una especie del universo, el CUIT se escribe contra la **raíz de emisión** de esa
especie (`raiz_emision`), porque el emisor es atributo de la emisión y no de la especie de
liquidación: resolver `CS34O` resuelve también `CS34D` y `CS34C`.

**Lo que a propósito NO se hace: matchear por raíz cuando el ticker no coincide.** Hay 4 casos donde
ARCA trae la especie en pesos y el universo sólo tiene la de cable (o al revés) — `CP32O` contra
`CP32C`, `MGC9O` contra `MGC9C`, `PECAO` contra `PECAD`, `SNAAD` contra `SNAAO`. Tentador, pero
`SNAA` muestra por qué no: ARCA lo declara venciendo el 19/05/25 y el universo lo tiene venciendo el
14/07/29, o sea que el código se reusó y no son la misma emisión. Sin una forma de distinguir el
caso bueno del malo por dato duro, los cuatro van a pendientes (regla 1: nunca "el más parecido").

**Dónde ARCA le gana al puente por nombre.** Sobre las 179 emisiones que las dos fuentes resuelven,
coinciden en el CUIT en 165 y discrepan en 14, todas del mismo tipo: un grupo económico con dos
sociedades y BYMA escribiendo el nombre de una mientras la emisión es de la otra. PAN AMERICAN
ENERGY es el caso grande (11 emisiones) — el nombre lleva a `PAN AMERICAN ENERGY S.A.`
(30695542476) y ARCA declara la especie emitida por `PAN AMERICAN ENERGY LLC (PAE SUCURSAL)`
(30714813583); los otros dos son CLISA y 360 ENERGY SOLAR. En todos gana ARCA, y no por preferencia:
su clave es la especie concreta, la del otro puente es el nombre que BYMA le puso al emisor. Saber
qué sociedad emitió *esta* emisión es exactamente lo que la primera responde y la segunda no. El
contraste se imprime en cada corrida para que la discrepancia quede a la vista y no enterrada.

**Salvedad de la fuente:** la tabla valúa al 31/12/2025. Una emisión que empezó a cotizar en 2026 no
figura, y eso no es un error del cruce — se declara como faltante y lo resuelve el puente por nombre
cuando el emisor está. Al revés también: ARCA trae cientos de especies ya vencidas que el universo
de hoy no tiene, y ésas simplemente no matchean.

Uso (con el backend local corriendo — lee el universo de hoy, no toca la base):
    python3 tools/curar_emisores_arca.py --dry-run
    python3 tools/curar_emisores_arca.py
    python3 tools/curar_emisores_arca.py --artefacto data/fuentes/2025-Obligaciones-Negociables.ods
"""

import argparse
import csv
import io
import os
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from datetime import date

import httpx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "backend"))

from app.ingesta.raiz import raiz_emision  # noqa: E402

ARTEFACTO_LOCAL = os.path.join(BASE_DIR, "data", "fuentes", "2025-Obligaciones-Negociables.ods")
EMISORES_ARCA_CSV = os.path.join(BASE_DIR, "data", "emisores_arca.csv")
PENDIENTES_CSV = os.path.join(BASE_DIR, "data", "emisores_arca_pendientes.csv")

ZIP_ARCA = (
    "https://www.afip.gob.ar/gananciasYBienes/bienes-personales/valuaciones"
    "/documentos/Bienes-Personales-2025/Obligaciones-negociables/2025-Obligaciones-Negociables.zip"
)
FUENTE = "ARCA Bienes Personales 2025 (valuación al 31/12/2025)"
USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"

CLASE_ON = "on_corporativo"

# Los nombres de columna tal como los titula ARCA en la primera fila del ODS. Se buscan por nombre y
# no por posición: si la fuente agrega una columna el año que viene, esto sigue leyendo bien o falla
# ruidosamente, pero no lee la columna equivocada en silencio.
COL_CODIGO = "Código Especie"
COL_CUIT = "Cuit Emisor"
COL_DENOMINACION = "Denominación Emisor"
COL_CLASE = "Clase de Especie"
COL_NOMBRE = "Nombre Especie"

_NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_NS = {"table": _NS_TABLE, "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def bajar_artefacto() -> bytes:
    """El ODS de adentro del ZIP de ARCA. Se baja entero a memoria: son 56 KB."""
    respuesta = httpx.get(
        ZIP_ARCA, headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True
    )
    respuesta.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(respuesta.content)) as z:
        nombres = [n for n in z.namelist() if n.lower().endswith(".ods")]
        if len(nombres) != 1:
            raise RuntimeError(f"el ZIP de ARCA trajo {nombres!r}, se esperaba un único .ods")
        return z.read(nombres[0])


def _celdas(fila: ET.Element) -> list[str]:
    """El texto de cada celda de una fila del ODS, expandiendo las celdas repetidas.

    `number-columns-repeated` es cómo el formato comprime celdas vacías consecutivas, y viene con
    valores enormes al final de cada fila (el ancho de la hoja). El tope de 40 corta esa cola sin
    perder datos: la tabla tiene 10 columnas.
    """
    celdas: list[str] = []
    for celda in fila.findall("table:table-cell", _NS):
        repeticiones = int(celda.get(f"{{{_NS_TABLE}}}number-columns-repeated", 1))
        texto = "".join("".join(p.itertext()) for p in celda.findall("text:p", _NS)).strip()
        celdas.extend([texto] * min(repeticiones, 40))
    while celdas and celdas[-1] == "":
        celdas.pop()
    return celdas


def leer_ods(contenido: bytes) -> list[dict[str, str]]:
    """Las filas del ODS como diccionarios `{titulo_de_columna: valor}`.

    Se parsea con la stdlib a propósito: un ODS es un ZIP con `content.xml`, y agregar `odfpy` al
    backend para leer una vez al año un archivo de 60 KB no se justifica.
    """
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        raiz = ET.fromstring(z.read("content.xml"))

    hoja = raiz.find(".//table:table", _NS)
    if hoja is None:
        raise RuntimeError("el ODS de ARCA no trae ninguna hoja")

    filas = [c for f in hoja.findall("table:table-row", _NS) if (c := _celdas(f))]
    if not filas:
        raise RuntimeError("el ODS de ARCA no trae filas")

    titulos = filas[0]
    faltantes = {COL_CODIGO, COL_CUIT, COL_DENOMINACION} - set(titulos)
    if faltantes:
        raise RuntimeError(
            f"el ODS de ARCA no trae las columnas {sorted(faltantes)!r} — trae {titulos!r}. "
            "La fuente cambió de forma: revisar antes de curar nada."
        )

    return [dict(zip(titulos, fila, strict=False)) for fila in filas[1:]]


def especies_del_universo(api_base: str) -> list[dict[str, object]]:
    """Las especies ON del universo vivo, tal como las expone `GET /universo/emisiones/especies`."""
    especies: list[dict[str, object]] = []
    cursor = None
    with httpx.Client(timeout=30.0) as cliente:
        while True:
            params: dict[str, object] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            respuesta = cliente.get(f"{api_base}/universo/emisiones/especies", params=params)
            respuesta.raise_for_status()
            datos = respuesta.json()
            items = datos.get("items", [])
            especies.extend(i for i in items if i.get("clase_activo") == CLASE_ON)
            cursor = datos.get("next_cursor")
            if not cursor or not items:
                break
    return especies


def _contrastar_con_el_puente_por_nombre(
    confirmados: list[tuple[str, str, str, str]],
    por_emision: dict[str, list[dict[str, object]]],
) -> None:
    """Cuánto coincide este puente con el que ya existía, y dónde no.

    No cambia ninguna decisión —la cascada del endpoint le da prioridad a ARCA siempre— pero sacar
    las discrepancias a la luz es la única forma de que alguien las revise: cada una es un grupo
    económico donde el nombre del emisor y la sociedad que emitió no son la misma entidad.
    """
    ruta = os.path.join(BASE_DIR, "data", "emisores_cuit.csv")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        por_nombre = {fila["emisor"]: fila["cuit"] for fila in csv.DictReader(f)}

    coinciden = 0
    discrepan: list[str] = []
    for raiz, denominacion, cuit, _clase in confirmados:
        nombres = {
            str(e.get("emisor") or "").strip()
            for e in por_emision[raiz]
            if str(e.get("emisor") or "").strip()
        }
        cuits_por_nombre = {por_nombre[n] for n in nombres if n in por_nombre}
        if not cuits_por_nombre:
            continue
        if cuits_por_nombre == {cuit}:
            coinciden += 1
        else:
            discrepan.append(
                f"    {raiz}: ARCA {cuit} ({denominacion!r}) contra "
                f"{sorted(cuits_por_nombre)} por el nombre {sorted(nombres)}"
            )

    print(
        f"\nContraste con data/emisores_cuit.csv (el puente por nombre), sobre las emisiones que "
        f"las dos fuentes resuelven: {coinciden} coinciden, {len(discrepan)} discrepan."
    )
    for linea in discrepan:
        print(linea)
    if discrepan:
        print("    En todas gana ARCA: su clave es la especie, no el nombre del emisor.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Curación raíz de emisión -> CUIT contra ARCA")
    ap.add_argument("--dry-run", action="store_true", help="Muestra el resultado sin escribir nada")
    ap.add_argument(
        "--artefacto",
        default=None,
        help=f"ODS local en vez de bajarlo de ARCA (p. ej. {ARTEFACTO_LOCAL})",
    )
    ap.add_argument(
        "--api-base",
        default="http://localhost:8000/api/v1",
        help="Backend local corriendo, para leer el universo de hoy (default: %(default)s)",
    )
    args = ap.parse_args()

    if args.artefacto:
        with open(args.artefacto, "rb") as f:
            contenido = f.read()
        print(f"Artefacto local: {args.artefacto}")
    else:
        contenido = bajar_artefacto()
        print(f"Artefacto bajado de ARCA: {len(contenido)} bytes")

    filas = leer_ods(contenido)
    arca: dict[str, dict[str, str]] = {}
    codigos_ambiguos: list[str] = []
    for fila in filas:
        codigo = fila[COL_CODIGO].strip().upper()
        if not codigo:
            continue
        previo = arca.get(codigo)
        if previo is not None and previo[COL_CUIT] != fila[COL_CUIT].strip():
            codigos_ambiguos.append(codigo)
            continue
        arca[codigo] = {k: (v or "").strip() for k, v in fila.items()}
    print(f"ARCA: {len(filas)} filas, {len(arca)} códigos de especie distintos.")
    if codigos_ambiguos:
        print(f"  ¡ojo! códigos con más de un CUIT en la fuente, descartados: {codigos_ambiguos}")

    especies = especies_del_universo(args.api_base)
    por_emision: dict[str, list[dict[str, object]]] = defaultdict(list)
    for especie in especies:
        por_emision[str(especie["emision"])].append(especie)
    print(f"Universo vivo: {len(especies)} especies ON en {len(por_emision)} emisiones.\n")

    confirmados: list[tuple[str, str, str, str]] = []  # (raiz, denominacion, cuit, clase)
    pendientes: list[tuple[str, str]] = []
    raices_del_universo = set(por_emision)

    for emision in sorted(por_emision):
        # Sólo los códigos de ARCA que son exactamente un ticker de esta emisión.
        matches = {
            especie["ticker"]: arca[str(especie["ticker"]).upper()]
            for especie in por_emision[emision]
            if str(especie["ticker"]).upper() in arca
        }
        cuits = {m[COL_CUIT] for m in matches.values()}

        if len(cuits) == 1:
            fila = next(iter(matches.values()))
            raiz = raiz_emision(str(next(iter(matches))))
            if raiz != emision:
                # No debería pasar: el universo agrupa con la misma función. Si pasa, la fuente y
                # nuestro agrupamiento discrepan sobre qué especies son el mismo bono — a mano.
                pendientes.append(
                    (emision, f"raíz calculada {raiz!r} != emisión del universo {emision!r}")
                )
                continue
            confirmados.append((emision, fila[COL_DENOMINACION], fila[COL_CUIT], fila[COL_CLASE]))
            continue

        if len(cuits) > 1:
            detalle = "; ".join(
                f"{tk} -> CUIT {m[COL_CUIT]} ({m[COL_DENOMINACION]!r})" for tk, m in matches.items()
            )
            pendientes.append((emision, f"ARCA declara más de un CUIT para la emisión: {detalle}"))
            continue

        # Sin match exacto. Se anota si ARCA trae otra especie de la misma raíz (los 4 casos de
        # sufijo de liquidación distinto) — es la pista más útil para quien revise a mano.
        hermanas = {
            codigo: arca[codigo]
            for codigo in arca
            if raiz_emision(codigo) == emision and codigo not in matches
        }
        tickers = [str(e["ticker"]) for e in por_emision[emision]]
        if hermanas:
            detalle = "; ".join(
                f"{c} -> CUIT {m[COL_CUIT]} ({m[COL_DENOMINACION]!r}, {m[COL_NOMBRE]!r})"
                for c, m in hermanas.items()
            )
            pendientes.append(
                (
                    emision,
                    f"ARCA trae la raíz con otro sufijo de liquidación (nuestras especies: "
                    f"{tickers}) — {detalle}",
                )
            )
        else:
            pendientes.append(
                (
                    emision,
                    f"sin código en ARCA (nuestras especies: {tickers}) — esperable si la emisión "
                    "empezó a cotizar después del 31/12/2025",
                )
            )

    sin_emisor = {
        emision
        for emision, esp in por_emision.items()
        if not any(str(e.get("emisor") or "").strip() for e in esp)
    }
    resueltas = {raiz for raiz, _, _, _ in confirmados}

    print(f"{len(confirmados)} emisiones con CUIT confirmado por código de especie exacto.")
    print(f"{len(pendientes)} emisiones sin resolver por ARCA (ver el CSV de pendientes).")
    print(
        f"De las {len(sin_emisor)} emisiones sin emisor declarado en ninguna fuente, "
        f"ARCA resuelve {len(sin_emisor & resueltas)} y deja {len(sin_emisor - resueltas)}."
    )
    print(f"CUITs distintos: {len({c for _, _, c, _ in confirmados})}.")

    codigos_sin_uso = {c for c in arca if raiz_emision(c) not in raices_del_universo}
    print(
        f"{len(codigos_sin_uso)} códigos de ARCA no corresponden a ninguna emisión del universo de "
        "hoy: especies ya vencidas o que dejaron de cotizar."
    )

    _contrastar_con_el_puente_por_nombre(confirmados, por_emision)

    if args.dry_run:
        print("\n--dry-run: no se escribió nada.")
        return

    hoy = date.today().isoformat()
    with open(EMISORES_ARCA_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raiz_emision", "denominacion", "cuit", "clase", "fuente", "verificado"])
        for raiz, denominacion, cuit, clase in sorted(confirmados):
            w.writerow([raiz, denominacion, cuit, clase, FUENTE, hoy])
    print(f"\nEscrito: {EMISORES_ARCA_CSV}")

    with open(PENDIENTES_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raiz_emision", "motivo"])
        for raiz, motivo in sorted(pendientes):
            w.writerow([raiz, motivo])
    print(f"Escrito: {PENDIENTES_CSV} (revisión manual, no se usa en runtime)")


if __name__ == "__main__":
    main()
