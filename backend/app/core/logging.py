"""Logging estructurado en JSON a stdout, con un request_id que atraviesa todo el request.

Dos capas garantizan que ningún secreto llegue al log: el middleware sólo emite método, ruta,
status y duración —nunca headers, query strings completas ni body—, y encima de eso el
procesador `redact_secrets` tapa el valor de cualquier clave que huela a credencial.
"""

import logging
import re
import sys
import time
from collections.abc import Iterable, MutableMapping
from typing import Any, TextIO
from uuid import uuid4

import structlog
from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_SECRET_KEY_PATTERN = re.compile(
    r"token|key|secret|password|passwd|authorization|credential|dsn|database_url",
    re.IGNORECASE,
)
_REDACTED = "[REDACTED]"

logger = structlog.get_logger()


def _redact(value: Any) -> Any:
    if isinstance(value, MutableMapping):
        return {
            clave: _REDACTED if _SECRET_KEY_PATTERN.search(str(clave)) else _redact(valor)
            for clave, valor in value.items()
        }
    if isinstance(value, Iterable) and not isinstance(value, str | bytes):
        return [_redact(elemento) for elemento in value]
    return value


def redact_secrets(_logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]) -> Any:
    return _redact(event_dict)


def configure_logging(level: str = "INFO", stream: TextIO | None = None) -> None:
    """Configura structlog para emitir una línea JSON por evento.

    `stream` existe para que los tests capturen la salida; en producción va a stdout.
    """
    nivel = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_secrets,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(nivel),
        logger_factory=structlog.WriteLoggerFactory(file=stream or sys.stdout),
        cache_logger_on_first_use=False,
    )
    # El middleware ya emite una línea por request, en JSON. El access log de uvicorn diría lo
    # mismo en texto plano y ensuciaría la salida estructurada.
    logging.getLogger("uvicorn.access").disabled = True


class RequestLoggingMiddleware:
    """Middleware ASGI que asigna un request_id y emite el log de cada request.

    Se implementa a nivel ASGI y no con BaseHTTPMiddleware para no romper respuestas en
    streaming ni agregar una task por request.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        entrante = Headers(scope=scope).get(REQUEST_ID_HEADER)
        request_id = entrante or uuid4().hex

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        # También en el scope: el handler de errores 500 corre por encima de este middleware,
        # cuando el contextvar ya se limpió, y necesita el mismo id para el cuerpo del error.
        scope.setdefault("state", {})["request_id"] = request_id

        # Si la aplicación explota antes de emitir la respuesta, el handler de errores devuelve
        # un 500; este default hace que el log diga lo mismo que ve el cliente.
        status_code = 500
        inicio = time.perf_counter()

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            logger.info(
                "request",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                duration_ms=round((time.perf_counter() - inicio) * 1000, 2),
            )
            structlog.contextvars.clear_contextvars()


def current_request_id() -> str | None:
    """El request_id del request en curso, o None fuera de un request."""
    return structlog.contextvars.get_contextvars().get("request_id")
