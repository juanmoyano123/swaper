"""Endpoints del universo saneado — F-010, y después F-011 y F-012.

Las tres features que envuelven `tools/segmentos.py` —sanidad, deduplicación y tipo de cambio
implícito— exponen el mismo universo bajo este prefijo, y por eso el plan las serializa: son tres
vistas del mismo servicio, no tres servicios.

**El resumen y los descartes son dos recursos y no uno.** El resumen contesta "¿sirve el universo de
hoy?" y es lo que mira una corrida; el listado de descartes contesta "¿por qué no está VSCQD?" y es
lo que mira alguien auditando un caso. Meterlos juntos obligaría a devolver la colección entera en
cada chequeo de salud, que es exactamente lo que la paginación por cursor existe para evitar.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.universo import MotivoDescarte
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/universo", tags=["universo"])


@router.get(
    "/sanidad",
    summary="Cuánto del universo de hoy es dato confiable",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def sanidad(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Corre las dos capas sobre el universo del día y devuelve los conteos y las alertas.

    El desglose viene abierto por segmento a propósito: un descarte sólo se lee contra su unidad de
    tasa, y un total único mezclaría una TIR en dólares con una TNA nominal en pesos.

    Los instrumentos descartados **siguen en el universo**. Lo que dice este endpoint es cuáles no
    se proponen y por qué; ninguno se corrige ni se estima.
    """
    saneado = await sanear_universo(conn)
    return saneado.como_dict()


@router.get(
    "/sanidad/descartes",
    summary="Qué instrumentos no se proponen, con su motivo y el valor que lo disparó",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def descartes(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    motivo: Annotated[
        MotivoDescarte | None,
        Query(description="Filtra por capa: coherencia entre especies o techo por segmento."),
    ] = None,
) -> Page[dict[str, object]]:
    """El listado auditable: ticker, motivo, valor declarado y contra qué se comparó.

    Ordenado por ticker, que además es la clave del cursor: la sanidad es determinística sobre el
    universo del día, así que dos páginas consecutivas ven el mismo listado salvo que haya entrado
    una corrida nueva en el medio — y en ese caso lo correcto es ver el universo nuevo, no una foto
    del anterior.
    """
    saneado = await sanear_universo(conn)
    listado = saneado.descartes if motivo is None else saneado.sanidad.por_motivo(motivo)

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [d for d in listado if d.ticker > ultimo]

    filas = [d.como_dict() for d in listado[: params.limit + 1]]
    return build_page(filas, params.limit, lambda f: {"ticker": f["ticker"]})
