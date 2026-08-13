"""Qué se arregla a mano y qué se arregla esperando — F-013, GWT-4.

`Alerta` ya explica en su docstring por qué "el token venció" y "la API está caída" son cosas
distintas aunque las dos dejen al producto sin ese dato: la primera necesita que alguien vaya a
regenerar un link y la segunda se destraba sola cuando la fuente vuelva. Presentarlas juntas, con
el mismo color y en la misma lista, haría que alguien espere sentado algo que nunca se va a
destrabar solo — o al revés, que salga corriendo a renovar una credencial que está perfecta.

Este módulo no clasifica nada nuevo: **lee el `codigo` que la fuente ya puso** y separa las alertas
de la última corrida en los dos montones. Volver a inferir la causa desde el texto del mensaje sería
inventar una segunda clasificación que puede contradecir a la primera.

## Por qué se reparten por código y no por `accion_requerida`

`accion_requerida` es la distinción operativa —hay algo que hacer o no lo hay— y la barra también la
muestra, pero no alcanza para el GWT-4: `formato_inesperado` también trae acción requerida y no es
una credencial vencida. El código es lo que identifica el hecho; la acción es lo que se hace con él.

**Nunca se expone la URL de la fuente.** El `detalle` viaja tal como lo dejó quien emitió la alerta,
y el contrato de `Alerta.detalle` ya prohíbe meter ahí una URL con credencial, que lleva el token
embebido. Acá no se agrega ni un campo nuevo a ese diccionario.
"""

from collections.abc import Iterable, Sequence

from app.ingesta.alertas import CODIGO_CREDENCIAL_VENCIDA, CODIGO_FUENTE_CAIDA

# Alertas de ingesta cuyo código dice qué clase de intervención hace falta. Las que no están acá no
# se clasifican: van a la lista general y se leen por su mensaje.
CODIGOS_CREDENCIAL = (CODIGO_CREDENCIAL_VENCIDA,)
CODIGOS_CAIDA = (CODIGO_FUENTE_CAIDA,)


def _con_codigo(alertas: Iterable[dict[str, object]], codigos: Sequence[str]) -> list[dict]:
    return [a for a in alertas if a.get("codigo") in codigos]


def diagnosticar(alertas: Sequence[dict[str, object]]) -> dict[str, object]:
    """Separa las alertas de una corrida en los dos montones que se arreglan distinto.

    Recibe las alertas ya serializadas —así vienen de `corridas_ingesta`, que las guarda como
    `jsonb`— y devuelve las mismas alertas, sin reescribirlas, repartidas.

    `requiere_intervencion` mira `accion_requerida` sobre **todas** las alertas y no sólo sobre las
    dos categorías de acá: es la pregunta que la barra contesta de un vistazo —"¿hay algo que
    alguien tenga que hacer hoy?"— y responderla mirando sólo las credenciales dejaría afuera, por
    ejemplo, un formato de fuente que cambió.
    """
    credenciales = _con_codigo(alertas, CODIGOS_CREDENCIAL)
    caidas = _con_codigo(alertas, CODIGOS_CAIDA)
    return {
        "credenciales_vencidas": credenciales,
        "caidas": caidas,
        "hay_credencial_vencida": bool(credenciales),
        "hay_fuente_caida": bool(caidas),
        "requiere_intervencion": any(a.get("accion_requerida") for a in alertas),
    }
