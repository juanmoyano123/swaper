"""El contrato HTTP de `GET /renta-variable/especies` — F-052.

Fake que despacha por SQL, mismo patrón que `FakeConexionInstrumentos` de
`test_instrumentos_api.py`: la lectura de renta variable y la lectura del universo (para el tipo de
cambio) son dos consultas distintas, y un fake que devolviera lo mismo a las dos no probaría que el
endpoint lee lo que dice leer. El universo que se usa para el tipo de cambio tiene menos de
`MIN_PARES_FX` pares a propósito: es el caso real y declarado (GWT-2) en el que el volumen en
dólares de las especies en pesos queda `s/d`.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from tests.conftest import cliente

RUTA = "/api/v1/renta-variable/especies"

# Universo mínimo para `sanear_universo`: dos bonos sin tipo de tasa reconocido no aportan ningún
# par al tipo de cambio, así que el FX del día queda no disponible — igual que si hubiera cero
# bonos, pero más parecido al universo real, que siempre tiene renta fija además de renta variable.
FILAS_UNIVERSO_SIN_FX: list[dict[str, Any]] = [
    {"ticker": "AL30", "clase_activo": "bono_soberano"},
    {"ticker": "GD30", "clase_activo": "bono_soberano"},
]

GGAL = {
    "ticker": "GGAL",
    "clase_activo": "accion",
    "lastPrice": 5000.0,
    "effectiveVolume": 1_500_000_000.0,
    "cierre_anterior": 4850.0,
    "moneda_cotizacion": "ARS",
    "px_bid": 4995.0,
    "px_ask": 5005.0,
    "operaciones": 120,
}

# Sin cierre anterior: el caso "cero" de la migración, primera corrida posterior a agregarla.
YPFD = {
    "ticker": "YPFD",
    "clase_activo": "accion",
    "lastPrice": 30_000.0,
    "effectiveVolume": 800_000_000.0,
    "cierre_anterior": None,
    "moneda_cotizacion": "ARS",
    "px_bid": None,
    "px_ask": None,
    "operaciones": 50,
}

AAPL = {
    "ticker": "AAPL",
    "clase_activo": "cedear",
    "lastPrice": 43.0,
    "effectiveVolume": 2_000_000.0,
    "cierre_anterior": 42.0,
    "moneda_cotizacion": "USD",
    "px_bid": 42.9,
    "px_ask": 43.1,
    "operaciones": 30,
}


class FakeConexionRentaVariable:
    """Conexión falsa que despacha por consulta: la lectura de renta variable o la del universo."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        renta_variable: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO_SIN_FX if universo is None else universo
        self.renta_variable = [] if renta_variable is None else renta_variable
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "clase_activo IN" in query:
            return self.renta_variable
        return self.universo


@pytest.fixture
def app_con_renta_variable(crear_app):
    def _crear(**kwargs: Any):
        return crear_app(FakeConexionRentaVariable(**kwargs))

    return _crear


async def test_clase_accion_devuelve_solo_acciones(app_con_renta_variable) -> None:
    async with cliente(app_con_renta_variable(renta_variable=[GGAL, YPFD, AAPL])) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    assert respuesta.status_code == 200
    tickers = {f["ticker"] for f in respuesta.json()["items"]}
    assert tickers == {"GGAL", "YPFD"}


async def test_clase_cedear_devuelve_solo_cedears(app_con_renta_variable) -> None:
    async with cliente(app_con_renta_variable(renta_variable=[GGAL, YPFD, AAPL])) as http:
        respuesta = await http.get(RUTA, params={"clase": "cedear"})

    assert respuesta.status_code == 200
    tickers = {f["ticker"] for f in respuesta.json()["items"]}
    assert tickers == {"AAPL"}


async def test_ninguna_fila_trae_rendimiento(app_con_renta_variable) -> None:
    """GWT-1: ni la columna existe en el contrato, ni nada viaja en su lugar."""
    async with cliente(app_con_renta_variable(renta_variable=[GGAL, AAPL])) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    assert all("rendimiento" not in fila for fila in respuesta.json()["items"])


