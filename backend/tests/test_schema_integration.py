"""Verificación del esquema de F-002 contra PostgreSQL de verdad.

Marcados `integration`: quedan fuera de la corrida por defecto porque necesitan la base migrada.
Se corren con `pytest -m integration` antes de dar la feature por terminada.

Lo que se verifica acá no se puede simular con una conexión falsa: que RLS esté activa, que los
CHECK rechacen lo que tienen que rechazar, y que las columnas del contrato del motor existan con
el nombre exacto.
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

TABLAS_DE_USUARIO = ["carteras", "posiciones", "propuestas"]
TABLAS_DE_MERCADO = ["instrumentos", "precios", "puntas", "cashflow", "condiciones_emision"]

# Las 21 columnas de COLUMNAS_RESUMEN (tools/consolidar_universo.py), en orden. Este literal es el
# contrato: si el motor lee una columna que no está acá, la vista no le sirve.
COLUMNAS_RESUMEN = [
    "ticker",
    "clase_activo",
    "tipo_tasa",
    "subtipo",
    "underlying",
    "sector",
    "tir",
    "tna",
    "duration",
    "maturity",
    "law",
    "couponCurrency",
    "lamina",
    "calificacion",
    "paridad",
    "residualValue",
    "lastPrice",
    "effectiveVolume",
    "revisar",
    "duplicado",
    "archivo_origen",
]

# Las 9 columnas de cashflow_completo.csv.
COLUMNAS_CASHFLOW = [
    "ticker",
    "type",
    "issue_date",
    "payment_date",
    "capital",
    "interest_rate",
    "interest_amount",
    "residual_value",
    "cash_flow",
]


@pytest.fixture
async def conn():
    """Conexión directa a la base real. Se cierra siempre, aunque el test falle."""
    import asyncpg

    conexion = await asyncpg.connect(dsn=dotenv_values(ENV_FILE)["DATABASE_URL"], timeout=15)
    try:
        yield conexion
    finally:
        await conexion.close()


async def _columnas(conn, relacion: str) -> list[str]:
    filas = await conn.fetch(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1
        ORDER BY ordinal_position
        """,
        relacion,
    )
    return [f["column_name"] for f in filas]


# --- Criterio 1: aislamiento entre asesores ---------------------------------------------------


@pytest.mark.parametrize("tabla", TABLAS_DE_USUARIO)
async def test_las_tablas_de_usuario_tienen_rls_activa(conn, tabla: str) -> None:
    activa = await conn.fetchval(
        "SELECT relrowsecurity FROM pg_class WHERE oid = $1::regclass", f"public.{tabla}"
    )
    assert activa, f"{tabla} sin RLS: un bug del frontend filtraría carteras de otro asesor"


@pytest.mark.parametrize("tabla", TABLAS_DE_USUARIO)
async def test_las_tablas_de_usuario_exigen_user_id(conn, tabla: str) -> None:
    nullable = await conn.fetchval(
        """
        SELECT is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = $1 AND column_name = 'user_id'
        """,
        tabla,
    )
    assert nullable == "NO", f"{tabla}.user_id admite nulos: habría filas sin dueño"


@pytest.mark.parametrize("tabla", TABLAS_DE_USUARIO)
async def test_user_id_apunta_a_los_usuarios_de_auth(conn, tabla: str) -> None:
    destino = await conn.fetchval(
        """
        SELECT confrelid::regclass::text
        FROM pg_constraint
        WHERE conrelid = $1::regclass
          AND contype = 'f'
          AND conkey = ARRAY[(
              SELECT attnum FROM pg_attribute
              WHERE attrelid = $1::regclass AND attname = 'user_id'
          )]
        """,
        f"public.{tabla}",
    )
    assert destino == "auth.users", f"{tabla}.user_id no referencia auth.users (es {destino})"


@pytest.mark.parametrize("tabla", TABLAS_DE_USUARIO)
async def test_cada_operacion_tiene_su_policy(conn, tabla: str) -> None:
    """SELECT, INSERT, UPDATE y DELETE: sin las cuatro, alguna operación quedaría sin control."""
    comandos = await conn.fetch(
        "SELECT cmd FROM pg_policies WHERE schemaname = 'public' AND tablename = $1", tabla
    )
    assert {c["cmd"] for c in comandos} == {"SELECT", "INSERT", "UPDATE", "DELETE"}


