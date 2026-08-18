"""Los dos puentes que llevan de una ON al CUIT de su emisor, para pedirle documentos a la CNV
(F-072).

Ninguna fuente que el producto ya consume trae el CUIT de un emisor: ni BYMA, ni
`condiciones_emision.csv` (que sólo trae el nombre, en `underlying`/`emisor`). Se curan una vez,
fuera de request, y acá sólo se leen — nada se adivina en este módulo.

**Por raíz de emisión, contra ARCA** (`data/emisores_arca.csv`, `tools/curar_emisores_arca.py`): la
tabla de valuación de Bienes Personales publica código de especie, CUIT y denominación en la misma
fila, así que la clave es el ticker y el nombre del emisor no participa. Es el puente fuerte: cubre
emisiones que no tienen emisor declarado en ninguna fuente, y cuando las dos fuentes discrepan gana
ésta, porque identifica la sociedad que emitió *esta* emisión en vez del nombre que BYMA le puso al
emisor (PAN AMERICAN ENERGY LLC contra PAN AMERICAN ENERGY S.A., por ejemplo).

**Por nombre de emisor, contra la CNV** (`data/emisores_cuit.csv`, `tools/curar_emisores_cuit.py`):
el puente original, hoy respaldo. Sólo entran los emisores donde el listado o el buscador de la CNV
devolvió un único candidato cuyo nombre normalizado coincide exacto; el resto queda en
`data/emisores_cuit_pendientes.csv` para revisión a mano. Sigue haciendo falta porque ARCA valúa al
31/12 y no puede traer una emisión que salió a cotizar después.

Mismo criterio que `app/condiciones/corrida.py::ruta_semilla` en los dos: la ruta configurada se
resuelve contra la raíz del repo, no contra el cwd del proceso.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from app.core.config import ENV_FILE, Settings

_RAIZ_REPO = ENV_FILE.parent


@dataclass(frozen=True)
class EmisorArca:
    """Lo que ARCA declara del emisor de una emisión, tal como lo declara.

    `denominacion` viaja sin normalizar (regla 11): es el nombre que la fuente publica, y sirve para
    mostrar un emisor en las emisiones donde el universo no trae ninguno.
    """

    cuit: str
    denominacion: str


def ruta_emisores_cuit(settings: Settings) -> Path:
    ruta = Path(settings.emisores_cuit_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def ruta_emisores_arca(settings: Settings) -> Path:
    ruta = Path(settings.emisores_arca_csv)
    return ruta if ruta.is_absolute() else _RAIZ_REPO / ruta


def leer_emisores_arca(ruta: Path) -> dict[str, EmisorArca]:
    """`{raiz_emision: EmisorArca}`, tal como quedó curado. Vacío si el archivo no está: sin este
    puente la feature cae al de por nombre y declara lo que no puede resolver, igual que antes."""
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return {
            fila["raiz_emision"]: EmisorArca(cuit=fila["cuit"], denominacion=fila["denominacion"])
            for fila in csv.DictReader(f)
        }


def leer_emisores_cuit(ruta: Path) -> dict[str, str]:
    """`{emisor: cuit}`, tal como quedó curado. Vacío si el archivo no está — no es fatal como la
    semilla de condiciones: sin este puente, F-072 simplemente declara cada emisor sin CUIT
    resuelto en vez de tener nada que mostrar, y el resto de la app sigue funcionando igual."""
    if not ruta.exists():
        return {}
    with ruta.open(encoding="utf-8") as f:
        return {fila["emisor"]: fila["cuit"] for fila in csv.DictReader(f)}
