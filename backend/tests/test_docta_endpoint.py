"""`POST /docta/ingesta`: 200 con el snapshot tanto en éxito como en fallo de fuente (la corrida
corrió; el status HTTP no es lo que declara si sirvió), y 503 sólo cuando falta configuración.
"""

import io

import pandas as pd
import pytest
import respx
from httpx import Response

from tests.conftest import cliente as crear_cliente_http

URL_DE_PRUEBA = "https://docta.test/api/cash-flow?token=${DOCTA_API_TOKEN}&fromDate=2020-01-01"


def _excel_con_una_fila() -> bytes:
    df = pd.DataFrame(
        {
            "ticker": ["AL30"],
            "type": ["AMORT"],
            "issue_date": [pd.Timestamp("2020-09-04")],
            "payment_date": [pd.Timestamp("2026-01-09")],
            "capital": [1.75],
            "interest_rate": [0.0125],
            "interest_amount": [0.5],
            "residual_value": [98.25],
            "cash_flow": [2.25],
        }
    )
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def _config_docta(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("DOCTA_CASHFLOW_URL", URL_DE_PRUEBA)
    monkeypatch.setenv("DOCTA_API_TOKEN", "token-de-prueba")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@respx.mock
async def test_el_endpoint_responde_200_con_snapshot_cuando_la_ingesta_sale_bien(
    crear_app,
) -> None:
    respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(200, content=_excel_con_una_fila())
    )

    app = crear_app()
    async with crear_cliente_http(app) as http:
        respuesta = await http.post("/api/v1/docta/ingesta")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["snapshot"]["fuente"] == "Docta"
    assert cuerpo["snapshot"]["filas_por_tramo"] == {"cash-flow": 1}
    assert cuerpo["snapshot"]["completo"] is True


@respx.mock
async def test_el_endpoint_responde_200_con_snapshot_aunque_la_fuente_falle(crear_app) -> None:
    respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(500, content=b"Error al verificar el token")
    )

    app = crear_app()
    async with crear_cliente_http(app) as http:
        respuesta = await http.post("/api/v1/docta/ingesta")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["snapshot"]["completo"] is False
    assert cuerpo["snapshot"]["alertas"][0]["codigo"] == "credencial_vencida"


async def test_el_endpoint_responde_503_si_falta_docta_cashflow_url(
    crear_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.delenv("DOCTA_CASHFLOW_URL", raising=False)
    get_settings.cache_clear()

    app = crear_app()
    async with crear_cliente_http(app) as http:
        respuesta = await http.post("/api/v1/docta/ingesta")

    assert respuesta.status_code == 503
    assert "DOCTA_CASHFLOW_URL" in respuesta.json()["error"]["message"]
