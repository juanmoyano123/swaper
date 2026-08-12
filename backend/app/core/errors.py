"""Contrato de error uniforme para todo el API.

Todo error, venga de donde venga, sale con la misma forma:

    {"error": {"code": "...", "message": "...", "details": [...], "request_id": "..."}}

El `request_id` es el mismo que aparece en la línea de log del request, así que un error que
reporta un asesor se rastrea sin adivinar. Los 500 nunca devuelven el traceback: ese va al log.
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import REQUEST_ID_HEADER, current_request_id
from app.core.pagination import InvalidCursorError
from app.jobs.horarios import FueraDeLaRueda

logger = structlog.get_logger()

_CODIGOS_POR_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "service_unavailable",
}

MENSAJE_INTERNO = "Error interno del servicio. El detalle quedó registrado con este request_id."


def _request_id(request: Request) -> str | None:
    # El middleware lo deja en el scope; el contextvar es el respaldo para los handlers que
    # corren por encima del middleware, donde ya fue limpiado.
    return getattr(request.state, "request_id", None) or current_request_id()


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": request_id,
            }
        },
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Se reporta qué campo falló y por qué, pero nunca el valor recibido: el payload puede
    # traer datos de cartera de un cliente.
    detalles = [
        {
            "field": ".".join(str(parte) for parte in error.get("loc", ())),
            "issue": error.get("msg", ""),
        }
        for error in exc.errors()
    ]
    return error_response(
        request,
        422,
        "validation_error",
        "Los parámetros de la consulta no son válidos.",
        detalles,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    codigo = _CODIGOS_POR_STATUS.get(exc.status_code, "error")
    return error_response(request, exc.status_code, codigo, str(exc.detail))


async def invalid_cursor_handler(request: Request, exc: InvalidCursorError) -> JSONResponse:
    return error_response(request, 400, "invalid_cursor", str(exc))


async def fuera_de_la_rueda_handler(request: Request, exc: FueraDeLaRueda) -> JSONResponse:
    """409 y no 422: el pedido está bien formado y el servicio está sano; lo que no está es el
    mercado. El código propio —en vez del `conflict` genérico— es para que el cliente pueda
    distinguir "probá más tarde" de cualquier otro conflicto que aparezca después."""
    return error_response(request, 409, "fuera_de_la_rueda", str(exc))


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        request_id=_request_id(request),
        path=request.url.path,
        exc_info=exc,
    )
    return error_response(request, 500, "internal_error", MENSAJE_INTERNO)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(InvalidCursorError, invalid_cursor_handler)
    app.add_exception_handler(FueraDeLaRueda, fuera_de_la_rueda_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
