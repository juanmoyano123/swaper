"""El contrato de error es uno solo, venga el error de donde venga."""

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, HTTPException

from tests.conftest import FakeConnection, cliente

DETALLE_INTERNO = "la cartera del cliente quedó a medio calcular"


def _app_con_rutas_que_fallan(crear_app: Callable[..., FastAPI]) -> FastAPI:
    app = crear_app(FakeConnection())

    @app.get("/api/v1/explota")
    async def explota() -> Any:
        raise ValueError(DETALLE_INTERNO)

    @app.get("/api/v1/prohibido")
    async def prohibido() -> Any:
        raise HTTPException(status_code=403, detail="No tenés acceso a esta cartera.")

    @app.get("/api/v1/con-parametro")
    async def con_parametro(cantidad: int) -> Any:
        return {"cantidad": cantidad}

    return app


async def test_un_error_no_manejado_devuelve_500_sin_filtrar_el_detalle(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_rutas_que_fallan(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/explota")

    error = respuesta.json()["error"]
    assert respuesta.status_code == 500
    assert error["code"] == "internal_error"
    assert error["request_id"], "sin request_id el error no se puede rastrear en el log"
    assert DETALLE_INTERNO not in respuesta.text
    assert "Traceback" not in respuesta.text


async def test_una_httpexception_conserva_su_status_y_su_mensaje(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_rutas_que_fallan(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/prohibido")

    error = respuesta.json()["error"]
    assert respuesta.status_code == 403
    assert error["code"] == "forbidden"
    assert error["message"] == "No tenés acceso a esta cartera."


async def test_una_ruta_inexistente_usa_el_mismo_contrato(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_rutas_que_fallan(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/no-existe")

    error = respuesta.json()["error"]
    assert respuesta.status_code == 404
    assert error["code"] == "not_found"
    assert error["details"] == []


async def test_un_parametro_invalido_dice_que_campo_fallo_sin_repetir_el_valor(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_rutas_que_fallan(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/con-parametro", params={"cantidad": "no-es-un-numero"})

    error = respuesta.json()["error"]
    assert respuesta.status_code == 422
    assert error["code"] == "validation_error"
    assert error["details"][0]["field"].endswith("cantidad")
    assert error["details"][0]["issue"]
    assert "no-es-un-numero" not in respuesta.text, "el valor recibido no se ecoa al cliente"


async def test_los_errores_llevan_el_header_de_correlacion(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_rutas_que_fallan(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/explota", headers={"X-Request-ID": "trazador-abc"})

    assert respuesta.headers["X-Request-ID"] == "trazador-abc"
    assert respuesta.json()["error"]["request_id"] == "trazador-abc"
