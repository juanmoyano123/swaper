"""F-010 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá es que la vista `resumen` tenga las columnas que `lectura.py`
pide y con los tipos que `segmentacion.py` espera. Los tests offline prueban el veredicto de las dos
capas sobre datos armados; éste prueba que el universo de verdad entre por la puerta.

**Las aserciones son sobre invariantes, no sobre números del día.** Cuántos instrumentos descarta la
sanidad depende de la corrida de ingesta que haya pasado último, y un test que fije ese número
fallaría cada mañana por la razón equivocada. Lo que sí tiene que valer siempre es que ningún
descarte se haya medido contra el tope de otro segmento y que ninguno haya salido de un faltante.
"""

from pathlib import Path

import asyncpg
import pytest
from dotenv import dotenv_values

from app.universo.sanidad import DISCORDANCIA_ESPECIES, TOPE_SANIDAD_SEGMENTO, MotivoDescarte
from app.universo.segmentacion import NATURALEZA_TASA
from app.universo.servicio import sanear_universo

RAIZ_REPO = Path(__file__).resolve().parents[2]


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


@pytest.fixture
async def saneado(conexion):
    return await sanear_universo(conexion)


@pytest.mark.integration
async def test_la_vista_resumen_alcanza_para_segmentar_el_universo(saneado) -> None:
    """Si `lectura.COLUMNAS` pidiera una columna que la vista no tiene, esto falla con un error de
    SQL; si la vista cambiara de tipos, falla acá al no poder segmentar nada."""
    assert saneado.leidos > 0
    assert len(saneado.especies) > 0
    assert saneado.leidos == len(saneado.especies) + saneado.renta_variable + len(
        saneado.sin_segmento
    )


@pytest.mark.integration
async def test_cada_especie_del_universo_real_cae_en_un_segmento_con_unidad_conocida(
    saneado,
) -> None:
    assert {e.segmento for e in saneado.especies} <= set(NATURALEZA_TASA)


@pytest.mark.integration
async def test_ningun_descarte_se_midio_contra_el_tope_de_otro_segmento(saneado) -> None:
    """Es el corazón de la feature: el tope se elige por segmento porque el segmento determina la
    unidad. Un descarte medido contra el tope ajeno sería un instrumento sano condenado por estar en
    la unidad equivocada."""
    for descarte in saneado.descartes:
        esperado = (
            DISCORDANCIA_ESPECIES
            if descarte.motivo is MotivoDescarte.ESPECIE_INCOHERENTE
            else TOPE_SANIDAD_SEGMENTO[descarte.segmento]
        )
        assert descarte.umbral == esperado, descarte.ticker


@pytest.mark.integration
async def test_ningun_descarte_salio_de_un_faltante(saneado) -> None:
    """Regla 1: lo que no se sabe no se completa ni se condena."""
    for descarte in saneado.descartes:
        assert descarte.rendimiento == descarte.rendimiento  # no es NaN
        assert descarte.rendimiento is not None


@pytest.mark.integration
async def test_los_descartados_no_aparecen_entre_los_operables(saneado) -> None:
    assert saneado.sanidad.descartados.isdisjoint({e.ticker for e in saneado.operables()})
