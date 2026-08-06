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
CODIGO_CONDICIONES_EN_CONFLICTO = "condiciones_en_conflicto"
CODIGO_ESPECIE_INCOHERENTE = "especie_incoherente"
CODIGO_RENDIMIENTO_FUERA_DE_RANGO = "rendimiento_fuera_de_rango"


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


def condiciones_en_conflicto(
    campo: str, raiz: str, valores: dict[str, object], **detalle: object
) -> Alerta:
    """Dos especies de la misma emisión declaran valores distintos para un atributo que, por
    definición, comparten. F-009.

    El sistema **no elige**: vacía las dos y lo reporta con los valores en pugna. Elegir requeriría
    un criterio de precedencia entre fuentes que nadie estableció, y aplicarlo por cuenta propia
    sería presentar una preferencia inventada como si fuera el dato. Es la regla 1 del proyecto:
    si falta o si está en disputa, se deja vacío y se alerta con nombre y apellido.
    """
    en_pugna = ", ".join(f"{ticker}={valor!r}" for ticker, valor in sorted(valores.items()))
    return Alerta(
        codigo=CODIGO_CONDICIONES_EN_CONFLICTO,
        mensaje=(
            f"La emisión {raiz} declara {campo} distinto según la especie ({en_pugna}): "
            f"se vacía en todas y no se elige ninguno."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            f"Resolver a mano cuál es el {campo} de {raiz} y corregirlo en la semilla curada."
        ),
        detalle={"campo": campo, "raiz": raiz, "valores": valores, **detalle},
    )


def especie_incoherente(cantidad: int, tickers: list[str], **detalle: object) -> Alerta:
    """Capa 1 de la sanidad (F-010): una especie se despega de las otras del mismo bono.

    Un bono tiene UNA TIR. Cuando una especie declara más de 100 pp de diferencia contra sus
    hermanas, lo que está mal es el precio de esa especie, no el rendimiento del bono: VSCQD
    figuraba con 34.627.917 % mientras VSCQO, el mismo bono, rendía 6,75 %. El resto de las
    especies de esa emisión sigue disponible.
    """
    return Alerta(
        codigo=CODIGO_ESPECIE_INCOHERENTE,
        mensaje=(
            f"{cantidad} especies declaran un rendimiento incoherente contra las otras especies "
            f"del mismo bono ({', '.join(tickers[:6])}): su precio está mal escalado en la fuente."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"cantidad": cantidad, "tickers": tickers, **detalle},
    )


def rendimiento_fuera_de_rango(cantidad: int, tickers: list[str], **detalle: object) -> Alerta:
    """Capa 2 de la sanidad (F-010): el rendimiento supera el techo de lo posible de su segmento.

    El tope se compara **en la unidad de cada segmento** —300 % de TIR en dólares, 100 % de tasa
    real sobre CER, 500 % de TNA nominal en pesos— porque un tope único cruzaría naturalezas de
    tasa que no son la misma magnitud. Son holgados a propósito: tienen que dejar pasar el distress
    real, como SNSBO al 245 % en dólares, que es dato correcto.
    """
    return Alerta(
        codigo=CODIGO_RENDIMIENTO_FUERA_DE_RANGO,
        mensaje=(
            f"{cantidad} instrumentos declaran un rendimiento por encima del techo de su segmento "
            f"({', '.join(tickers[:6])}): no puede ser cierto en esa unidad de tasa."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"cantidad": cantidad, "tickers": tickers, **detalle},
    )
