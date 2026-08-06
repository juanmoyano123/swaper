"""Endpoints del dato curado por especie — F-009.

Tres recursos y ninguno se solapa: **sembrar** es la acción que carga el artefacto curado y por eso
es un POST; **cobertura** contesta "¿de cuántas especies del universo sabemos la lámina, y por qué
lo sabemos?", que es lo que justifica la feature; y el **listado** es la tabla consultable, paginada
como cualquier colección del API.

Los conflictos no tienen recurso propio: no se persisten en ninguna tabla —el esquema de F-002 no
tiene una y esta feature no agrega migraciones— y salen enteros en la respuesta de la siembra, con
los valores en pugna. Como la semilla se relee del artefacto en cada corrida, volver a sembrar
vuelve a reportar los mismos conflictos mientras sigan en el CSV.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_db
from app.condiciones import medir_cobertura_curada, sembrar
from app.condiciones.persistencia import COLUMNAS, TABLA
from app.core.config import Settings, get_settings
from app.core.pagination import CursorParams, Page, build_page

router = APIRouter(prefix="/condiciones", tags=["condiciones"])

# Las mismas columnas que se escriben, en el mismo orden: el listado devuelve lo que la semilla
# cargó, y una segunda lista escrita a mano se desincronizaría en cuanto se agregara un campo.
SQL_LISTADO = (
    f"SELECT {', '.join(COLUMNAS)} FROM public.{TABLA} WHERE ticker > $1 ORDER BY ticker LIMIT $2"
)


@router.post(
    "/semilla",
    summary="Carga el CSV curado con herencia entre especies y detección de conflictos",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def semilla(
    conn: Annotated[object, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Siembra `condiciones_emision` y devuelve qué se cargó, con qué origen y qué quedó en pugna.

    Responde 200 aunque el artefacto no se haya podido leer: la corrida corrió y su estado lo
    declaran la cobertura y las alertas, no el status HTTP. Un artefacto ilegible no escribe nada,
    así que la tabla queda como estaba.

    Es idempotente: no hay reloj ni fuente externa en el medio, así que sembrar dos veces seguidas
    deja la tabla igual.
    """
    resultado = await sembrar(conn, settings)
    return resultado.como_dict()


@router.get(
    "/cobertura",
    summary="De cuántas especies del universo se sabe cada condición, y con qué origen",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def cobertura(conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Cobertura de los seis campos curados sobre el universo, abierta por origen.

    La apertura por origen es lo que hace auditable el conteo: cada valor presente dice si vino del
    artefacto curado o si lo heredó de otra especie de la misma emisión, y la suma de los orígenes
    de un campo da exactamente sus presentes. Ninguna fila se completa por inferencia, así que no
    hay un tercer origen posible.
    """
    medida = await medir_cobertura_curada(conn)
    return {"campos": [c.como_dict() for c in medida]}


@router.get(
    "",
    summary="Las condiciones de emisión cargadas, por especie",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def listado(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
) -> Page[dict[str, object]]:
    """Listado paginado por ticker, con el triplete completo de cada campo.

    Cada valor viaja con su origen y su fecha en la misma fila y no hay forma de pedirlo sin ellos:
    un valor curado sin decir de dónde salió es un dato sin respaldo, y el que lo consuma tiene que
    poder ver que la fecha es la del artefacto y no la del dato.
    """
    desde = params.decoded_cursor() or {}
    filas = await conn.fetch(SQL_LISTADO, str(desde.get("ticker", "")), params.limit + 1)
    return build_page([dict(f) for f in filas], params.limit, lambda f: {"ticker": f["ticker"]})
