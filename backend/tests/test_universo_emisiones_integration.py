"""F-011 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá es que la vista `resumen` traiga las cinco columnas que F-011
agregó a `lectura.COLUMNAS` y con los tipos que la deduplicación espera: `duration` como número y
`maturity` como fecha. Si `couponCurrency` no llegara entrecomillada, esto falla con un error de SQL
antes de llegar a la primera aserción, que es justamente lo que tiene que pasar.

**Las aserciones son sobre invariantes, no sobre números del día.** Cuántas emisiones colapsan
depende de la corrida de ingesta que haya pasado último. Lo que tiene que valer siempre es que las
dos vistas sean del mismo universo, que la colapsada no pierda ninguna emisión y que ninguna especie
descartada represente a la suya.
"""

from pathlib import Path

import asyncpg
import pytest
from dotenv import dotenv_values

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
async def test_la_vista_resumen_trae_los_campos_que_deciden_el_representante(saneado) -> None:
    """`duration` como número y `maturity` como fecha. Si la vista cambiara de tipos, la
    completitud daría cero para todos y el representante se elegiría por el desempate sin que nadie
    se entere: esto lo detecta."""
    especies = saneado.especies
    assert especies, "el universo vino vacío: no hay nada que deduplicar"
    assert any(e.duracion is not None for e in especies)
    assert any(e.vencimiento is not None for e in especies)
    assert any(e.ley is not None for e in especies)
    assert any(e.moneda_cupon is not None for e in especies)


@pytest.mark.integration
async def test_las_dos_vistas_son_del_mismo_universo(saneado) -> None:
    """La viva tiene todas las especies del universo saneado, sin perder ni agregar ninguna; la
    colapsada es un subconjunto de ella. Deduplicar no filtra."""
    dedup = saneado.emisiones()
    viva = {e.ticker for e in dedup.vivo()}
    assert viva == {e.ticker for e in saneado.especies}
    assert {e.ticker for e in dedup.colapsado()} <= viva


@pytest.mark.integration
async def test_ninguna_emision_desaparece_al_colapsar(saneado) -> None:
    """Colapsar reduce filas, nunca emisiones: cada clave del universo tiene que seguir teniendo al
    menos una fila en la vista del armador."""
    dedup = saneado.emisiones()
    en_la_colapsada = {e.raiz for e in dedup.colapsado()}
    assert en_la_colapsada == set(dedup.por_raiz)


@pytest.mark.integration
async def test_ninguna_especie_descartada_representa_a_su_emision(saneado) -> None:
    """El criterio 2 sobre el universo de verdad: un dato roto nunca es la cara visible del bono,
    salvo que todas las especies de la emisión estén rotas — y ahí no hay a quién elegir."""
    dedup = saneado.emisiones()
    descartados = saneado.sanidad.descartados
    for emision in dedup.emisiones:
        representante = emision.representante
        if representante is None or representante.ticker not in descartados:
            continue
        assert all(e.ticker in descartados for e in emision.especies), emision.raiz


@pytest.mark.integration
async def test_el_universo_real_tiene_emisiones_con_varias_especies(saneado) -> None:
    """Si esto diera cero, la feature no estaría haciendo nada sobre el universo de hoy y todos los
    tests de arriba pasarían por vacuidad. Es el testigo de que hay algo que deduplicar."""
    dedup = saneado.emisiones()
    assert any(len(e.especies) > 1 for e in dedup.emisiones)