async def test_sin_fila_de_perfil_los_campos_nuevos_viajan_en_null(app_con_renta_variable) -> None:
    """Una especie que el job de clasificación todavía no tocó no inventa nombre: viaja declarado
    vacío, no ausente del contrato."""
    async with cliente(app_con_renta_variable(renta_variable=[GGAL])) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    (ggal,) = respuesta.json()["items"]
    assert ggal["nombre_largo"] is None
    assert ggal["perfil_fuente"] is None
    assert ggal["perfil_capturado_en"] is None


async def test_con_fila_de_perfil_los_campos_nuevos_viajan_tal_cual(app_con_renta_variable) -> None:
    # `perfil_capturado_en` llega de asyncpg como `datetime` (columna timestamptz), no como texto.
    ggal_con_perfil = {
        **GGAL,
        "nombre_largo": "Grupo Financiero Galicia S.A.",
        "perfil_fuente": "SEC EDGAR",
        "perfil_capturado_en": datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
    }
    async with cliente(app_con_renta_variable(renta_variable=[ggal_con_perfil])) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    (ggal,) = respuesta.json()["items"]
    assert ggal["nombre_largo"] == "Grupo Financiero Galicia S.A."
    assert ggal["perfil_fuente"] == "SEC EDGAR"
    assert ggal["perfil_capturado_en"] == "2026-08-09T12:00:00+00:00"


async def test_fila_ars_sin_fx_da_volumen_usd_null_y_la_usd_lo_conserva(
    app_con_renta_variable,
) -> None:
    """GWT-2: sin tipo de cambio del día, ARS queda `s/d` y nunca el crudo travestido de dólares."""
    async with cliente(app_con_renta_variable(renta_variable=[GGAL])) as http:
        respuesta_accion = await http.get(RUTA, params={"clase": "accion"})
    async with cliente(app_con_renta_variable(renta_variable=[AAPL])) as http:
        respuesta_cedear = await http.get(RUTA, params={"clase": "cedear"})

    (ggal,) = respuesta_accion.json()["items"]
    (aapl,) = respuesta_cedear.json()["items"]
    assert ggal["volumen_usd"] is None
    assert aapl["volumen_usd"] == aapl["volumen"]


async def test_variacion_con_cierre_anterior_none_es_null_y_con_ambos_es_el_cociente(
    app_con_renta_variable,
) -> None:
    """GWT-3: lo que falta se declara vacío, nunca se estima desde el histórico."""
    async with cliente(app_con_renta_variable(renta_variable=[GGAL, YPFD])) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    filas = {f["ticker"]: f for f in respuesta.json()["items"]}
    assert filas["YPFD"]["variacion"] is None
    assert filas["GGAL"]["variacion"] == pytest.approx((5000.0 - 4850.0) / 4850.0)


async def test_paginacion_con_limit_1_trae_next_cursor_y_la_segunda_pagina_la_otra(
    app_con_renta_variable,
) -> None:
    async with cliente(app_con_renta_variable(renta_variable=[GGAL, YPFD])) as http:
        primera = await http.get(RUTA, params={"clase": "accion", "limit": 1})
        assert primera.json()["next_cursor"] is not None

        segunda = await http.get(
            RUTA, params={"clase": "accion", "limit": 1, "cursor": primera.json()["next_cursor"]}
        )

    tickers = {primera.json()["items"][0]["ticker"], segunda.json()["items"][0]["ticker"]}
    assert tickers == {"GGAL", "YPFD"}


async def test_clase_invalida_da_422(app_con_renta_variable) -> None:
    async with cliente(app_con_renta_variable()) as http:
        respuesta = await http.get(RUTA, params={"clase": "bono"})

    assert respuesta.status_code == 422


async def test_sin_clase_da_422(app_con_renta_variable) -> None:
    async with cliente(app_con_renta_variable()) as http:
        respuesta = await http.get(RUTA)

    assert respuesta.status_code == 422


async def test_clase_valida_sin_filas_da_pagina_vacia_no_404(app_con_renta_variable) -> None:
    async with cliente(app_con_renta_variable(renta_variable=[])) as http:
        respuesta = await http.get(RUTA, params={"clase": "cedear"})

    assert respuesta.status_code == 200
    assert respuesta.json()["items"] == []


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(RUTA, params={"clase": "accion"})

    assert respuesta.status_code == 503
