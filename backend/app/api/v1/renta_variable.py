"""Endpoints de renta variable — F-052.

Base común de la tanda 8b: el router se creó vacío y se montó en `router.py` antes de soltar los
agentes, para que F-052 no tuviera que editar un archivo que comparte con las otras tres features de
la tanda. Es la lección de la Tanda 1 — lo que colisionó no fue el código de las features, fueron
los archivos compartidos que ninguna había previsto.

**Por qué existe este módulo y no un parámetro más en `universo.py`.** La renta variable no está en
el listado del universo y no es un descuido: `segmentar()` la descarta *antes* de segmentar, porque
una acción no tiene TIR, ni duración, ni cronograma, y nunca fue comparable con un bono.
`Segmentacion.renta_variable` es un contador, no una lista — las filas se cuentan y se sueltan. Y
`EspecieUniverso` no puede representarlas: su `naturaleza` busca el segmento en `NATURALEZA_TASA` y
una acción no tiene ninguno.

Así que acá se lee aparte, con el mismo criterio que `posiciones/lectura.py` ya usa por esta misma
razón: SQL propio contra el universo consolidado, filtrando por `clase_activo`. El precedente está
escrito allá y conviene mirarlo antes de escribir el de acá.

**Lo que este recurso no va a tener nunca es una columna de rendimiento.** Ni TIR, ni nada puesto en
su lugar. Una acción no tiene TIR y presentar otra magnitud en esa columna sería exactamente lo que
la regla 2 prohíbe — y el hecho de que desde F-051 el universo de renta fija tenga TIR calculada no
cambia nada acá.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.renta_variable import armar_renta_variable, leer_renta_variable
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/renta-variable", tags=["renta variable"])


@router.get(
    "/especies",
    summary="Las acciones y CEDEARs del día, con puntas, variación y volumen en dólares",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def especies(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    clase: Annotated[
        Literal["accion", "cedear"],
        Query(description="Qué pestaña de renta variable se pide. Obligatorio: sin él, 422."),
    ],
) -> Page[dict[str, object]]:
    """Acciones o CEDEARs del universo, con precio, variación, volumen en dólares y puntas.

    El tipo de cambio sale de `sanear_universo(conn).cambio` — el MEP implícito derivado de la
    renta fija del propio universo (regla 3) — y no de ninguna otra fuente, aunque esta especie
    no sea renta fija. Una clase sin filas hoy devuelve página vacía, no 404: no es un error, es
    el estado real de la primera corrida después de que BYMA deje de publicar algo, o del primer
    día sin ninguna acción cargada.
    """
    # sólo se usa saneado.cambio: el FX del día sale del propio universo, regla 3
    saneado = await sanear_universo(conn)
    filas = await leer_renta_variable(conn)
    listado = [e for e in armar_renta_variable(filas, saneado.cambio) if e.clase_activo == clase]

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    filas_api = [e.como_dict() for e in listado[: params.limit + 1]]
    return build_page(filas_api, params.limit, lambda f: {"ticker": f["ticker"]})
