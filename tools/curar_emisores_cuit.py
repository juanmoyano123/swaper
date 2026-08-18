#!/usr/bin/env python3
"""
Curación de una vez: emisor -> CUIT, contra las dos fuentes públicas de la CNV.

Puente para F-072 (prospecto de emisión de ONs, vía CNV): la ficha de una ON necesita el CUIT del
emisor para pedirle a la CNV sus documentos, y ninguna fuente que ya consumimos lo trae (ni BYMA ni
`data/condiciones_emision.csv`). Se resuelve una sola vez, a mano y verificado, y no en cada request.

**Fuente primaria: el "Listado Completo de Emisoras por Régimen"** — el XLSX descargable que la
propia CNV publica en su buscador de empresas (`Reportes/ListadoSociedadesEmisorasPorRegimen`), con
CUIT, razón social, categoría y estado de todas las emisoras en oferta pública (~531 al 17/08/2026,
verificado en vivo). Es un descargable oficial, sin clave, y resuelve de una sola vez lo que el
buscador resuelve nombre por nombre. Ojo con leerlo: openpyxl en modo `read_only` ve 4 filas (el
XLSX viene sin metadatos de dimensión); en modo normal ve las ~534 — cargar SIN `read_only`.

**Fuente secundaria: el AutoComplete del buscador** (`Empresas/AutoComplete?term=`) — sólo para los
nombres que el listado no matchea, porque busca difuso y a veces encuentra grafías que el listado
escribe distinto. Es un buscador nombre por nombre y adivina el parecido, así que el criterio de
confirmación es el mismo y conservador en las dos fuentes: match único con nombre normalizado
exactamente igual, o pendiente a revisión humana (regla 1 del proyecto).

**La clave de curación tiene que ser el `emisor` tal como sale de `EspecieUniverso` en vivo, no el
`underlying` de `condiciones_emision.csv`.** Los dos difieren: BYMA publica su propio `underlying`
por especie (mayúsculas, forma societaria completa — "LEDESMA S.A.A.I.") y ese es el que gana en
`EspecieUniverso.emisor` cuando está presente; el CSV curado sólo rellena el hueco cuando BYMA no
lo trae, con su propio nombre abreviado ("Ledesma"). Curar contra el CSV deja el bridge sin usarse
en el caso más común: el endpoint busca `especie.emisor` (mayormente el de BYMA) y no lo encuentra.
Verificado el 17/08/2026 contra el universo vivo: de 82 nombres distintos en el CSV curado, el
universo real trae 112 —incluye los mismos emisores, dos veces, con dos grafías cada uno—.

Uso (con el backend local corriendo — lee el universo de hoy, no toca la base):
    python3 tools/curar_emisores_cuit.py --dry-run
    python3 tools/curar_emisores_cuit.py
    python3 tools/curar_emisores_cuit.py --api-base http://localhost:8000/api/v1

Sólo se escribe `data/emisores_cuit.csv` con matches sin ambigüedad: un único candidato cuyo nombre,
normalizado (sin tildes, sin mayúsculas/minúsculas, sin la forma societaria S.A./S.R.L./etc.), es
igual al emisor tal como lo trae el universo. Todo lo demás —cero candidatos, más de uno, o un único
candidato que no matchea exacto— va a `data/emisores_cuit_pendientes.csv` con los candidatos que sí
aparecieron, para revisión humana. Nunca se elige "el más parecido".
"""

import argparse
import csv
import os
import re
import sys
import time
import unicodedata
from datetime import date

import httpx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMISORES_CUIT_CSV = os.path.join(BASE_DIR, "data", "emisores_cuit.csv")
PENDIENTES_CSV = os.path.join(BASE_DIR, "data", "emisores_cuit_pendientes.csv")

AUTOCOMPLETE_URL = "https://www.cnv.gov.ar/SitioWeb/Empresas/AutoComplete"
LISTADO_URL = "https://www.cnv.gov.ar/SitioWeb/Reportes/ListadoSociedadesEmisorasPorRegimen"
USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"
PAUSA_ENTRE_PEDIDOS_SEGUNDOS = 0.5

# El Tesoro no es un emisor corporativo: F-072 sólo aplica a ONs (clase_activo == 'on_corporativo').
# Curarle un CUIT no tiene destino y sólo agrega ruido al archivo.
EMISOR_SOBERANO = "Gobierno Argentino"

