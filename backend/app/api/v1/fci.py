"""Endpoints de fondos comunes de inversión — F-057.

Ninguno pasa por `sanear_universo` ni por `/universo/segmentos`: `public.fci` es una tabla propia,
sin puntas, sin volumen y sin tipo de cambio implícito que aplicarle — un FCI no cotiza en dos
monedas, así que no hay cociente del cual derivar nada (regla 3, ver F-046).
"""

from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.fci import fondo_de_fila, leer_fondo, leer_fondos, leer_planilla, leer_segmentos, planilla_como_dict

router = APIRouter(prefix="/fci", tags=["fci"])


@router.get(
    "/segmentos",
    summary="Los tipos de renta de FCI presentes hoy, con la planilla que los sostiene",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def segmentos(conn: Annotated[asyncpg.Connection, Depends(get_db)]) -> dict[str, object]:
    """Un tipo de renta por fila, con cuántos fondos tiene y en qué monedas — el equivalente de
    `/universo/segmentos` para renta fija, pero sin naturaleza de tasa: todos comparten la misma,
    `variacion_cuotaparte` (F-057, regla 2).

    El bloque `planilla` es `None` si la ingesta nunca corrió (`CAFCI_HABILITADO=false`, el
    default): el frontend lo distingue de una planilla vacía por dato de mercado.
    """
    filas = await leer_segmentos(conn)
    planilla = await leer_planilla(conn)
    return {
        "segmentos": [
            {"tipo_renta": f["tipo_renta"], "cantidad": f["cantidad"], "monedas": list(f["monedas"])}
            for f in filas
        ],
        "planilla": planilla_como_dict(planilla),
    }


@router.get(
    "/fondos",
    summary="Los fondos comunes de inversión de hoy, paginados",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def fondos(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    tipo_renta: str | None = None,
    moneda: str | None = None,
) -> Page[dict[str, object]]:
    """Sin `tipo_renta` ni `moneda` devuelve todos los fondos — el picker de F-046 y el comparador
    de F-067 los necesitan sin filtrar por segmento."""
    filas = await leer_fondos(conn, tipo_renta=tipo_renta, moneda=moneda)
    listado = [fondo_de_fila(f) for f in filas]

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("codigo_cafci", ""))
        listado = [f for f in listado if f.codigo_cafci > ultimo]

    filas_api = [f.como_dict() for f in listado[: params.limit + 1]]
    return build_page(filas_api, params.limit, lambda f: {"codigo_cafci": f["codigo_cafci"]})


@router.get(
    "/{codigo_cafci}/ficha",
    summary="El detalle de un fondo: costos, sociedad gerente y depositaria, códigos",
    responses={
        404: {"description": "El código no está en la planilla de hoy"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def ficha(
    codigo_cafci: str,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict[str, object]:
    fila = await leer_fondo(conn, codigo_cafci.strip())
    if fila is None:
        raise HTTPException(404, detail=f"{codigo_cafci} no está en la planilla de hoy")
    return fondo_de_fila(fila).como_dict()
