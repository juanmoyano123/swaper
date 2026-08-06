"""Ruta que dispara la consolidación multi-fuente — F-007.

Es el disparo manual de la corrida completa. F-008 va a llamar a `consolidar()` directamente desde
su job, sin pasar por HTTP, que es la razón por la que la función recibe la conexión por parámetro
en vez de sacarla del estado de la app.
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.ingesta.consolidacion import consolidar

router = APIRouter(tags=["consolidacion"])


@router.post(
    "/consolidar",
    summary="Une BYMA, IAMC y Docta en las tablas de mercado",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def consolidacion(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Corre la consolidación y devuelve qué se escribió, con qué cobertura y qué salió mal.

    Responde 200 aunque una fuente no haya estado disponible: la corrida corrió y su estado lo
    declaran los snapshots y las alertas, no el status HTTP. Un 503 significa otra cosa —que no hay
    dónde escribir— y ahí no tiene sentido molestar a las fuentes.

    Las filas no viajan en la respuesta: son miles y ya quedaron en la base. Lo que viaja es lo que
    hace falta para saber si la corrida sirve —conteos por tabla, cobertura por campo y alertas—,
    el mismo criterio que los endpoints de las tres fuentes.
    """
    resultado = await consolidar(conn, settings)
    return resultado.como_dict()
