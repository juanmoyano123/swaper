"""Endpoints agregados de FCI — F-067 (categorías, gestoras).

Router montado vacío junto con la base común de la Tanda 2 (23/08/2026), antes de soltar los
agentes de F-067 y F-046 en paralelo: mismo criterio que `renta_variable.py` en la Tanda 8b — el
archivo que ambas features comparten (`router.py`) se toca una sola vez, a mano, para que ninguna
de las dos tenga que editarlo.
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.fci import agregados_por_categoria, agregados_por_gestora, fondo_de_fila, leer_fondos

router = APIRouter(prefix="/fci/agregados", tags=["fci"])


@router.get(
    "/categorias",
    summary="AUM y participación de cada fondo, agrupado por tipo de renta y moneda",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def categorias(conn: Annotated[asyncpg.Connection, Depends(get_db)]) -> dict[str, object]:
    """Un bloque por tipo de renta, roto por moneda dentro: el AUM y la participación de cada
    fondo se calculan contra el total de su propia moneda, nunca contra un total que mezcle
    monedas (regla 3)."""
    filas = await leer_fondos(conn)
    fondos = [fondo_de_fila(f) for f in filas]
    return {"categorias": agregados_por_categoria(fondos)}


@router.get(
    "/gestoras",
    summary="AUM por moneda, cantidad de fondos y market share por sociedad gerente",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def gestoras(conn: Annotated[asyncpg.Connection, Depends(get_db)]) -> dict[str, object]:
    """Un bloque por `gerente` tal cual viene en la planilla, sin normalizar grafías. El flujo
    neto a 30 días y en el año no se calcula —el producto no acumula planillas históricas— y
    viaja siempre declarado como no disponible, nunca omitido."""
    filas = await leer_fondos(conn)
    fondos = [fondo_de_fila(f) for f in filas]
    return {"gestoras": agregados_por_gestora(fondos)}
