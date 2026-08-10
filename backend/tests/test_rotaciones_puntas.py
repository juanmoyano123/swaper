"""Lectura de puntas bid/ask — F-035, `app/rotaciones/puntas.py`.

El caso que motiva este archivo es de tipos, no de SQL: `public.puntas` guarda las puntas como
`numeric`, que asyncpg entrega como `Decimal`. Si esos `Decimal` viajan sin convertir, el costo
revienta al mezclarlos con el arancel, que es `float` — y revienta sólo contra la base real, porque
los fixtures de los otros tests usan `float` directamente. Un 500 en `POST /rotaciones` que ninguna
suite veía.
"""

from decimal import Decimal

import pytest

from app.rotaciones.costos import calcular_costo, spread_pct
from app.rotaciones.puntas import leer_puntas


class FakeConexionPuntas:
    """Devuelve las filas tal como las entrega asyncpg para una columna `numeric`."""

    def __init__(self, filas: list[dict]) -> None:
        self._filas = filas
        self.sql_recibido: str | None = None

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        self.sql_recibido = sql
        return self._filas


@pytest.mark.asyncio
async def test_las_puntas_llegan_como_float_aunque_la_base_las_de_en_decimal() -> None:
    conn = FakeConexionPuntas(
        [{"ticker": "AL30D", "px_bid": Decimal("125.50"), "px_ask": Decimal("126.10"), "fuente": "byma"}]
    )

    puntas = await leer_puntas(conn, ["AL30D"])

    bid, ask = puntas["AL30D"]
    assert isinstance(bid, float)
    assert isinstance(ask, float)
    assert bid == pytest.approx(125.50)
    assert ask == pytest.approx(126.10)


@pytest.mark.asyncio
async def test_el_costo_se_calcula_sobre_las_puntas_leidas_sin_romper_por_tipos() -> None:
    """La cadena entera: leer de la base → spread → costo. Es el camino que devolvía 500."""
    conn = FakeConexionPuntas(
        [
            {"ticker": "AL30D", "px_bid": Decimal("125.50"), "px_ask": Decimal("126.10"), "fuente": "byma"},
            {"ticker": "AE38D", "px_bid": Decimal("98.20"), "px_ask": Decimal("99.00"), "fuente": "byma"},
        ]
    )

    puntas = await leer_puntas(conn, ["AL30D", "AE38D"])
    bid_o, ask_o = puntas["AL30D"]
    bid_d, ask_d = puntas["AE38D"]

    costo = calcular_costo(spread_pct(bid_o, ask_o), spread_pct(bid_d, ask_d), 1.8)

    assert costo.verificable is True
    assert costo.total_pct is not None
    assert isinstance(costo.total_pct, float)


@pytest.mark.asyncio
async def test_una_punta_de_arrastre_no_es_una_punta_viva() -> None:
    conn = FakeConexionPuntas(
        [{"ticker": "AL30D", "px_bid": Decimal("125.50"), "px_ask": Decimal("126.10"), "fuente": "byma-arrastre"}]
    )

    assert (await leer_puntas(conn, ["AL30D"]))["AL30D"] == (None, None)


@pytest.mark.asyncio
async def test_un_ticker_sin_fila_sale_sin_punta() -> None:
    conn = FakeConexionPuntas([{"ticker": "AL30D", "px_bid": None, "px_ask": None, "fuente": None}])

    assert (await leer_puntas(conn, ["AL30D"]))["AL30D"] == (None, None)


@pytest.mark.asyncio
async def test_sin_tickers_no_consulta_la_base() -> None:
    conn = FakeConexionPuntas([])

    assert await leer_puntas(conn, []) == {}
    assert conn.sql_recibido is None
