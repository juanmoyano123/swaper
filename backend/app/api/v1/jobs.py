"""Endpoints del job programado de ingesta (F-008).

El scheduler corre solo cuando `ingesta_habilitada=True`, así que estos endpoints también sirven
para disparar una corrida a mano en desarrollo o para forzar un refresh puntual en producción —el
mismo criterio que ya usa `POST /api/v1/consolidar` para la corrida matinal completa.
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.externos import cliente_yahoo
from app.jobs.corridas import corrida_matinal, refresh_intra_rueda
from app.jobs.registro import listar_corridas
from app.renta_variable import enriquecer_perfiles
from app.renta_variable.enriquecimiento import LIMITE_POR_CORRIDA

router = APIRouter(prefix="/jobs", tags=["jobs"])

LIMITE_MAXIMO = 100
LIMITE_POR_DEFECTO = 20


@router.get(
    "/corridas",
    summary="Historial de corridas del job de ingesta",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def corridas(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_POR_DEFECTO,
) -> list[dict[str, object]]:
    """Las corridas más recientes primero, con hora, duración, filas por fuente y alertas.

    Es lo que F-013 va a consumir para la barra de estado del dato. `limite` tiene tope para que
    nadie pida el historial entero por accidente.
    """
    return await listar_corridas(conn, limite=min(limite, LIMITE_MAXIMO))


@router.post(
    "/corridas/matinal",
    summary="Dispara a mano la corrida matinal completa (BYMA + data912 + IAMC + consolidación)",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def disparar_matinal(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    return await corrida_matinal(conn, settings)


@router.post(
    "/corridas/refresh",
    summary="Dispara a mano un refresh intra-rueda (sólo precios y puntas de BYMA)",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def disparar_refresh(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    return await refresh_intra_rueda(conn, settings)


@router.post(
    "/perfiles-renta-variable",
    summary=(
        "Enriquece nombre, sector, industria y país de acciones y CEDEARs pendientes, contra "
        "Yahoo Finance"
    ),
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def disparar_enriquecimiento_renta_variable(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_POR_CORRIDA,
) -> dict[str, object]:
    """Incremental: procesa hasta `limite` tickers pendientes por corrida, corta al primer 429 de
    la fuente y deja el resto para la próxima invocación (ver
    `app/renta_variable/enriquecimiento.py`)."""
    resumen = await enriquecer_perfiles(conn, cliente_yahoo(), limite=limite)
    return resumen.como_dict()
