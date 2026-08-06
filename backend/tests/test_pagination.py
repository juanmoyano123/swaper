"""Criterio 3: ninguna colección devuelve el conjunto completo."""

from collections.abc import Callable
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI

from app.core.pagination import (
    DEFAULT_LIMIT,
    CursorParams,
    InvalidCursorError,
    build_page,
    decode_cursor,
    encode_cursor,
)
from tests.conftest import cliente

TOTAL = 120


def _app_con_coleccion(crear_app: Callable[..., FastAPI]) -> FastAPI:
    """App con una colección en memoria que pagina igual que lo harán las de F-004 en adelante."""
    app = crear_app()
    filas = [{"id": i, "nombre": f"especie-{i:03d}"} for i in range(TOTAL)]

    @app.get("/api/v1/demo")
    async def demo(params: Annotated[CursorParams, Depends()]) -> Any:
        desde = params.decoded_cursor()
        arranque = desde["id"] + 1 if desde else 0
        pagina = [f for f in filas if f["id"] >= arranque][: params.limit + 1]
        return build_page(pagina, params.limit, lambda f: {"id": f["id"]})

    return app


async def test_la_primera_pagina_no_trae_la_coleccion_entera(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_coleccion(crear_app)

    async with cliente(app) as c:
        cuerpo = (await c.get("/api/v1/demo")).json()

    assert len(cuerpo["items"]) == DEFAULT_LIMIT
    assert len(cuerpo["items"]) < TOTAL
    assert cuerpo["next_cursor"]


async def test_el_recorrido_por_cursores_cubre_todo_sin_repetir(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_coleccion(crear_app)
    vistos: list[int] = []
    cursor: str | None = None

    async with cliente(app) as c:
        for _ in range(TOTAL):  # cota dura: si no converge, falla el assert de abajo
            parametros = {"cursor": cursor} if cursor else {}
            cuerpo = (await c.get("/api/v1/demo", params=parametros)).json()
            vistos.extend(fila["id"] for fila in cuerpo["items"])
            cursor = cuerpo["next_cursor"]
            if not cursor:
                break

    assert vistos == list(range(TOTAL))


async def test_la_ultima_pagina_no_devuelve_cursor(crear_app: Callable[..., FastAPI]) -> None:
    app = _app_con_coleccion(crear_app)

    async with cliente(app) as c:
        cuerpo = (await c.get("/api/v1/demo", params={"limit": TOTAL})).json()

    assert len(cuerpo["items"]) == TOTAL
    assert cuerpo["next_cursor"] is None


async def test_un_cursor_invalido_devuelve_400_con_el_contrato_de_error(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = _app_con_coleccion(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/demo", params={"cursor": "esto-no-es-un-cursor"})

    error = respuesta.json()["error"]
    assert respuesta.status_code == 400
    assert error["code"] == "invalid_cursor"
    assert error["request_id"]


async def test_un_limit_fuera_de_rango_es_rechazado(crear_app: Callable[..., FastAPI]) -> None:
    app = _app_con_coleccion(crear_app)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/demo", params={"limit": 5_000})

    assert respuesta.status_code == 422
    assert respuesta.json()["error"]["code"] == "validation_error"


def test_el_cursor_es_opaco_y_reversible() -> None:
    payload = {"k": "2026-08-06", "id": 42}

    codificado = encode_cursor(payload)

    assert "42" not in codificado, "el cursor no debe filtrar la clave de orden en claro"
    assert decode_cursor(codificado) == payload


@pytest.mark.parametrize("basura", ["###", "", "bm90LWEtZGljdA"])
def test_decode_cursor_rechaza_lo_que_no_emitio_el_servicio(basura: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(basura)
