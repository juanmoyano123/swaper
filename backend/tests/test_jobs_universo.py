"""Lo que el refresh intra-rueda lee del universo ya persistido, sin volver a golpear IAMC ni
Docta: qué tickers ya están en `instrumentos` y el `type` del cronograma tal como quedó guardado.
"""

from app.jobs.universo import (
    filtrar_precios_al_universo,
    leer_tickers_existentes,
    leer_tipos_cronograma,
)
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


async def test_lee_los_tipos_de_cronograma_como_dicts() -> None:
    conn = _FakeFetch([{"ticker": "AL30", "type": "HARD_DOLLAR"}])
    resultado = await leer_tipos_cronograma(conn)
    assert resultado == [{"ticker": "AL30", "type": "HARD_DOLLAR"}]


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
