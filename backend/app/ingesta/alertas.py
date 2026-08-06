"""Lo que salió mal en una corrida, dicho de forma que se sepa qué hacer al respecto.

Una alerta no es un mensaje de error: es un aviso operativo dirigido a alguien que tiene que decidir
algo. Por eso lleva `accion_requerida` separada del mensaje. La diferencia entre "el token venció" y
"la API está caída" no está en la gravedad —las dos dejan al producto sin ese dato— sino en que la
primera se arregla regenerando un link a mano y la segunda se arregla esperando. Presentarlas igual
haría que alguien espere sentado a que se destrabe algo que nunca se va a destrabar solo.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Severidad(StrEnum):
    """Cuánto duele. Ordenadas de menor a mayor para poder comparar y priorizar."""

    INFO = "info"
    """Vale la pena saberlo, no cambia nada de lo que se puede hacer con el dato."""

    ADVERTENCIA = "advertencia"
    """La corrida sirve pero salió incompleta: falta una fuente, un campo o un tramo."""

    ERROR = "error"
    """Esta fuente no aportó nada en esta corrida."""


# Códigos que las fuentes comparten. Cada cliente puede definir los suyos, pero éstos aparecen en
# más de una y conviene que se escriban igual en todas.
CODIGO_FUENTE_CAIDA = "fuente_no_disponible"
CODIGO_CREDENCIAL_VENCIDA = "credencial_vencida"
CODIGO_RESPUESTA_VACIA = "respuesta_vacia"
CODIGO_FORMATO_INESPERADO = "formato_inesperado"
CODIGO_CAMPO_SIN_COBERTURA = "campo_sin_cobertura"


@dataclass(frozen=True, slots=True)
class Alerta:
    """Un aviso de una corrida de ingesta.

    `codigo` es para el código que decide (agrupar, contar, filtrar); `mensaje` y
    `accion_requerida` son para la persona que lo lee.
    """

    codigo: str
    mensaje: str
    severidad: Severidad = Severidad.ADVERTENCIA
    accion_requerida: str | None = None
    """Qué tiene que hacer una persona. `None` significa que no hay nada que hacer a mano."""

    detalle: dict[str, object] = field(default_factory=dict)
    """Contexto para depurar: endpoint, cantidad de filas, código de status. **Nunca credenciales**
    ni URLs con token embebido: esto se serializa al log y a la respuesta de la API."""

    def como_dict(self) -> dict[str, object]:
        return {
            "codigo": self.codigo,
            "mensaje": self.mensaje,
            "severidad": self.severidad.value,
            "accion_requerida": self.accion_requerida,
            "detalle": self.detalle,
        }


def fuente_caida(fuente: str, motivo: str, **detalle: object) -> Alerta:
    """La fuente no respondió o respondió mal. Se resuelve sola cuando la fuente vuelva."""
    return Alerta(
        codigo=CODIGO_FUENTE_CAIDA,
        mensaje=f"{fuente} no está disponible: {motivo}.",
        severidad=Severidad.ERROR,
        accion_requerida=None,
        detalle=detalle,
    )


def credencial_vencida(fuente: str, como_renovarla: str, **detalle: object) -> Alerta:
    """La fuente contestó que no nos reconoce. No se arregla esperando: alguien tiene que actuar."""
    return Alerta(
        codigo=CODIGO_CREDENCIAL_VENCIDA,
        mensaje=f"La credencial de {fuente} no es válida.",
        severidad=Severidad.ERROR,
        accion_requerida=como_renovarla,
        detalle=detalle,
    )


def respuesta_vacia(fuente: str, intentos: int, **detalle: object) -> Alerta:
    return Alerta(
        codigo=CODIGO_RESPUESTA_VACIA,
        mensaje=f"{fuente} devolvió cero filas tras {intentos} intentos.",
        severidad=Severidad.ERROR,
        accion_requerida=None,
        detalle=detalle,
    )


def formato_inesperado(fuente: str, que_falta: str, **detalle: object) -> Alerta:
    """La fuente cambió lo que entrega. Nadie lo avisa: se descubre así."""
    return Alerta(
        codigo=CODIGO_FORMATO_INESPERADO,
        mensaje=f"{fuente} devolvió un formato inesperado: {que_falta}.",
        severidad=Severidad.ERROR,
        accion_requerida=f"Revisar si {fuente} cambió su contrato y actualizar el cliente.",
        detalle=detalle,
    )


def campo_sin_cobertura(campo: str, total: int, **detalle: object) -> Alerta:
    """Ninguna fila del universo tiene este campo. Distinto de tenerlo poco: no lo tiene nadie.

    Un campo que está en el esquema, que alguien lee y que ninguna fuente llena es la forma más
    silenciosa de perder información: las consultas siguen funcionando y devuelven vacío. Que sea
    una alerta y no una línea de log es lo que hace que se vea en la respuesta de la corrida.
    """
    return Alerta(
        codigo=CODIGO_CAMPO_SIN_COBERTURA,
        mensaje=f"Ninguna de las {total} filas trae {campo}: ninguna fuente lo publica hoy.",
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"campo": campo, "total": total, **detalle},
    )
