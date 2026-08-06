"""Criterio 1: el health informa el estado de PostgreSQL y la hora del último snapshot."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from dotenv import dotenv_values
from fastapi import FastAPI

from app.core.config import ENV_FILE
from app.db.health import get_last_snapshot
from tests.conftest import FakeConnection, cliente

# El único test que toca una base real toma el DSN del .env, no de las variables de prueba.
_DSN_REAL = dotenv_values(ENV_FILE).get("DATABASE_URL")


async def test_responde_ok_aunque_no_existan_las_tablas_de_mercado(
    crear_app: Callable[..., FastAPI],
) -> None:
    """Hasta F-002 no hay tabla de precios: se informa vacío y se explica por qué."""
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/health")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["status"] == "ok"
    assert cuerpo["database"] == "ok"
    assert cuerpo["last_market_snapshot_at"] is None
    assert any("F-002" in aviso for aviso in cuerpo["warnings"])


async def test_informa_la_hora_del_ultimo_snapshot(crear_app: Callable[..., FastAPI]) -> None:
    momento = datetime(2026, 8, 6, 17, 30, tzinfo=UTC)
    conn = FakeConnection(tabla_existe=True, columna_existe=True, ultimo_snapshot=momento)
    app = crear_app(conn)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/health")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200
    assert cuerpo["last_market_snapshot_at"].startswith("2026-08-06T17:30")
    assert cuerpo["warnings"] == []


async def test_avisa_cuando_la_tabla_existe_pero_no_hubo_ingesta(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection(tabla_existe=True, columna_existe=True))

    async with cliente(app) as c:
        cuerpo = (await c.get("/api/v1/health")).json()

    assert cuerpo["last_market_snapshot_at"] is None
    assert any("vacía" in aviso for aviso in cuerpo["warnings"])


async def test_responde_503_cuando_no_hay_base(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(None)

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/health")

    cuerpo = respuesta.json()
    assert respuesta.status_code == 503
    assert cuerpo["status"] == "error"
    assert cuerpo["database"] == "error"
    assert cuerpo["last_market_snapshot_at"] is None


async def test_responde_503_cuando_la_consulta_falla(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(FakeConnection(error=OSError("conexión cortada")))

    async with cliente(app) as c:
        respuesta = await c.get("/api/v1/health")

    assert respuesta.status_code == 503
    assert respuesta.json()["database"] == "error"


async def test_no_existe_fuera_del_prefijo_de_version(crear_app: Callable[..., FastAPI]) -> None:
    """Toda ruta vive bajo /api/v1: el prefijo se aplica una vez y no hay forma de saltearlo."""
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        assert (await c.get("/health")).status_code == 404


@pytest.mark.integration
@pytest.mark.skipif(not _DSN_REAL, reason="DATABASE_URL sin configurar en el .env de la raíz")
async def test_consulta_una_base_real() -> None:
    """Smoke contra PostgreSQL de verdad. Fuera de la corrida por defecto."""
    import asyncpg

    pool = await asyncpg.create_pool(dsn=_DSN_REAL, min_size=1, max_size=2, timeout=10)
    try:
        async with pool.acquire() as conn:
            ultimo, avisos = await get_last_snapshot(conn)
    finally:
        await pool.close()

    assert ultimo is None or isinstance(ultimo, datetime)
    assert ultimo is not None or avisos, "sin snapshot tiene que haber un aviso que lo explique"