# Confirmaciones manuales del 17/08/2026, donde el match automático no alcanza porque las dos
# fuentes escriben el nombre distinto (sigla contra razón social, "SOCIEDAD ANONIMA" contra "S.A.",
# typo de BYMA). **Ninguna entró por parecido a secas**: cada una se verificó contra los documentos
# reales del CUIT candidato en la CNV (`ClienteCnv.documentos_de`) — o los documentos nombran al
# emisor (Cresud: 264 de 386 docs dicen CRESUD; IRSA: 248 de 342; ICBC: 36; Mirgor: 23; Richmond:
# 14; Ledesma: 10; Aluar: 3; CGC: 3), o el nombre del candidato es la expansión literal del que
# trae el universo (OLEODUCTOS DEL VALLE "SOCIEDAD ANONIMA" = "S.A."; COMPAÑÍA MEGA ídem; RIVER
# PLATE "ASOC CIVIL" = "ASOCIACIÓN CIVIL"; PROFERTIL "S A" = "S.A."; SCANIA CREDIT "S. A. U." =
# "S.A.U."; MINAS ARGENTINAS "S. A." = "S.A."; C&C "MEDICAL S" = "MEDICALS" en el listado oficial),
# o la propia CNV asocia los nombres (EDEMSA/EDENOR: su buscador devuelve la razón social completa
# ante la sigla; OILTANKING EBYTEM: su buscador devuelve OTAMERICA EBYTEM, la sociedad renombrada;
# MERCADO PAGO: único candidato, "SERVICIOS" contra el "SERVICIO" que tipea BYMA).
#
# Lo que NO está acá, a propósito: HAVANNA (hay dos sociedades, holding y operativa, y nuestras
# propias fuentes discrepan sobre cuál emite), EDESA (ídem: distribuidora y holding), BNA y Banco
# Provincia Bs As (bancos públicos sin ficha EMISIO consultable en la CNV), Farmacity (sin
# candidato en ninguna de las dos fuentes). Quedan en pendientes hasta tener evidencia.
CONFIRMADOS_A_MANO: dict[str, str] = {
    "ALUMINIO ARGENTINO S.A.I.C": "30522780606",  # Aluar Aluminio Argentino
    "C&C MEDICALS S.A.": "30707174702",  # C & C MEDICAL S SOCIEDAD ANONIMA (listado)
    "CLUB ATLETICO RIVER PLATE ASOCIACIÓN CIVIL": "30526748448",
    "COMPAÑIA GENERAL DE COMBUSTIBLES S.A.": "30506733932",  # Cia. General de Combustibles
    "Compañía General De Combustibles S.A.": "30506733932",
    "COMPAÑIA MEGA S.A.": "30696139888",
    "CRESUD S.A.C.I.F.A.": "30509300700",
    "EDEMSA S.A.": "30699542454",  # Emp. Distribuidora de Electricidad de Mendoza
    "Edemsa S.A.": "30699542454",
    "EDENOR S.A.": "30655116202",  # Empresa Distribuidora y Comercializadora Norte
    "Icbc": "30709447846",  # Industrial and Commercial Bank of China (Argentina)
    "INVERSIONES Y REPRESENTACIONES S.A.": "30525322749",  # IRSA
    "Irsa Inversiones Y Representaciones S.A.": "30525322749",
    "LABORATORIOS RICHMOND S.A.C.I.F.": "30501152826",
    "LEDESMA S.A.A.I.": "30501250305",
    "Mercado Pago": "30716999498",
    "MERCADO PAGO SERVICIO DE PROCESAMIENTO S.R.L.": "30716999498",
    "Minas Argentinas S.A.": "30677262466",
    "MIRGOR S.A.C.I.F.I.A.": "30578036071",
    "OILTANKING EBYTEM S.A.": "30658839523",  # renombrada OTAMERICA EBYTEM
    "OLEODUCTOS DEL VALLE S.A.": "30658840165",
    "PROFERTIL S.A.": "30691576511",
    "Profertil": "30691576511",
    "Scania Credit": "30717023990",
    "SCANIA CREDIT ARGENTINA S.A.U.": "30717023990",
    "Tango Energy": "30714814229",  # TANGO ENERGY ARGENTINA S.A.
}

# Formas societarias que el nombre del emisor trae y la CNV a veces no repite igual (o al revés).
# Se sacan sólo para comparar, nunca para lo que se guarda en el CSV final. Los puntos ya salieron
# de la cadena antes de aplicar esto (ver `normalizar`), así que acá van sin `\.?`.
FORMAS_SOCIETARIAS = re.compile(
    r"\b(SAU|SAIC|SACIFYA|SACI|SRL|SAS|SA|CIASA|LLC)\b"
)


