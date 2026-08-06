"""Criterio 4: una línea JSON por request, con request_id, y sin un solo secreto."""

import io
import json
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from app.core.logging import configure_logging, redact_secrets
from tests.conftest import ENV_DE_PRUEBA, FakeConnection, cliente


def _eventos(salida: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(linea) for linea in salida.getvalue().splitlines() if linea.strip()]


def _evento_request(salida: io.StringIO) -> dict[str, Any]:
    return next(evento for evento in _eventos(salida) if evento["event"] == "request")


async def test_cada_request_deja_una_linea_json_completa(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection())
    salida = io.StringIO()
    configure_logging("INFO", stream=salida)

    async with cliente(app) as c:
        await c.get("/api/v1/health")

    evento = _evento_request(salida)
    assert evento["request_id"]
    assert evento["method"] == "GET"
    assert evento["path"] == "/api/v1/health"
    assert evento["status_code"] == 200
    assert evento["duration_ms"] >= 0
    assert evento["level"] == "info"
    assert evento["timestamp"]


async def test_el_request_id_entrante_se_respeta_y_se_devuelve(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection())
    salida = io.StringIO()
    configure_logging("INFO", stream=salida)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/health", headers={"X-Request-ID": "trazador-123"})

    assert respuesta.headers["X-Request-ID"] == "trazador-123"
    assert _evento_request(salida)["request_id"] == "trazador-123"


async def test_sin_header_entrante_se_genera_un_request_id(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection())
    salida = io.StringIO()
    configure_logging("INFO", stream=salida)

    async with cliente(app) as c:
        primera = await c.get("/api/v1/health")
        segunda = await c.get("/api/v1/health")

    assert primera.headers["X-Request-ID"] != segunda.headers["X-Request-ID"]


async def test_ningun_secreto_llega_al_log(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(FakeConnection())
    salida = io.StringIO()
    configure_logging("INFO", stream=salida)

    async with cliente(app) as c:
        await c.get("/api/v1/health", headers={"Authorization": "Bearer token-que-no-debe-salir"})

    texto = salida.getvalue()
    for valor in ENV_DE_PRUEBA.values():
        assert valor not in texto
    assert "contrasena-secreta" not in texto
    assert "token-que-no-debe-salir" not in texto


def test_el_redactor_tapa_las_claves_sensibles() -> None:
    evento = {
        "event": "algo",
        "path": "/api/v1/health",
        "api_key": "abc123",
        "database_url": "postgresql://usuario:clave@host/db",
        "docta_api_token": "xyz",
        "anidado": {"password": "secreta"},
    }

    resultado = redact_secrets(None, "info", evento)

    assert resultado["api_key"] == "[REDACTED]"
    assert resultado["database_url"] == "[REDACTED]"
    assert resultado["docta_api_token"] == "[REDACTED]"
    assert resultado["anidado"]["password"] == "[REDACTED]"
    assert resultado["path"] == "/api/v1/health", "lo que no es secreto tiene que seguir visible"
