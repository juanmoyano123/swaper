"""F-029 contra la base real. Marcado `integration`, fuera de la corrida por defecto.

Lo que sólo se puede verificar acá es que `instrumentos.plazo_liquidacion` exista, se lea y traiga
lo que la resolución espera —el código de BYMA sin traducir— y que la distinción entre "no existe"
y "existe pero no es comparable" sea real y no una hipótesis: `GGAL` es una acción y `RUCEX` una ON
sin tipo de tasa reconocido, y los dos están en la base.

**Las aserciones son sobre invariantes, no sobre números del día.** Cuántas posiciones resuelven
depende de la corrida de ingesta que haya pasado último. Lo que tiene que valer siempre es que un
ticker declarado no se convierta en otro, que lo no resuelto siga en la cartera y que el porcentaje
se calcule sobre la base que declara.
"""

from pathlib import Path

import asyncpg
import pytest
from dotenv import dotenv_values

from app.posiciones import PosicionDeclarada, resolver_cartera
from app.posiciones.lectura import leer_instrumentos
from app.posiciones.resolucion import MotivoNoResuelta

pytestmark = pytest.mark.integration

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


def posicion(ticker: str, monto: float | None, fila: int) -> PosicionDeclarada:
    return PosicionDeclarada(id=f"p{fila}", fila=fila, ticker_declarado=ticker, monto=monto)


# Una cartera de prueba con un caso de cada cosa: soberanos y ONs que existen, una acción, una ON
# sin tipo de tasa, un ticker que no existe y uno escrito a mano con espacios y en minúsculas.
CARTERA = [
    posicion("AL30D", 5264.50, 1),
    posicion("GD30D", 8100.00, 2),
    posicion("MR46O", 3200.00, 3),
    posicion("RUCEO", 1500.00, 4),
    posicion("TX26", 2200.00, 5),
    posicion("GGAL", 4000.00, 6),
    posicion("RUCEX", 900.00, 7),
    posicion("NOEXISTE1", 700.00, 8),
    posicion("  al30 ", 1000.00, 9),
]


@pytest.fixture
async def cartera(conexion):
    return await resolver_cartera(conexion, CARTERA)


def por_declarado(cartera, ticker: str):
    (resuelta,) = [p for p in cartera.posiciones if p.declarada.ticker_declarado == ticker]
    return resuelta


async def test_la_columna_de_plazo_existe_y_llega_con_el_codigo_sin_traducir(conexion) -> None:
    """Si `plazo_liquidacion` no estuviera en `instrumentos`, esto falla con un error de SQL antes
    de la primera aserción, que es justo lo que tiene que pasar."""
    filas = await leer_instrumentos(conexion)

    assert filas
    plazos = {f["plazo_liquidacion"] for f in filas}
    # `"1"` / `"2"` de BYMA, o vacío. Nunca "48hs": nadie mapeó esos códigos en este proyecto.
    assert plazos <= {"1", "2", None}


async def test_ninguna_posicion_se_pierde_al_resolver(cartera) -> None:
    assert len(cartera.posiciones) == len(CARTERA)
    assert cartera.cobertura.posiciones == len(CARTERA)
    assert cartera.cobertura.resueltas + cartera.cobertura.no_resueltas == len(CARTERA)


async def test_ningun_ticker_declarado_se_convierte_en_otro(cartera) -> None:
    """La invariante central: lo resuelto es exactamente lo que se pidió, salvo caja y espacios."""
    for p in cartera.posiciones:
        if p.especie is not None:
            assert p.especie.ticker == p.declarada.ticker_declarado.strip().upper()


async def test_una_accion_no_se_reporta_como_ticker_inexistente(cartera) -> None:
    ggal = por_declarado(cartera, "GGAL")

    assert not ggal.resuelta
    assert ggal.motivo is MotivoNoResuelta.RENTA_VARIABLE
    assert ggal.clase_activo == "accion"


async def test_rucex_existe_no_resuelve_y_no_se_deriva_a_ruceo(cartera) -> None:
    rucex = por_declarado(cartera, "RUCEX")
    ruceo = por_declarado(cartera, "RUCEO")

    assert not rucex.resuelta
    assert rucex.motivo is MotivoNoResuelta.SIN_TIPO_DE_TASA
    # La hermana sí resuelve, y eso no arrastra a RUCEX: son dos tickers distintos.
    assert ruceo.resuelta


async def test_el_ticker_escrito_a_mano_resuelve_sin_perder_lo_declarado(cartera) -> None:
    escrito = por_declarado(cartera, "  al30 ")

    assert escrito.resuelta
    assert escrito.especie is not None
    assert escrito.especie.ticker == "AL30"


async def test_las_posiciones_resueltas_traen_plazo_de_liquidacion(cartera) -> None:
    """Hoy la cobertura del plazo es total; si dejara de serlo, sale la alerta en vez de un plazo
    inventado. La aserción es sobre el par —o hay plazo, o hay alerta— y no sobre el número."""
    resueltas = [p for p in cartera.posiciones if p.resuelta]

    assert resueltas
    for p in resueltas:
        assert p.plazo_liquidacion in {"1", "2", None}
    if any(p.plazo_liquidacion is None for p in resueltas):
        assert "plazo_de_liquidacion_no_disponible" in {a.codigo for a in cartera.alertas}


async def test_el_porcentaje_se_calcula_sobre_el_monto_declarado(cartera) -> None:
    cobertura = cartera.cobertura

    assert cobertura.posiciones_con_monto == len(CARTERA)
    assert cobertura.monto_declarado == pytest.approx(sum(p.monto or 0 for p in CARTERA))
    assert cobertura.porcentaje_no_resuelto is not None
    esperado = cobertura.monto_no_resuelto / cobertura.monto_declarado * 100
    assert cobertura.porcentaje_no_resuelto == pytest.approx(esperado)


async def test_lo_no_resuelto_conserva_su_monto(cartera) -> None:
    no_resueltas = cartera.no_resueltas

    assert no_resueltas
    assert all(p.declarada.monto is not None for p in no_resueltas)
    assert cartera.cobertura.monto_no_resuelto == pytest.approx(
        sum(p.declarada.monto or 0 for p in no_resueltas)
    )
