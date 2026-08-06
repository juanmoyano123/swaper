"""`corridas_ingesta` contra PostgreSQL de verdad. Marcado `integration`, fuera de la corrida por
defecto — necesita la migración de F-008 aplicada.
"""

import pytest
from dotenv import dotenv_values

from app.core.config import ENV_FILE

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not dotenv_values(ENV_FILE).get("DATABASE_URL"),
        reason="DATABASE_URL sin configurar en el .env de la raíz",
    ),
]


def _dsn() -> str:
    return dotenv_values(ENV_FILE)["DATABASE_URL"]


@pytest.fixture
async def conexion():
    import asyncpg

    conn = await asyncpg.connect(_dsn(), timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()


async def test_la_tabla_existe_con_rls_activo(conexion) -> None:
    fila = await conexion.fetchrow(
        "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.corridas_ingesta'::regclass"
    )
    assert fila is not None, "la migración de F-008 no está aplicada"
    assert fila["relrowsecurity"] is True


async def test_el_check_de_tipo_rechaza_lo_que_no_es_matinal_o_refresh(conexion) -> None:
    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        import asyncpg as asyncpg_mod

        with pytest.raises(asyncpg_mod.exceptions.CheckViolationError):
            await conexion.execute(
                "INSERT INTO public.corridas_ingesta "
                "(tipo, iniciado_en, finalizado_en, duracion_ms, estado) "
                "VALUES ('semanal', now(), now(), 0, 'completa')"
            )
    finally:
        await transaccion.rollback()


async def test_el_check_de_estado_rechaza_lo_que_no_esta_en_el_dominio(conexion) -> None:
    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        import asyncpg as asyncpg_mod

        with pytest.raises(asyncpg_mod.exceptions.CheckViolationError):
            await conexion.execute(
                "INSERT INTO public.corridas_ingesta "
                "(tipo, iniciado_en, finalizado_en, duracion_ms, estado) "
                "VALUES ('matinal', now(), now(), 0, 'exitosa')"
            )
    finally:
        await transaccion.rollback()


async def test_inserta_y_lee_filas_por_fuente_y_alertas_como_jsonb(conexion) -> None:
    import json

    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        fila = await conexion.fetchrow(
            "INSERT INTO public.corridas_ingesta "
            "(tipo, iniciado_en, finalizado_en, duracion_ms, filas_por_fuente, alertas, estado) "
            "VALUES ('refresh', now(), now(), 1200, '{\"byma\": 10}'::jsonb, '[]'::jsonb, "
            "'completa') RETURNING filas_por_fuente, alertas"
        )
        # asyncpg no tiene codec de jsonb por defecto: vuelve como el texto que Postgres eligió
        # para serializarlo, que no es necesariamente idéntico byte a byte al que se insertó.
        assert json.loads(fila["filas_por_fuente"]) == {"byma": 10}
        assert json.loads(fila["alertas"]) == []
    finally:
        await transaccion.rollback()
