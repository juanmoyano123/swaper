"""De dónde sale el `index-price` con el que se contrasta el tipo de cambio — F-012.

**Decisión: se pide vivo a BYMA en el momento, no se persiste.** El porqué, en orden:

1. **Persistirlo sería un cambio de esquema, y F-007 lo dejó afuera a propósito** (`FilaIndice`
   viaja en `ResultadoRueda.indices` y no tiene tabla). Agregarla desde acá sería tomar por cuenta
   propia una decisión sobre el modelo de datos que se tomó explícitamente en otra feature.
2. **El contraste es un control de hoy sobre un número de hoy.** El implícito se deriva de los
   precios de la última corrida; el índice contra el que se lo compara tiene que ser del mismo
   momento. Un índice guardado ayer contrastaría dos ruedas distintas y la diferencia hablaría del
   paso del tiempo, no de un error.
3. **Es una sola llamada y sin token.** `index-price` devuelve 16 filas, la API abierta de BYMA no
   lleva credencial, y el resto de la ingesta no hace falta traerlo para esto.

**Nada de acá puede romper el cálculo del implícito.** Cualquier fallo —endpoint caído, respuesta
vacía, formato inesperado— devuelve una lista vacía, y sin índices el contraste queda en `None` con
su alerta. El implícito sale del universo y no necesita a BYMA para existir.
"""

from typing import Any

import structlog

from app.core.config import Settings, get_settings
from app.ingesta.byma.cliente import ENDPOINT_INDICE, descargar_endpoint
from app.ingesta.byma.normalizacion import FilaIndice, normalizar_fila_indice
from app.ingesta.http import crear_cliente

logger = structlog.get_logger()


async def leer_indices(settings: Settings | None = None) -> list[FilaIndice]:
    """Las filas de `index-price`, o una lista vacía si BYMA no las dio.

    Se atrapa `Exception` y no un conjunto de excepciones nombradas porque acá el criterio no es
    *qué* falló sino *que no puede propagarse*: esto es un control opcional colgado de un cálculo
    que ya está hecho, y una excepción que suba dejaría al producto sin tipo de cambio por no haber
    podido verificarlo. El motivo se registra en el log para que el fallo no quede mudo.
    """
    settings = settings or get_settings()
    try:
        async with crear_cliente() as cliente:
            descarga = await descargar_endpoint(cliente, settings.byma_base_url, ENDPOINT_INDICE)
    except Exception as exc:  # el contraste no puede tumbar el cálculo; ver el docstring
        _registrar_fallo(exc)
        return []
    return [normalizar_fila_indice(fila) for fila in descarga.filas]


def _registrar_fallo(exc: Any) -> None:
    """El fallo se nombra por su tipo y su motivo. **Nunca la URL**: es la regla de siempre."""
    logger.warning(
        "indice_de_contraste_no_disponible",
        endpoint=ENDPOINT_INDICE,
        error=type(exc).__name__,
        motivo=getattr(exc, "motivo", None),
    )
