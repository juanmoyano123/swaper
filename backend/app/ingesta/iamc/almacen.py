"""Resolución del directorio de subida y guardado del PDF de IAMC.

`settings.iamc_directorio` puede ser relativo (`"fuentes"`, el default) o absoluto. Un relativo se
resuelve contra la raíz del repo, no contra el `cwd` del proceso — el mismo criterio que usa
`ENV_FILE` en `app/core/config.py`, porque el cwd cambia según se arranque con uvicorn, pytest o
Docker. Se reexporta desde ahí en vez de recalcular la raíz acá para no tener dos formas de
llegar al mismo lugar.
"""

from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import ENV_FILE, get_settings

_RAIZ_REPO = ENV_FILE.parent


def _directorio() -> Path:
    ruta = Path(get_settings().iamc_directorio)
    if not ruta.is_absolute():
        ruta = _RAIZ_REPO / ruta
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta


def guardar_informe(
    contenido: bytes, *, fecha_informe: date | None = None, rechazado: bool = False
) -> Path:
    """Guarda el PDF subido y devuelve la ruta.

    Subir dos veces el informe del mismo día sobreescribe: es el mismo informe, y versionar
    subidas repetidas inventaría un historial que no existe. Un informe rechazado (que no se pudo
    parsear) también se guarda —como evidencia para diagnosticar el cambio de layout, no como
    dato válido— con un nombre que no colisiona con el de un informe aceptado.
    """
    directorio = _directorio()

    if rechazado:
        marca = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        nombre = f"iamc-rechazado-{marca}.pdf"
    else:
        if fecha_informe is None:
            raise ValueError("un informe aceptado necesita su fecha para nombrarse")
        nombre = f"iamc-deuda-corporativa-{fecha_informe.isoformat()}.pdf"

    ruta = directorio / nombre
    ruta.write_bytes(contenido)
    return ruta
