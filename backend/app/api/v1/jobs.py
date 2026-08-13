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
from app.externos.sec import ClienteSec
from app.ingesta.byma.cedears import traer_lista
from app.jobs.corridas import corrida_matinal, refresh_intra_rueda
from app.jobs.registro import listar_corridas
from app.renta_variable import enriquecer_perfiles
from app.renta_variable.agrupamiento import agrupar
from app.renta_variable.clasificacion import (
    LIMITE_POR_CORRIDA as LIMITE_CLASIFICACION,
)
from app.renta_variable.clasificacion import (
    DatosDeBymaPorPapel,
    clasificar_renta_variable,
)
from app.renta_variable.enriquecimiento import LIMITE_POR_CORRIDA
from app.renta_variable.lectura import leer_renta_variable

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


@router.post(
    "/clasificar-renta-variable",
    summary=(
        "Clasifica acciones y CEDEARs contra la SEC: actividad, eslabón de la cadena productiva "
        "y estrategia si es un fondo"
    ),
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def disparar_clasificacion_renta_variable(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_CLASIFICACION,
) -> dict[str, object]:
    """Incremental, como el de Yahoo: procesa hasta `limite` papeles por corrida y retoma después.

    Se clasifica **por papel y no por especie** — `AAPL` una vez, y `AAPLC`/`AAPLD` heredan su
    clasificación—, así que primero se arma el mapa de especie a papel con el mismo agrupamiento
    que usa el universo.

    La lista de CEDEARs de BYMA es opcional y aporta nombre y ratio: si no se pudo bajar, la
    clasificación sigue con lo que da la SEC y lo que falte queda declarado.
    """
    filas = await leer_renta_variable(conn)
    tickers = {str(f["ticker"]) for f in filas}
    grupos = agrupar(tickers)
    por_papel = {t: g.emision for t, g in grupos.items() if not g.no_identificado}

    lista = await traer_lista()
    datos_byma = {
        codigo: DatosDeBymaPorPapel(nombre=c.nombre, ratio=c.ratio, mercado=c.mercado)
        for codigo, c in lista.cedears.items()
    }

    resumen = await clasificar_renta_variable(
        conn,
        ClienteSec(),
        por_papel=por_papel,
        datos_byma=datos_byma,
        limite=limite,
    )
    return resumen.como_dict()
