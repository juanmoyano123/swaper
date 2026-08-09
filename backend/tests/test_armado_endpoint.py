"""El endpoint del armado asistido — F-019, `POST /api/v1/armado`.

Lo que se prueba acá es el **contrato HTTP**: qué viaja, qué se rechaza y qué pasa sin base. El
algoritmo de selección ya está probado sin levantar nada en `test_armado_paridad_motor.py` y
`test_armado_min_sectores.py`, así que este archivo no lo vuelve a recorrer — mismo criterio que
`test_concentracion_api.py` frente a `test_concentracion_servicio.py`.
"""

from typing import Any

import pytest

from tests.conftest import cliente

RUTA = "/api/v1/armado"

# Sólo instrumentos `usd_hard`: con la cobertura por defecto ("mixta", que reparte también en cer,
# tasa_fija y dollar_linked) los otros tres segmentos quedan sin candidatos a propósito, para poder
# probar la cartera parcial del GWT-3 sin tener que armar cuatro segmentos completos.
FILAS_UNIVERSO: list[dict[str, Any]] = [
    {
        "ticker": "YMCHO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.07,
        "duration": 3.0,
        "sector": "O&G",
        "underlying": "YPF S.A.",
        "lastPrice": 99.0,
    },
    {
        "ticker": "PECNO",
        "clase_activo": "on_corporativo",
        "tipo_tasa": "hard-dollar",
        "tir": 0.075,
        "duration": 3.5,
        "sector": "Servicios",
        "underlying": "Pecom S.A.",
        "lastPrice": 100.0,
    },
    {
        "ticker": "AL30",
        "clase_activo": "bono_soberano",
        "tipo_tasa": "hard-dollar",
        "tir": 0.08,
        "duration": 2.0,
        "sector": "Soberano",
        "lastPrice": 86.0,
    },
]


class FakeConexionArmado:
    """Conexión falsa con una sola consulta: el armado, como la concentración, sólo lee el
    universo."""

    def __init__(self, universo: list[dict[str, Any]] | None = None) -> None:
        self.universo = FILAS_UNIVERSO if universo is None else universo
        self.consultas: list[str] = []

    async def fetch(self, query: str, *_: Any) -> list[dict[str, Any]]:
        self.consultas.append(query)
        return self.universo


@pytest.fixture
def app_con_universo(crear_app):
    def _crear(**kwargs):
        return crear_app(FakeConexionArmado(**kwargs))

    return _crear


async def test_arma_una_cartera_parcial_cuando_el_universo_no_alcanza(app_con_universo) -> None:
    """GWT-3: sin candidatos en cer/tasa_fija/dollar_linked, la cartera sale igual con lo que hay
    en usd_hard y declara qué segmentos quedaron sin candidatos -- nunca se rellena con otra
    naturaleza."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo["posiciones"]) > 0
    tickers = {p["ticker"] for p in cuerpo["posiciones"]}
    assert tickers <= {"YMCHO", "PECNO", "AL30"}
    # La cartera se reescala a 100% con lo único que se pudo cubrir (usd_hard).
    assert sum(p["pct_cartera"] for p in cuerpo["posiciones"]) == pytest.approx(100.0, abs=0.5)
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert "segmento_sin_candidatos" in codigos
    assert cuerpo["origen_mix"] == "mix balanceado (por defecto)"


async def test_la_respuesta_trae_el_contrato_completo(app_con_universo) -> None:
    pedido = {"monto": 50_000, "cobertura": "devaluacion", "moneda": "usd"}
    async with cliente(app_con_universo()) as http:
        cuerpo = (await http.post(RUTA, json=pedido)).json()

    assert set(cuerpo) == {
        "posiciones",
        "mix_aplicado",
        "origen_mix",
        "perfil",
        "sectores",
        "alertas",
    }
    assert set(cuerpo["sectores"]) == {"presentes", "minimo", "suficiente"}
    if cuerpo["posiciones"]:
        assert set(cuerpo["posiciones"][0]) == {"ticker", "pct_cartera", "monto"}


async def test_un_mix_con_segmento_desconocido_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000, "mix": {"no_existe": 100}})

    assert respuesta.status_code == 422


async def test_un_monto_no_positivo_se_rechaza(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        assert (await http.post(RUTA, json={"monto": 0})).status_code == 422
        assert (await http.post(RUTA, json={"monto": -1000})).status_code == 422


async def test_una_moneda_sin_segmentos_del_mix_se_rechaza(app_con_universo) -> None:
    """`--moneda usd` sobre una cobertura 100% en pesos no tiene nada que armar: es un pedido mal
    formado (422), no un hecho de la cartera (200 con alerta)."""
    async with cliente(app_con_universo()) as http:
        respuesta = await http.post(
            RUTA, json={"monto": 100_000, "cobertura": "tasa-pesos", "moneda": "usd"}
        )

    assert respuesta.status_code == 422


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.post(RUTA, json={"monto": 100_000})

    assert respuesta.status_code == 503


async def test_el_endpoint_hace_una_sola_consulta(crear_app) -> None:
    conexion = FakeConexionArmado()
    async with cliente(crear_app(conexion)) as http:
        await http.post(RUTA, json={"monto": 100_000})

    assert len(conexion.consultas) == 1
