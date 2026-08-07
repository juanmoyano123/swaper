"""Lo que el refresh intra-rueda lee del universo ya persistido, sin volver a golpear IAMC ni Docta.

El cronograma lo lee `persistencia.leer_cronograma` desde F-051 y ya no vive acá: el refresh
necesita el flujo entero, no sólo el `type`, porque de él salen también las métricas calculadas.
"""

from app.ingesta.consolidacion.persistencia import leer_cronograma
from app.jobs.universo import filtrar_precios_al_universo, leer_tickers_existentes
from tests.conftest import FakeConnection


class _FakeFetch(FakeConnection):
    def __init__(self, filas: list[dict]) -> None:
        super().__init__()
        self._filas = filas

    async def fetch(self, query: str, *args) -> list[dict]:
        self._registrar(query)
        return self._filas


async def test_lee_los_tickers_existentes_como_set() -> None:
    conn = _FakeFetch([{"ticker": "AL30"}, {"ticker": "GD30"}])
    resultado = await leer_tickers_existentes(conn)
    assert resultado == {"AL30", "GD30"}


async def test_tickers_existentes_vacio_si_no_hay_instrumentos() -> None:
    conn = _FakeFetch([])
    assert await leer_tickers_existentes(conn) == set()


async def test_el_cronograma_persistido_llega_con_los_montos_y_no_solo_con_el_tipo() -> None:
    """Con `ticker` y `type` alcanzaba para clasificar, pero no para descontar: cada refresco
    dejaría la fila de precios sin TIR y la vista publicaría el universo sin rendimiento."""
    fila = {
        "ticker": "AL30",
        "type": "HARD_DOLLAR",
        "payment_date": "2030-07-09",
        "capital": 8.0,
        "interest_amount": 0.07,
        "residual_value": 0.0,
        "cash_flow": 8.07,
    }
    conn = _FakeFetch([fila])
    assert await leer_cronograma(conn) == [fila]


def test_filtra_precios_al_universo() -> None:
    precios = [
        {"ticker": "AL30", "last_price": 156000.0},
        {"ticker": "NUEVO", "last_price": 100.0},
    ]
    en_universo, fuera = filtrar_precios_al_universo(precios, {"AL30"})
    assert en_universo == [{"ticker": "AL30", "last_price": 156000.0}]
    assert fuera == ["NUEVO"]


def test_filtra_precios_al_universo_sin_nada_afuera() -> None:
    precios = [{"ticker": "AL30", "last_price": 156000.0}]
    en_universo, fuera = filtrar_precios_al_universo(precios, {"AL30", "GD30"})
    assert en_universo == precios
    assert fuera == []


def test_filtra_precios_al_universo_ordena_los_que_quedan_afuera() -> None:
    precios = [{"ticker": "ZZZ"}, {"ticker": "AAA"}]
    _, fuera = filtrar_precios_al_universo(precios, set())
    assert fuera == ["AAA", "ZZZ"]
