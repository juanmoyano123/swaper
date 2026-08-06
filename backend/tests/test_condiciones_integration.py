"""F-009 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Tres cosas que sólo se pueden verificar acá. Que PostgreSQL acepte el upsert que `persistencia.py`
arma —los tests offline prueban el contrato del SQL, no que el motor lo ejecute—. Que los seis
CHECK de trazabilidad no rechacen ni una de las 823 filas, que es la forma en que la base verifica
por su cuenta que ningún valor se escribió sin decir de dónde salió. Y el tercer criterio de
aceptación, que es una consulta: la cobertura reportada tiene que corresponderse con los valores
efectivamente cargados y su origen.

**Todo corre adentro de una transacción que se deshace.** La siembra de verdad es un acto
operativo (`POST /api/v1/condiciones/semilla`), no un efecto colateral de correr los tests.
"""

from pathlib import Path

import asyncpg
import pytest
from dotenv import dotenv_values

from app.condiciones import sembrar
from app.condiciones.persistencia import HERENCIA_ENTRE_ESPECIES
from app.condiciones.resolucion import PREFIJO_HERENCIA
from app.condiciones.semilla import CAMPOS, ORIGEN_SEMILLA
from app.core.config import get_settings

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _dsn() -> str:
    dsn = dotenv_values(RAIZ_REPO / ".env").get("DATABASE_URL")
    if not dsn:
        pytest.skip("sin DATABASE_URL en el .env de la raíz")
    return dsn


@pytest.fixture
async def conexion():
    conn = await asyncpg.connect(_dsn(), timeout=15.0)
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def sembrado(conexion):
    """Siembra el artefacto real y deshace todo al terminar."""
    transaccion = conexion.transaction()
    await transaccion.start()
    try:
        yield await sembrar(conexion, get_settings())
    finally:
        await transaccion.rollback()


@pytest.mark.integration
async def test_las_823_especies_curadas_entran_sin_violar_ningun_check(sembrado) -> None:
    """Los CHECK de trazabilidad rechazarían cualquier valor escrito sin origen o sin fecha."""
    assert sembrado.escritura.filas == 823
    assert sembrado.escritura.alertas == []


@pytest.mark.integration
async def test_ningun_valor_cargado_tiene_un_origen_que_no_sea_el_artefacto_o_una_herencia(
    conexion, sembrado
) -> None:
    """El tercer criterio: ninguna fila completada por inferencia, y se ve en el origen.

    Dos comprobaciones distintas: el reporte agregado no puede tener un tercer origen, y la tabla
    fila por fila no puede tener un origen que no sea el artefacto o una herencia con donante.
    """
    for medida in sembrado.cobertura:
        assert set(medida.por_origen) <= {ORIGEN_SEMILLA, HERENCIA_ENTRE_ESPECIES}

    for campo in CAMPOS:
        origenes = await conexion.fetch(
            f"SELECT DISTINCT {campo}_origen AS origen FROM public.condiciones_emision "
            f"WHERE {campo} IS NOT NULL"
        )
        for fila in origenes:
            assert fila["origen"] == ORIGEN_SEMILLA or fila["origen"].startswith(
                f"{PREFIJO_HERENCIA} "
            )


@pytest.mark.integration
async def test_los_origenes_de_cada_campo_suman_los_presentes(sembrado) -> None:
    for medida in sembrado.cobertura:
        assert sum(medida.por_origen.values()) == medida.cobertura.presentes


@pytest.mark.integration
async def test_la_cobertura_reportada_es_la_que_la_base_tiene(conexion, sembrado) -> None:
    """El conteo del reporte se contrasta contra un COUNT independiente sobre las mismas tablas."""
    for medida in sembrado.cobertura:
        campo = medida.cobertura.campo
        presentes = await conexion.fetchval(
            f"SELECT count(c.{campo})::int FROM public.instrumentos i "
            f"LEFT JOIN public.condiciones_emision c ON c.ticker = i.ticker"
        )
        assert medida.cobertura.presentes == presentes, campo


@pytest.mark.integration
async def test_la_lamina_llega_al_universo_y_antes_no_estaba(sembrado) -> None:
    """La razón de ser de la feature: ninguna fuente de mercado publica lámina."""
    lamina = next(m for m in sembrado.cobertura if m.cobertura.campo == "lamina")

    assert lamina.cobertura.presentes > 0
    assert lamina.cobertura.total > 0


@pytest.mark.integration
async def test_sembrar_dos_veces_no_duplica_ni_cambia_la_cobertura(conexion, sembrado) -> None:
    """El upsert por ticker: la siembra se puede reejecutar sin miedo."""
    segunda = await sembrar(conexion, get_settings())

    assert await conexion.fetchval("SELECT count(*) FROM public.condiciones_emision") == 823
    assert [m.como_dict() for m in segunda.cobertura] == [m.como_dict() for m in sembrado.cobertura]


@pytest.mark.integration
async def test_los_curados_que_el_universo_no_conoce_no_se_pierden(conexion, sembrado) -> None:
    """La tabla no tiene FK a `instrumentos` justamente para esto."""
    en_la_tabla = await conexion.fetchval("SELECT count(*) FROM public.condiciones_emision")
    en_el_universo = await conexion.fetchval(
        "SELECT count(*) FROM public.instrumentos i "
        "JOIN public.condiciones_emision c ON c.ticker = i.ticker"
    )

    assert en_la_tabla - en_el_universo == sembrado.curados_fuera_del_universo


@pytest.mark.integration
async def test_el_listado_expone_el_triplete_de_los_seis_campos(conexion, sembrado) -> None:
    fila = await conexion.fetchrow(
        "SELECT * FROM public.condiciones_emision ORDER BY ticker LIMIT 1"
    )

    for campo in CAMPOS:
        assert {campo, f"{campo}_origen", f"{campo}_fecha"} <= set(fila.keys())
