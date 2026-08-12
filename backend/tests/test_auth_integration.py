"""F-014 contra la base real: el criterio que más importa de toda la feature.

    GIVEN el asesor A con una cartera guardada y el asesor B autenticado
    WHEN B consulta la API de carteras directamente, salteando el frontend
    THEN no recibe la cartera de A, porque la restricción es de RLS y no de filtro de cliente

Esto no se puede verificar con un mock: un mock no puede mentir sobre si RLS filtra o no, porque
un mock nunca pasa por RLS. Acá se conecta a PostgreSQL de verdad y se reproduce exactamente lo
que hace PostgREST cuando le llega el JWT de un asesor logueado: cambia la sesión al rol
`authenticated` y deja el claim `sub` del token disponible como `request.jwt.claim.sub`, que es
lo que lee `auth.uid()` adentro de cada policy (`select auth.uid()`, ver la definición de la
función en la base). El backend de FastAPI no arma esta parte —eso lo hace PostgREST/Supabase—;
lo que el backend sí hace, `app/core/seguridad.verificar_token`, es lo que decide *qué* `sub`
llega hasta acá, y eso lo cubre `test_seguridad.py` sin necesitar la base.

Se conecta con el mismo DSN de servicio (`DATABASE_URL`) que usa `test_consolidacion_integration.
py`: ese rol puede asumir `authenticated` (`pg_has_role('postgres', 'authenticated', 'MEMBER')`
es cierto en este proyecto), que es lo que permite simular la sesión de cada asesor sin tener que
pasar por un login real. El armado y el chequeo corren dentro de una transacción que se
descarta al final, así que no queda un asesor de prueba en `auth.users`.
"""

import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from dotenv import dotenv_values

RAIZ_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_REPO / "tools"))


def _dsn() -> str:
    dsn = dotenv_values(RAIZ_REPO / ".env").get("DATABASE_URL")
    if not dsn:
        pytest.skip("sin DATABASE_URL en el .env de la raíz")
    return dsn


@pytest.fixture
async def conexion():
    conn = await asyncpg.connect(_dsn(), timeout=10.0)
    try:
        yield conn
    finally:
        await conn.close()


async def _simular_sesion_de(conexion, id_asesor) -> None:
    """Lo que PostgREST hace con el JWT antes de correr la query: cambiar de rol y dejar el
    `sub` del token en la sesión. Transaction-scoped (`SET LOCAL` / el tercer argumento `true`
    de `set_config`), así que no se filtra a otra prueba."""
    await conexion.execute("SET LOCAL ROLE authenticated")
    await conexion.execute("SELECT set_config('request.jwt.claim.sub', $1, true)", str(id_asesor))


@pytest.mark.integration
async def test_b_no_recibe_la_cartera_de_a_por_rls(conexion) -> None:
    asesor_a, asesor_b = uuid4(), uuid4()

    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        # El armado corre como dueño de la tabla (bypassa RLS a propósito): un fixture de test
        # no es el escenario que se quiere probar, sólo el punto de partida.
        for id_asesor in (asesor_a, asesor_b):
            await conexion.execute("INSERT INTO auth.users (id) VALUES ($1)", id_asesor)
        id_cartera = await conexion.fetchval(
            "INSERT INTO public.carteras (user_id, nombre) VALUES ($1, $2) RETURNING id",
            asesor_a,
            "Cartera de A",
        )

        # A partir de acá la sesión es la de B: cualquier SELECT que siga pasa por su policy.
        await _simular_sesion_de(conexion, asesor_b)

        fila = await conexion.fetchrow("SELECT id FROM public.carteras WHERE id = $1", id_cartera)
        assert fila is None, "B pidió la cartera de A por id y RLS la tiene que ocultar igual"

        listado = await conexion.fetch("SELECT id FROM public.carteras")
        assert listado == [], "tampoco puede aparecer en un listado sin filtro explícito"
    finally:
        # Con `SET LOCAL ROLE` adentro, el rollback además devuelve la sesión a como estaba.
        await transaccion.rollback()


@pytest.mark.integration
async def test_a_si_recibe_su_propia_cartera_por_rls(conexion) -> None:
    """El contraste necesario del test anterior: si esto también diera vacío, RLS no estaría
    filtrando por asesor — estaría rechazando todo, y el test de arriba pasaría por la razón
    equivocada."""
    asesor_a = uuid4()

    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        await conexion.execute("INSERT INTO auth.users (id) VALUES ($1)", asesor_a)
        id_cartera = await conexion.fetchval(
            "INSERT INTO public.carteras (user_id, nombre) VALUES ($1, $2) RETURNING id",
            asesor_a,
            "Cartera de A",
        )

        await _simular_sesion_de(conexion, asesor_a)

        fila = await conexion.fetchrow("SELECT id FROM public.carteras WHERE id = $1", id_cartera)
        assert fila is not None
        assert fila["id"] == id_cartera
    finally:
        await transaccion.rollback()


@pytest.mark.integration
async def test_b_no_puede_insertar_una_posicion_a_nombre_de_a(conexion) -> None:
    """El `WITH CHECK` de la policy de INSERT, no sólo el `USING` de lectura: sin esto un
    asesor podría escribir una fila que declara ser de otro."""
    asesor_a, asesor_b = uuid4(), uuid4()

    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        for id_asesor in (asesor_a, asesor_b):
            await conexion.execute("INSERT INTO auth.users (id) VALUES ($1)", id_asesor)
        id_cartera = await conexion.fetchval(
            "INSERT INTO public.carteras (user_id, nombre) VALUES ($1, $2) RETURNING id",
            asesor_a,
            "Cartera de A",
        )

        await _simular_sesion_de(conexion, asesor_b)

        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conexion.execute(
                "INSERT INTO public.posiciones (cartera_id, user_id, ticker, cantidad) "
                "VALUES ($1, $2, 'AL30D', 100)",
                id_cartera,
                asesor_a,
            )
    finally:
        await transaccion.rollback()
