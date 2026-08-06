"""Cliente HTTP para las fuentes de mercado, con la política de reintentos que exige la realidad.

La lógica viene de `tools/consolidar_universo.py`, donde está probada contra la fuente real desde
hace meses. Lo que se conserva y por qué:

**Una respuesta vacía cuenta como fallo y se reintenta.** No es una regla de días hábiles ni de
horarios: es inestabilidad medida del endpoint — la misma consulta que devuelve cero filas trae
1.660 segundos después. Tratar el vacío como un resultado legítimo dejaba el pipeline sin datos sin
que nada fallara, que es la peor forma de romperse.

**La espera crece entre intentos** (3, 6, 9, 12 segundos). Reintentar de inmediato contra un
endpoint que se está recuperando lo empuja de nuevo.

**El timeout es amplio**, 90 segundos: una ventana de quince días con todas las columnas tarda unos
25 en responder, y cortar antes convierte una consulta lenta en un error.

**Una credencial vencida no se reintenta.** Ninguna cantidad de intentos la va a arreglar; hay que
avisar y salir.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

INTENTOS_POR_DEFECTO = 5
TIMEOUT_POR_DEFECTO = 90.0
ESPERA_BASE_SEGUNDOS = 3


class ErrorDeFuente(Exception):
    """La fuente no entregó el dato. Lleva el motivo para poder convertirlo en alerta."""

    def __init__(self, motivo: str, *, reintentable: bool = True, status: int | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.reintentable = reintentable
        self.status = status


class CredencialVencida(ErrorDeFuente):
    """La fuente no nos reconoce. Se arregla a mano, no esperando."""

    def __init__(self, motivo: str, status: int | None = None):
        super().__init__(motivo, reintentable=False, status=status)


@dataclass(slots=True)
class Reintentos:
    intentos: int = INTENTOS_POR_DEFECTO
    espera_base: int = ESPERA_BASE_SEGUNDOS

    def espera(self, intento: int) -> float:
        """Espera creciente: 3, 6, 9, 12 segundos."""
        return self.espera_base * intento


async def con_reintentos[T](
    operacion: Callable[[], Awaitable[T]],
    *,
    descripcion: str,
    politica: Reintentos | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Ejecuta `operacion` reintentando lo que valga la pena reintentar.

    `dormir` es inyectable para que los tests no esperen de verdad.
    """
    politica = politica or Reintentos()
    ultimo: ErrorDeFuente | None = None

    for intento in range(1, politica.intentos + 1):
        try:
            resultado = await operacion()
        except ErrorDeFuente as exc:
            if not exc.reintentable:
                raise
            ultimo = exc
        else:
            if intento > 1:
                logger.info("fuente_respondio_tras_reintentos", fuente=descripcion, intento=intento)
            return resultado

        if intento < politica.intentos:
            await dormir(politica.espera(intento))

    motivo = ultimo.motivo if ultimo else "sin respuesta"
    raise ErrorDeFuente(
        f"{motivo} tras {politica.intentos} intentos",
        status=ultimo.status if ultimo else None,
    )


def _detectar_credencial_vencida(status: int, cuerpo: bytes) -> bool:
    """Distingue "no te reconozco" de "me caí".

    No alcanza con mirar el código: la fuente de cashflow responde **500** cuando el token venció,
    no 401, y un 500 genérico sí es reintentable. Lo que las separa es que el cuerpo menciona el
    token. Es feo y es lo que hay: está verificado contra la fuente real.
    """
    if status in (401, 403):
        return True
    if status == 500:
        texto = cuerpo[:200].decode("utf-8", "replace").lower()
        return "token" in texto
    return False


async def pedir(
    cliente: httpx.AsyncClient,
    metodo: str,
    url: str,
    *,
    fuente: str,
    json: Any | None = None,
    vacio_es_fallo: Callable[[httpx.Response], bool] | None = None,
) -> httpx.Response:
    """Un intento contra la fuente. Traduce todo lo que puede salir mal a `ErrorDeFuente`.

    `url` nunca se loguea: las de la fuente de cashflow llevan el token en la query string, y el
    redactor de secretos del logger no tapa un campo llamado `url`.
    """
    try:
        respuesta = await cliente.request(metodo, url, json=json)
    except httpx.TimeoutException as exc:
        raise ErrorDeFuente(f"timeout ({exc.__class__.__name__})") from exc
    except httpx.HTTPError as exc:
        raise ErrorDeFuente(f"no se pudo conectar ({exc.__class__.__name__})") from exc

    if _detectar_credencial_vencida(respuesta.status_code, respuesta.content):
        raise CredencialVencida(
            f"{fuente} rechazó la credencial (HTTP {respuesta.status_code})",
            status=respuesta.status_code,
        )

    if respuesta.status_code >= 500:
        raise ErrorDeFuente(f"HTTP {respuesta.status_code}", status=respuesta.status_code)

    if respuesta.status_code >= 400:
        # Un 4xx que no es de credencial no se arregla reintentando: el pedido está mal armado.
        raise ErrorDeFuente(
            f"HTTP {respuesta.status_code}", reintentable=False, status=respuesta.status_code
        )

    if vacio_es_fallo is not None and vacio_es_fallo(respuesta):
        raise ErrorDeFuente("la fuente devolvió cero filas")

    return respuesta


def crear_cliente(timeout: float = TIMEOUT_POR_DEFECTO, **kwargs: Any) -> httpx.AsyncClient:
    """Cliente con el timeout amplio que necesitan estas fuentes."""
    return httpx.AsyncClient(timeout=timeout, follow_redirects=True, **kwargs)
