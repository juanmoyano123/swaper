"""El puente emisor -> CUIT, curado una vez contra el buscador de la CNV (F-072).

Ninguna fuente que el producto ya consume trae el CUIT de un emisor: ni BYMA, ni
`condiciones_emision.csv` (que sólo trae el nombre, en `underlying`/`emisor`). Se cura una vez con
`tools/curar_emisores_cuit.py` —sin ambigüedad: sólo entran los emisores donde el buscador de la
CNV devolvió un único candidato cuyo nombre normalizado coincide exacto— y el resto queda en
`data/emisores_cuit_pendientes.csv` para revisión a mano, nunca adivinado en este módulo.

Mismo criterio que `app/condiciones/corrida.py::ruta_semilla`: la ruta configurada se resuelve
contra la raíz del repo, no contra el cwd del proceso.
"""

import csv
from pathlib import Path

from app.core.config import ENV_FILE, Settings

_RAIZ_REPO = ENV_FILE.parent


def ruta_emisores_cuit(settings: Settings) -> Path:
    ruta = Path(settings.emisores_cuit_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def leer_emisores_cuit(ruta: Path) -> dict[str, str]:
    """`{emisor: cuit}`, tal como quedó curado. Vacío si el archivo no está — no es fatal como la
    semilla de condiciones: sin este puente, F-072 simplemente declara cada emisor sin CUIT
    resuelto en vez de tener nada que mostrar, y el resto de la app sigue funcionando igual."""
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return {fila["emisor"]: fila["cuit"] for fila in csv.DictReader(f)}
