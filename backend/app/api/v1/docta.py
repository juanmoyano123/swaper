"""Rutas de la ingesta del feed de cashflow — F-006.

El router está vacío y ya montado en `router.py`: F-006 agrega sus rutas acá sin tocar ningún otro
archivo compartido.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.ingesta.docta import ConfiguracionFaltante, ingerir_cashflow

router = APIRouter(tags=["docta"])


@router.post(
    "/docta/ingesta",
    summary="Corre la ingesta del feed de cashflow de Docta",
    responses={503: {"description": "Falta configuración obligatoria de Docta"}},
)
async def ingesta_docta(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Dispara la corrida. Responde 200 con el snapshot aunque la fuente haya fallado — la
    corrida corrió; su estado lo declaran `completo` y las alertas del snapshot, no el status
    HTTP. Las filas del cashflow no viajan en la respuesta: quien las necesita las consume vía
    `ingerir_cashflow()` directamente (F-007), no por este endpoint.

    503 es sólo para `ConfiguracionFaltante`: el servicio no está en condiciones de intentar la
    corrida porque falta una variable obligatoria, y eso se nombra en el mensaje.
    """
    try:
        resultado = await ingerir_cashflow(settings)
    except ConfiguracionFaltante as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"snapshot": resultado.snapshot.como_dict()}
