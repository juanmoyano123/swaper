"""Los tres endpoints de la ficha de instrumento — F-039.

Lo que se prueba acá es el contrato HTTP de cada uno, por separado: la deduplicación de especies ya
está probada sin levantar nada en `test_universo_emisiones.py`, la matemática del cronograma en
`test_calendario_cupones.py`, y el triplete campo/origen/fecha en
`test_condiciones_persistencia.py`. Una conexión falsa que despacha por SQL, mismo patrón que
`FakeConexionCalendario` en
`test_calendario_api.py`: universo, condiciones y cashflow son tres consultas distintas, y un fake
que devolviera lo mismo a las tres no probaría que cada endpoint lee lo que dice leer.
"""

from datetime import date
from typing import Any

import pytest

from app.condiciones.semilla import CAMPOS
from tests.conftest import cliente

FICHA = "/api/v1/instrumentos/{ticker}"
CONDICIONES = "/api/v1/instrumentos/{ticker}/condiciones"
CRONOGRAMA = "/api/v1/instrumentos/{ticker}/cronograma"

# AL30 / AL30D / AL30C: la misma emisión en pesos, MEP y cable — mismas duraciones, así que
# deduplica en una sola emisión con dos hermanas por especie. S30J6 no comparte raíz con nadie:
# es el caso "sin hermanas".
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "AL30",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.12,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 65_000.0,
        "effectiveVolume": 1_000.0,
        "moneda_cotizacion": "ARS",
        "paridad": 0.7,
    },
    {
        "ticker": "AL30D",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.121,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 43.0,
        "effectiveVolume": 500.0,
        "moneda_cotizacion": "USD",
        "paridad": 0.7,
    },
    {
        "ticker": "AL30C",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.119,
        "tna": None,
        "duration": 3.5,
        "maturity": date(2030, 7, 9),
        "law": "Ley Argentina",
        "couponCurrency": "USD",
        "underlying": "Gobierno Argentino",
        "lastPrice": 43.2,
        "effectiveVolume": 300.0,
        "moneda_cotizacion": "USD",
        "paridad": 0.7,
    },
    {
        "ticker": "S30J6",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "tasa-fija",
        "tir": None,
        "tna": 0.35,
        "duration": 0.5,
        "maturity": date(2027, 6, 30),
        "law": "Ley Argentina",
        "couponCurrency": "ARS",
        "underlying": "Gobierno Argentino",
        "lastPrice": 130.0,
        "effectiveVolume": 9_000.0,
        "moneda_cotizacion": "ARS",
        "paridad": 0.98,
    },
]

# Dos pagos futuros de AL30 (raíz de AL30/AL30D/AL30C): uno de renta pura y uno de capital+renta al
# vencimiento. `residual_value` no importa para estos endpoints — no calculan valor técnico, sólo
# listan los pagos tal como vienen.
FILAS_CASHFLOW: list[dict[str, Any]] = [
    {
        "ticker": "AL30",
        "issue_date": date(2020, 1, 9),
        "payment_date": date(2028, 1, 9),
        "capital": 0.0,
        "interest_amount": 1.5,
        "residual_value": 100.0,
        "cash_flow": 1.5,
    },
    {
        "ticker": "AL30",
        "issue_date": date(2020, 1, 9),
        "payment_date": date(2030, 7, 9),
        "capital": 100.0,
        "interest_amount": 1.5,
        "residual_value": 0.0,
        "cash_flow": 101.5,
    },
]


def _fila_condiciones(ticker: str, **valores: Any) -> dict[str, Any]:
    """Una fila de `condiciones_emision` con el triplete completo de cada campo de `CAMPOS`."""
    fila: dict[str, Any] = {"ticker": ticker}
    for campo in CAMPOS:
        fila[campo] = valores.get(campo)
        fila[f"{campo}_origen"] = valores.get(f"{campo}_origen")
        fila[f"{campo}_fecha"] = valores.get(f"{campo}_fecha")
    return fila


CONDICIONES_AL30 = _fila_condiciones(
    "AL30",
    ley="Ley Argentina",
    ley_origen="condiciones_emision.csv (curado)",
    ley_fecha="2026-08-05",
    calificacion=None,
    calificacion_origen=None,
    calificacion_fecha=None,
)


