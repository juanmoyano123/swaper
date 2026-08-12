"""GWT-1/2/3 de la ficha F-006: token vencido vs API caída vs vacío errático — y que el token
nunca aparezca en un log ni en una alerta.

`respx` intercepta el tránsito HTTP sin importar qué instancia de `httpx.AsyncClient` lo dispare
(la crea `crear_cliente()` adentro de `ingerir_cashflow`), así que no hace falta inyectar el
cliente. `dormir` se inyecta como corrutina nula para no esperar de verdad los 3/6/9/12 segundos
entre reintentos.
"""

import io
import logging

import pandas as pd
import respx
from httpx import Response, TimeoutException

from app.core.config import Settings
from app.ingesta.alertas import (
    CODIGO_CREDENCIAL_VENCIDA,
    CODIGO_FORMATO_INESPERADO,
    CODIGO_FUENTE_CAIDA,
    CODIGO_RESPUESTA_VACIA,
)
from app.ingesta.docta.ingesta import ingerir_cashflow

# El token falso viaja embebido en la query string, tal como lo hace el link real de Docta.
TOKEN_FALSO = "secreto-de-prueba-9f3a"
URL_DE_PRUEBA = f"https://docta.test/api/cash-flow?token={TOKEN_FALSO}&fromDate=2020-01-01"

COLUMNAS_REALES = (
    "ticker",
    "type",
    "issue_date",
    "payment_date",
    "capital",
    "interest_rate",
    "interest_amount",
    "residual_value",
    "cash_flow",
    "days_convention",
    "theoretical_payment_date",
    "theoretical_days_before",
)


def excel_de_cashflow(filas: int) -> bytes:
    """Arma bytes de un xlsx en memoria con `filas` pagos, las 12 columnas reales por defecto."""
    datos = {
        "ticker": ["AL30"] * filas,
        "type": ["AMORT"] * filas,
        "issue_date": [pd.Timestamp("2020-09-04")] * filas,
        "payment_date": [pd.Timestamp("2026-01-09")] * filas,
        "capital": [1.75] * filas,
        "interest_rate": [0.0125] * filas,
        "interest_amount": [0.5] * filas,
        "residual_value": [98.25] * filas,
        "cash_flow": [2.25] * filas,
        "days_convention": ["30/360"] * filas,
        "theoretical_payment_date": [pd.Timestamp("2026-01-09")] * filas,
        "theoretical_days_before": [0] * filas,
    }
    df = pd.DataFrame(datos, columns=COLUMNAS_REALES)
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)
    return buffer.getvalue()


def _settings() -> Settings:
    return Settings(docta_cashflow_url=URL_DE_PRUEBA, docta_api_token=TOKEN_FALSO)


async def _no_dormir(_: float) -> None:
    return None


# --- GWT-1: token vencido -------------------------------------------------------------------


@respx.mock
async def test_un_500_de_token_vencido_alerta_regenerar_y_no_reintenta() -> None:
    ruta = respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(500, content=b"Error al verificar el token")
    )

    resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    assert ruta.call_count == 1, "un token vencido no se arregla reintentando"
    assert resultado.filas is None
    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_CREDENCIAL_VENCIDA
    assert alerta.accion_requerida is not None
    assert "Docta Terminal" in alerta.accion_requerida


def test_el_resultado_distingue_fallo_de_lista_de_filas() -> None:
    """La otra mitad de "conservar el último cashflow válido": el contrato para quien persiste."""
    from app.ingesta.docta.ingesta import ResultadoCashflow
    from app.ingesta.snapshot import Snapshot

    exito = ResultadoCashflow(filas=[{"ticker": "AL30"}], snapshot=Snapshot(fuente="Docta"))
    fallo = ResultadoCashflow(filas=None, snapshot=Snapshot(fuente="Docta"))

    assert exito.filas is not None
    assert fallo.filas is None


# --- GWT-2: API caída, distinta de token vencido --------------------------------------------


@respx.mock
async def test_un_timeout_alerta_fuente_caida_y_no_credencial() -> None:
    respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        side_effect=TimeoutException("tardó demasiado")
    )

    resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    assert resultado.filas is None
    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_FUENTE_CAIDA
    assert alerta.accion_requerida is None


@respx.mock
async def test_un_500_generico_se_reintenta_y_alerta_fuente_caida() -> None:
    ruta = respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(500, content=b"Internal Server Error")
    )

    resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    assert ruta.call_count == 5, "un 500 genérico sí se reintenta, a diferencia del de token"
    assert resultado.filas is None
    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_FUENTE_CAIDA
    assert alerta.accion_requerida is None


async def test_token_vencido_y_api_caida_tienen_codigos_distintos() -> None:
    assert CODIGO_CREDENCIAL_VENCIDA != CODIGO_FUENTE_CAIDA


# --- GWT-3: cero filas erráticas, hasta 5 reintentos con espera creciente --------------------


@respx.mock
async def test_un_excel_vacio_erratico_se_reintenta_hasta_que_trae_filas() -> None:
    respuestas = [
        Response(200, content=excel_de_cashflow(0)),
        Response(200, content=excel_de_cashflow(0)),
        Response(200, content=excel_de_cashflow(3)),
    ]
    ruta = respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        side_effect=respuestas
    )
    esperas: list[float] = []

    async def dormir_y_registrar(segundos: float) -> None:
        esperas.append(segundos)

    resultado = await ingerir_cashflow(_settings(), dormir=dormir_y_registrar)

    assert ruta.call_count == 3
    assert resultado.filas is not None
    assert len(resultado.filas) == 3
    assert resultado.snapshot.alertas == []
    assert esperas == [3, 6]


@respx.mock
async def test_cinco_vacios_seguidos_declaran_respuesta_vacia() -> None:
    ruta = respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(200, content=excel_de_cashflow(0))
    )

    resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    assert ruta.call_count == 5
    assert resultado.filas is None
    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_RESPUESTA_VACIA


# --- fromDate reescrito viaja efectivamente en el request ------------------------------------


@respx.mock
async def test_el_fromdate_reescrito_es_el_que_viaja_en_el_request() -> None:
    from datetime import date, timedelta

    ruta = respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(200, content=excel_de_cashflow(1))
    )

    await ingerir_cashflow(_settings(), dormir=_no_dormir)

    esperado = (date.today() - timedelta(days=15)).strftime("%Y-%m-%d")
    request_enviado = ruta.calls.last.request
    assert f"fromDate={esperado}" in str(request_enviado.url)


# --- Columnas rotas: formato inesperado -------------------------------------------------------


@respx.mock
async def test_columnas_faltantes_declara_formato_inesperado() -> None:
    df = pd.DataFrame({"ticker": ["AL30"], "type": ["AMORT"]})  # faltan 7 de las 9
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False)

    respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(200, content=buffer.getvalue())
    )

    resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    assert resultado.filas is None
    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_FORMATO_INESPERADO


# --- El token nunca aparece en logs ni alertas -------------------------------------------------


@respx.mock
async def test_el_token_no_aparece_en_ningun_log_ni_alerta(caplog) -> None:
    respx.get(url__startswith="https://docta.test/api/cash-flow").mock(
        return_value=Response(500, content=b"Error al verificar el token")
    )

    with caplog.at_level(logging.DEBUG):
        resultado = await ingerir_cashflow(_settings(), dormir=_no_dormir)

    for registro in caplog.records:
        assert TOKEN_FALSO not in registro.getMessage()

    for alerta in resultado.snapshot.alertas:
        assert TOKEN_FALSO not in str(alerta.como_dict())

    assert TOKEN_FALSO not in str(resultado.snapshot.como_dict())
