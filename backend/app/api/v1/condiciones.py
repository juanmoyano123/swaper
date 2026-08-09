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

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.condiciones import medir_cobertura_curada, sembrar
from app.condiciones.carga_manual import cargar_lamina_manual
from app.condiciones.persistencia import COLUMNAS, TABLA, fila_para_api
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
    return build_page(
        [fila_para_api(f) for f in filas], params.limit, lambda f: {"ticker": f["ticker"]}
    )


class CargaManualLamina(BaseModel):
    valor: Annotated[float, Field(gt=0)]


@router.post(
    "/{ticker}/lamina",
    summary="Carga manual de la lámina de una especie, con trazabilidad y propagación",
    response_model=None,
    responses={
        409: {"description": "La lámina cargada contradice un valor de otro origen"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def cargar_lamina(
    ticker: str,
    cuerpo: CargaManualLamina,
    conn: Annotated[object, Depends(get_db)],
) -> dict[str, object] | JSONResponse:
    """Carga la lámina de `ticker` a mano y la propaga a las demás especies de la misma emisión.

    200 cuando `resolver()` resuelve sin conflicto: el triplete final guardado. 409 —no 500— cuando
    la lámina cargada contradice un valor ya declarado de otro origen: es un resultado válido del
    dominio (F-009), no un error de servidor, y el cuerpo trae los dos valores en pugna con sus
    orígenes para que el frontend los muestre tal cual.
    """
    resultado = await cargar_lamina_manual(conn, ticker, cuerpo.valor, date.today())

    if not resultado.guardado:
        conflicto = resultado.conflicto.como_dict() if resultado.conflicto is not None else None
        return JSONResponse(
            status_code=409,
            content={"guardado": False, "ticker": resultado.ticker, "conflicto": conflicto},
        )

    return {
        "guardado": True,
        "ticker": resultado.ticker,
        "lamina": resultado.lamina,
        "lamina_origen": resultado.origen,
        "lamina_fecha": resultado.fecha.isoformat() if resultado.fecha is not None else None,
    }