@pytest.mark.parametrize("tabla", TABLAS_DE_MERCADO)
async def test_el_mercado_se_lee_pero_no_se_escribe_desde_la_api(conn, tabla: str) -> None:
    """El universo es compartido: lectura para todos, escritura por ninguna policy."""
    comandos = {
        c["cmd"]
        for c in await conn.fetch(
            "SELECT cmd FROM pg_policies WHERE schemaname = 'public' AND tablename = $1", tabla
        )
    }
    assert comandos == {"SELECT"}, f"{tabla} tiene policies de escritura: {comandos - {'SELECT'}}"


# --- Criterio 2: ningún valor curado sin decir de dónde salió ---------------------------------


async def test_una_lamina_sin_origen_ni_fecha_es_rechazada(conn) -> None:
    import asyncpg

    tr = conn.transaction()
    await tr.start()
    try:
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conn.execute(
                "INSERT INTO public.condiciones_emision (ticker, lamina) VALUES ($1, $2)",
                "__PRUEBA__",
                100,
            )
    finally:
        await tr.rollback()


async def test_una_lamina_con_origen_y_fecha_entra(conn) -> None:
    """La contracara del test anterior: el CHECK no puede estar bloqueando todo."""
    from datetime import date

    tr = conn.transaction()
    await tr.start()
    try:
        await conn.execute(
            """
            INSERT INTO public.condiciones_emision (ticker, lamina, lamina_origen, lamina_fecha)
            VALUES ($1, $2, $3, $4)
            """,
            "__PRUEBA__",
            100,
            "prueba de esquema",
            date(2026, 8, 6),
        )
        fila = await conn.fetchrow(
            "SELECT lamina_origen, lamina_fecha FROM public.condiciones_emision WHERE ticker = $1",
            "__PRUEBA__",
        )
        assert fila["lamina_origen"] is not None
        assert fila["lamina_fecha"] is not None
    finally:
        await tr.rollback()


@pytest.mark.parametrize(
    "campo", ["ley", "moneda_pago", "lamina", "calificacion", "sector", "underlying"]
)
async def test_todo_campo_curado_lleva_su_triplete(conn, campo: str) -> None:
    columnas = await _columnas(conn, "condiciones_emision")
    assert campo in columnas
    assert f"{campo}_origen" in columnas
    assert f"{campo}_fecha" in columnas


# --- Criterio 3: el contrato del motor sigue en pie -------------------------------------------


async def test_la_vista_resumen_conserva_las_21_columnas_del_contrato(conn) -> None:
    """El contrato del motor son estas 21, en este orden y al principio de la vista.

    No es igualdad exacta: una feature puede **agregar** una columna al final —F-052 agregó
    `cierre_anterior`— y eso no rompe a nadie, porque `CREATE OR REPLACE VIEW` sólo admite columnas
    nuevas al final y todos los lectores, motor incluido, leen por nombre. Lo que sí rompería el
    contrato es que una de estas 21 desaparezca, cambie de nombre o se corra de lugar, y eso es
    exactamente lo que este test sigue atrapando.
    """
    columnas = await _columnas(conn, "resumen")
    assert columnas[: len(COLUMNAS_RESUMEN)] == COLUMNAS_RESUMEN


async def test_cashflow_replica_las_columnas_del_csv(conn) -> None:
    assert set(COLUMNAS_CASHFLOW) <= set(await _columnas(conn, "cashflow"))


async def test_la_vista_es_consultable(conn) -> None:
    """Que las columnas existan no prueba que el JOIN funcione: hay que ejecutarla."""
    await conn.fetch("SELECT * FROM public.resumen LIMIT 1")


async def test_precios_respeta_el_contrato_del_health(conn) -> None:
    """`health.py` lee esta columna en cada sondeo de la plataforma; el tipo importa."""
    tipo = await conn.fetchval(
        """
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'precios' AND column_name = 'capturado_en'
        """
    )
    assert tipo == "timestamp with time zone"