class FakeConexionInstrumentos:
    """Conexión falsa que despacha por consulta: universo, condiciones o cashflow."""

    def __init__(
        self,
        universo: list[dict[str, Any]] | None = None,
        condiciones: dict[str, dict[str, Any]] | None = None,
        cashflow: list[dict[str, Any]] | None = None,
    ) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.condiciones = {} if condiciones is None else condiciones
        self.cashflow = FILAS_CASHFLOW if cashflow is None else cashflow
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        if "public.cashflow" in query:
            return self.cashflow
        return self.universo

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        self.consultas.append(query)
        (ticker,) = args
        return self.condiciones.get(ticker)


@pytest.fixture
def app_con_instrumentos(crear_app):
    def _crear(**kwargs: Any):
        return crear_app(FakeConexionInstrumentos(**kwargs))

    return _crear


# --- GET /instrumentos/{ticker} -------------------------------------------------------------------


async def test_un_ticker_vivo_trae_sus_dos_hermanas(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ticker"] == "AL30D"
    assert cuerpo["especie"]["ticker"] == "AL30D"
    assert cuerpo["especie"]["emision"] == "AL30"
    assert cuerpo["especie"]["dato_sano"] is True
    assert {h["ticker"] for h in cuerpo["hermanas"]} == {"AL30", "AL30C"}


async def test_un_ticker_sin_hermanas_trae_la_lista_vacia(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="S30J6"))

    cuerpo = respuesta.json()
    assert cuerpo["especie"]["ticker"] == "S30J6"
    assert cuerpo["hermanas"] == []


async def test_un_ticker_fuera_del_universo_da_404(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(FICHA.format(ticker="NOEXISTE"))

    assert respuesta.status_code == 404


async def test_ficha_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(FICHA.format(ticker="AL30D"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/condiciones -------------------------------------------------------


async def test_condiciones_presentes_traen_origen_y_fecha(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos(condiciones={"AL30": CONDICIONES_AL30})) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 200
    condiciones_ = respuesta.json()["condiciones"]
    assert condiciones_["ley"] == "Ley Argentina"
    assert condiciones_["ley_origen"] == "condiciones_emision.csv (curado)"
    assert condiciones_["ley_fecha"] == "2026-08-05"
    assert condiciones_["calificacion"] is None


async def test_condiciones_ausentes_no_es_404(app_con_instrumentos) -> None:
    """Que no haya condiciones curadas para un ticker es un estado normal (GWT-2), no un error."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ticker": "AL30", "condiciones": None}


async def test_condiciones_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(CONDICIONES.format(ticker="AL30"))

    assert respuesta.status_code == 503


# --- GET /instrumentos/{ticker}/cronograma ----------------------------------------------------


async def test_cronograma_con_pagos_distingue_interes_de_amortizacion(app_con_instrumentos) -> None:
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["ticker"] == "AL30D"
    assert len(cuerpo["pagos"]) == 2
    solo_renta, capital_y_renta = cuerpo["pagos"]
    assert solo_renta["interes"] == 1.5
    assert solo_renta["amortizacion"] == 0.0
    assert capital_y_renta["amortizacion"] == 100.0
    assert capital_y_renta["interes"] == 1.5
    # La moneda sale del universo (couponCurrency), no se infiere del sufijo del ticker.
    assert cuerpo["pagos"][0]["moneda"] == "USD"


async def test_cronograma_vacio_no_es_404(app_con_instrumentos) -> None:
    """Sin cronograma para la raíz puede ser legítimamente un instrumento sin cashflow cargado."""
    async with cliente(app_con_instrumentos()) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="S30J6"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ticker": "S30J6", "pagos": []}


async def test_cronograma_sin_universo_declara_moneda_nula(app_con_instrumentos) -> None:
    """Sin fuente que declare la moneda de un ticker fuera del universo, se declara `null` y no se
    inventa a partir del sufijo del ticker (regla 1 del proyecto)."""
    async with cliente(app_con_instrumentos(universo=[], cashflow=FILAS_CASHFLOW)) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    cuerpo = respuesta.json()
    assert len(cuerpo["pagos"]) == 2
    assert all(pago["moneda"] is None for pago in cuerpo["pagos"])


async def test_cronograma_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(CRONOGRAMA.format(ticker="AL30D"))

    assert respuesta.status_code == 503
