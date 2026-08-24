"""El puente `codigo_cnv` -> id interno de la CNV, para linkear desde la ficha de un FCI a su
"COMPOSICIÓN DE CARTERA" pública (artículo 34 del Capítulo XI).

Ninguna fuente que el producto consume trae ese id: la planilla de CAFCI trae `codigo_cnv` (el
número de *registro* del fondo), y el listado de la CNV lo identifica con un id interno propio que
no aparece en ningún lado más. Se cura una sola vez, fuera de request, con
`tools/curar_fci_cnv.py` contra `data/fci_cnv_ids.csv`; acá sólo se lee (regla 11 del dominio:
nada se adivina en tiempo de ejecución).

Mismo criterio que `app/externos/emisores_cuit.py`: el CSV es chico (923 filas) y se lee tal cual
en cada consulta, sin cachear en memoria — la ficha de un fondo no es un endpoint de alto tráfico y
un archivo así de chico no justifica invalidar una caché cuando se recura.
"""

import csv
from pathlib import Path

from app.core.config import ENV_FILE, Settings, get_settings

_RAIZ_REPO = ENV_FILE.parent

URL_BASE_DETALLE_CNV = "https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI"


def ruta_fci_cnv(settings: Settings) -> Path:
    ruta = Path(settings.fci_cnv_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def leer_fci_cnv(ruta: Path) -> dict[str, str]:
    """`{codigo_cnv: id_detalle_cnv}`, tal como quedó curado. Vacío si el archivo no está — sin
    este puente la ficha simplemente declara el fondo sin enlace, igual que un fondo no curado."""
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return {fila["codigo_cnv"]: fila["id_detalle_cnv"] for fila in csv.DictReader(f)}


def enlace_composicion_cnv(codigo_cnv: str | None) -> str | None:
    """La URL de la "COMPOSICIÓN DE CARTERA" pública del fondo en la CNV, o `None` si el fondo no
    trae `codigo_cnv` o no está en el CSV curado — nunca se arma una URL de búsqueda por nombre ni
    se adivina un id."""
    if not codigo_cnv:
        return None
    id_detalle = leer_fci_cnv(ruta_fci_cnv(get_settings())).get(codigo_cnv)
    if id_detalle is None:
        return None
    return f"{URL_BASE_DETALLE_CNV}/{id_detalle}"