def normalizar(nombre: str) -> str:
    """Mayúsculas, sin tildes, sin puntuación, sin forma societaria, espacios colapsados — sólo
    para comparar. Los puntos se sacan antes de buscar la forma societaria: dejarlos adentro rompía
    el `\\b` de cierre cuando el nombre terminaba en "S.A." (quedaba un punto colgado sin sacar)."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    sin_puntuacion = re.sub(r"[.,]", "", sin_tildes).upper()
    sin_forma = FORMAS_SOCIETARIAS.sub(" ", sin_puntuacion)
    return re.sub(r"\s+", " ", sin_forma).strip()


def emisores_del_universo(api_base: str) -> list[str]:
    """Los emisores distintos de las ONs del universo vivo (`clase_activo == 'on_corporativo'`),
    tal como los expone `GET /universo/emisiones/especies` — el mismo valor que va a llegar a
    `especie.emisor` en el endpoint de F-072. Pagina el cursor entero: no hay atajo, la API no
    filtra por clase."""
    emisores: set[str] = set()
    cliente = httpx.Client(timeout=20.0)
    cursor = None
    while True:
        params = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        respuesta = cliente.get(f"{api_base}/universo/emisiones/especies", params=params)
        respuesta.raise_for_status()
        datos = respuesta.json()
        items = datos.get("items", [])
        for item in items:
            emisor = (item.get("emisor") or "").strip()
            if item.get("clase_activo") == "on_corporativo" and emisor and emisor != EMISOR_SOBERANO:
                emisores.add(emisor)
        cursor = datos.get("next_cursor")
        if not cursor or not items:
            break
    cliente.close()
    return sorted(emisores)


def buscar(cliente: httpx.Client, nombre: str) -> list[dict]:
    """Los candidatos que la CNV propone para este nombre. Lista vacía si no encuentra nada."""
    respuesta = cliente.get(AUTOCOMPLETE_URL, params={"term": nombre}, headers={"User-Agent": USER_AGENT})
    respuesta.raise_for_status()
    return respuesta.json()


def listado_de_emisoras(cliente: httpx.Client) -> dict[str, list[tuple[str, str]]]:
    """El listado oficial completo, como `{forma_normalizada: [(cuit, razon_social), ...]}`.

    La lista por clave existe porque dos sociedades distintas podrían normalizar igual; el matching
    de `main` sólo confirma cuando todos los candidatos de la forma comparten un único CUIT.
    """
    import io

    import openpyxl

    respuesta = cliente.get(LISTADO_URL, headers={"User-Agent": USER_AGENT})
    respuesta.raise_for_status()
    # SIN read_only: el XLSX de la CNV viene sin metadatos de dimensión y en read_only openpyxl
    # corta en la fila 4 (verificado el 17/08/2026: 4 filas contra 534 reales).
    libro = openpyxl.load_workbook(io.BytesIO(respuesta.content))
    filas = list(libro["Sociedades"].iter_rows(values_only=True))

    listado: dict[str, list[tuple[str, str]]] = {}
    en_datos = False
    for fila in filas:
        if fila[:2] == ("CUIT", "Sociedad"):
            en_datos = True
            continue
        if not en_datos or not fila[0] or not fila[1]:
            continue
        cuit, nombre = str(fila[0]).strip(), str(fila[1]).strip()
        listado.setdefault(normalizar(nombre), []).append((cuit, nombre))
    return listado


def _agrupar_por_forma_normalizada(emisores: list[str]) -> dict[str, list[str]]:
    """El universo vivo trae el mismo emisor dos veces con dos grafías (BYMA en mayúsculas con la
    forma societaria completa, el curado de `condiciones_emision.csv` rellenando huecos con su
    nombre abreviado — 261 casos documentados en `_resolver_emisor`, `universo/segmentacion.py`).
    Agrupar por forma normalizada antes de consultar no es adivinar una coincidencia nueva: es
    reconocer variantes que el propio universo ya declaró del mismo emisor."""
    grupos: dict[str, list[str]] = {}
    for emisor in emisores:
        grupos.setdefault(normalizar(emisor), []).append(emisor)
    return grupos


def main() -> None:
    ap = argparse.ArgumentParser(description="Curación emisor -> CUIT contra la CNV")
    ap.add_argument("--dry-run", action="store_true", help="Muestra el resultado sin escribir nada")
    ap.add_argument(
        "--api-base",
        default="http://localhost:8000/api/v1",
        help="Backend local corriendo, para leer el universo de hoy (default: %(default)s)",
    )
    args = ap.parse_args()

    emisores = emisores_del_universo(args.api_base)
    grupos = _agrupar_por_forma_normalizada(emisores)
    print(
        f"{len(emisores)} emisores de ON distintos en el universo vivo, "
        f"{len(grupos)} formas normalizadas (sin el soberano).\n"
    )

    confirmados: list[tuple[str, str, str]] = []  # (emisor, cuit, fuente)
    pendientes: list[tuple[str, str]] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as cliente:
        listado = listado_de_emisoras(cliente)
        print(f"Listado oficial descargado: {sum(len(v) for v in listado.values())} emisoras.\n")

        for i, (objetivo, variantes) in enumerate(sorted(grupos.items()), 1):
            # Cero: las confirmaciones manuales verificadas contra los documentos de la CNV.
            a_mano = {CONFIRMADOS_A_MANO[v] for v in variantes if v in CONFIRMADOS_A_MANO}
            if len(a_mano) == 1:
                cuit = next(iter(a_mano))
                print(f"  [{i}/{len(grupos)}] {variantes[0]!r} -> CUIT {cuit} (confirmado a mano)")
                for variante in variantes:
                    confirmados.append((variante, cuit, "CNV, verificado a mano 17/08/2026"))
                continue

            # Primero el listado oficial: un lookup local, sin red por emisor.
            candidatos_listado = listado.get(objetivo, [])
            cuits = {c for c, _ in candidatos_listado}
            if len(cuits) == 1:
                cuit = next(iter(cuits))
                print(
                    f"  [{i}/{len(grupos)}] {variantes[0]!r} -> CUIT {cuit} "
                    f"({candidatos_listado[0][1]!r}, listado)"
                )
                for variante in variantes:
                    confirmados.append((variante, cuit, "CNV Listado Sociedades"))
                continue
            if len(cuits) > 1:
                detalle = "; ".join(f"{n!r} (CUIT {c})" for c, n in candidatos_listado)
                print(f"  [{i}/{len(grupos)}] {variantes!r}: ambiguo en el listado — {detalle}")
                for variante in variantes:
                    pendientes.append((variante, f"ambiguo en el listado: {detalle}"))
                continue

            # Sin match en el listado: cae al AutoComplete, probando cada grafía tal como aparece
            # en el universo — la búsqueda de la CNV es sensible a mayúsculas/puntuación de la
            # propia consulta (verificado el 17/08/2026: "Telecom Argentina S.A" encuentra el
            # emisor, "TELECOM ARGENTINA S.A." no).
            cuit_confirmado: str | None = None
            candidatos_vistos: list[dict] = []
            for variante in variantes:
                try:
                    candidatos = buscar(cliente, variante)
                except httpx.HTTPError as exc:
                    print(f"  [{i}/{len(grupos)}] {variante!r}: error de red ({exc})")
                    time.sleep(PAUSA_ENTRE_PEDIDOS_SEGUNDOS)
                    continue
                candidatos_vistos = candidatos
                time.sleep(PAUSA_ENTRE_PEDIDOS_SEGUNDOS)

                matches = [c for c in candidatos if normalizar(c["descripcion"]) == objetivo]
                if len(matches) == 1:
                    cuit_confirmado = matches[0]["cuit"]
                    print(
                        f"  [{i}/{len(grupos)}] {variante!r} -> CUIT {cuit_confirmado} "
                        f"({matches[0]['descripcion']!r}, autocomplete)"
                    )
                    break

            if cuit_confirmado is not None:
                for variante in variantes:
                    confirmados.append((variante, cuit_confirmado, "CNV AutoComplete"))
            else:
                detalle = (
                    "; ".join(f"{c['descripcion']!r} (CUIT {c['cuit']})" for c in candidatos_vistos)
                    or "sin candidatos"
                )
                print(f"  [{i}/{len(grupos)}] {variantes!r}: sin match único — {detalle}")
                for variante in variantes:
                    pendientes.append((variante, detalle))

    print(f"\n{len(confirmados)} confirmados sin ambigüedad, {len(pendientes)} a revisar a mano.")

    if args.dry_run:
        print("\n--dry-run: no se escribió nada.")
        return

    hoy = date.today().isoformat()
    with open(EMISORES_CUIT_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["emisor", "cuit", "fuente", "verificado"])
        for emisor, cuit, fuente in confirmados:
            w.writerow([emisor, cuit, fuente, hoy])
    print(f"Escrito: {EMISORES_CUIT_CSV}")

    with open(PENDIENTES_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["emisor", "candidatos"])
        for emisor, detalle in pendientes:
            w.writerow([emisor, detalle])
    print(f"Escrito: {PENDIENTES_CSV} (revisión manual, no se usa en runtime)")


if __name__ == "__main__":
    main()
