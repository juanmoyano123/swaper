"""Ruta que dispara la consolidación multi-fuente — F-007.

Es el disparo manual de la corrida completa. F-008 va a llamar a `consolidar()` directamente desde
su job, sin pasar por HTTP, que es la razón por la que la función recibe la conexión por parámetro
en vez de sacarla del estado de la app.

**Fuera de la rueda hay que pedirlo explícitamente** (08/08/2026). Correr esto con el mercado
cerrado no falla: BYMA responde un universo parcial, se escribe igual, y el snapshot pasa a declarar
frescura de hoy sobre datos de la última rueda de verdad. Ya pasó —una corrida un sábado escribió
466 filas sin un solo precio— y el costo no es el ruido sino la mentira del indicador. Por eso el
default es no correr, y forzarlo es un acto deliberado que queda en el log.
"""

from datetime import UTC, datetime
from typing import Annotated

import asyncpg
import structlog
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.ingesta.consolidacion import consolidar
from app.jobs.horarios import FueraDeLaRueda, en_ventana_de_rueda

logger = structlog.get_logger()

router = APIRouter(tags=["consolidacion"])


@router.post(
    "/consolidar",
    summary="Une BYMA, IAMC y Docta en las tablas de mercado",
    responses={
        409: {"description": "Fuera de la ventana de rueda y sin `forzar`"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def consolidacion(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    forzar: Annotated[
        bool,
        Query(
            description=(
                "Correr aunque el mercado esté cerrado. Degrada el snapshot: usar a propósito."
            )
        ),
    ] = False,
) -> dict[str, object]:
    """Corre la consolidación y devuelve qué se escribió, con qué cobertura y qué salió mal.

    Responde 200 aunque una fuente no haya estado disponible: la corrida corrió y su estado lo
    declaran los snapshots y las alertas, no el status HTTP. Un 503 significa otra cosa —que no hay
    dónde escribir— y ahí no tiene sentido molestar a las fuentes.

    Responde **409 fuera de la ventana de rueda** salvo que se pase `forzar=true`. No es una
    validación de entrada —de ahí que no sea 422—: el pedido está bien formado y el servicio está
    sano; lo que no está es el mercado. Con `forzar` corre igual, porque probar la ingesta un
    domingo es legítimo mientras sea una decisión y no un accidente.

    Las filas no viajan en la respuesta: son miles y ya quedaron en la base. Lo que viaja es lo que
    hace falta para saber si la corrida sirve —conteos por tabla, cobertura por campo y alertas—,
    el mismo criterio que los endpoints de las tres fuentes.
    """
    en_rueda = en_ventana_de_rueda(datetime.now(UTC), settings)
    if not en_rueda and not forzar:
        raise FueraDeLaRueda(
            "El mercado está cerrado: la rueda va de "
            f"{settings.ingesta_rueda_desde} a {settings.ingesta_rueda_hasta} "
            f"({settings.ingesta_zona_horaria}), de lunes a viernes. Correr ahora escribiría un "
            "universo parcial y el indicador de frescura pasaría a declarar hoy sobre datos de la "
            "última rueda. Reintentar en horario, o pasar `forzar=true` a propósito."
        )
    if forzar and not en_rueda:
        logger.warning("consolidacion_forzada_fuera_de_rueda")

    resultado = await consolidar(conn, settings)
    return resultado.como_dict()
