"""El recurso que alimenta la barra de estado del dato — F-013.

**Es el endpoint más pedido del producto**: la barra está en las seis pantallas y se consulta en
cada carga. Todo lo que se agregue acá lo paga el producto entero, así que el criterio para sumar
un campo no es "sería útil verlo" sino "sin esto la barra no puede decir si el dato sirve". Lo que
es útil pero caro va a su propio recurso, que alguien abre a propósito: los descartes completos
están en `/universo/sanidad/descartes`, la grilla del calendario en `/calendario/universo` y el
contraste del tipo de cambio en `/universo/tipo-de-cambio`.

El costo está medido y documentado en `app/estado/analisis.py`. En dos líneas: dos consultas de una
fila en cada request, y el análisis del universo entero una sola vez por corrida de ingesta.

## Por qué no pide sesión

La barra se dibuja en el layout, antes y por fuera de cualquier pantalla, y lo que declara es el
estado del **dato de mercado**, que es común a todos los asesores y no contiene información de
ninguna cartera. Pedir sesión acá no protegería nada y haría que la pantalla de login —la única sin
sesión— fuera la única que no puede decir si el backend tiene datos.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.estado.analisis import CacheDelAnalisis
from app.estado.servicio import estado_del_dato

router = APIRouter(prefix="/estado-del-dato", tags=["estado del dato"])


def get_cache(request: Request) -> CacheDelAnalisis:
    """El caché del análisis, uno por aplicación, creado en el primer request que lo necesite.

    Vive en `app.state` y no como global de módulo por lo mismo que el pool: dos aplicaciones en el
    mismo proceso —las que arma cada test— tienen que poder no compartirlo. Se crea perezosamente y
    no en el `lifespan` porque no tiene nada que abrir ni que cerrar, y ponerlo allá obligaría a que
    cualquier test que use este endpoint levante el ciclo de vida completo.
    """
    cache = getattr(request.app.state, "cache_estado", None)
    if cache is None:
        cache = CacheDelAnalisis()
        request.app.state.cache_estado = cache
    return cache


@router.get(
    "",
    summary="Todo lo que hace falta para saber si se puede confiar en el dato de hoy",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def estado(
    conn: Annotated[object, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    cache: Annotated[CacheDelAnalisis, Depends(get_cache)],
) -> dict[str, object]:
    """La hora del dato con su demora, la última corrida, la cobertura y todas las alertas.

    **La hora que viaja es la del snapshot, no la del reloj.** `dato.capturado_en` es cuándo se
    capturó el precio más nuevo de la base y `dato.dato_valido_hasta` es ese momento menos los 20
    minutos que BYMA declara de retraso: un snapshot de las 11:00 mirado a las 11:15 sigue diciendo
    11:00 y sigue declarando la demora. La hora en que se armó esta respuesta va aparte, en
    `consultado_en`, y no reemplaza a ninguna de las otras dos.

    `alertas` es la lista completa y estructurada —la que hasta hoy se acumulaba en una hoja
    "Alertas" del Excel— ordenada de la más urgente a la menos, y dentro de cada nivel con las que
    esperan que alguien haga algo primero. `fuentes` separa las dos que se arreglan distinto: una
    credencial vencida necesita que alguien la renueve, una fuente caída se destraba sola.
    """
    resultado = await estado_del_dato(conn, settings, cache=cache)
    return resultado.como_dict()
