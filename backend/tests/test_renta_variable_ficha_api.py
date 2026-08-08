"""El contrato HTTP de `GET /renta-variable/{ticker}/ficha` — F-053.

La conexión falsa y las filas son las de `test_renta_variable_api.py`: la ficha lee lo mismo que el
listado, y duplicar los fixtures haría que un cambio en el shape de la fila dejara uno de los dos
tests probando un universo que ya no existe.

Yahoo se mockea con `respx`. La propiedad que sostienen estos tests es la que importa el día que la
fuente cambie: **la ficha responde 200 con el bloque propio pase lo que pase con Yahoo**.
"""

from typing import Any

import httpx
import pytest
import respx

from app.api.v1 import renta_variable as modulo_endpoint
from app.externos.yahoo import (
    URL_CHART,
    URL_COOKIE,
    URL_CRUMB,
    URL_PERFIL,
    ClienteYahoo,
    Reintentos,
)
from tests.conftest import cliente
from tests.test_renta_variable_api import AAPL, GGAL, FakeConexionRentaVariable
from tests.test_yahoo_cliente import chart, perfil

RUTA = "/api/v1/renta-variable/{ticker}/ficha"
CHART_GGAL = URL_CHART.format(simbolo="GGAL.BA")
PERFIL_GGAL = URL_PERFIL.format(simbolo="GGAL.BA")


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def app_con_ficha(crear_app, monkeypatch):
    """App con el universo pedido y un cliente de Yahoo que no espera ni comparte caché entre tests.

    El cliente del proceso es un singleton (`lru_cache`) justamente para que la caché de TTL sirva;
    acá se reemplaza por uno nuevo en cada test para que el resultado de uno no filtre al siguiente.
    """

    def _crear(**kwargs: Any):
        yahoo = ClienteYahoo(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))
        monkeypatch.setattr(modulo_endpoint, "cliente_yahoo", lambda: yahoo)
        return crear_app(FakeConexionRentaVariable(**kwargs))

    return _crear


def _montar_yahoo_entero() -> None:
    respx.get(url__startswith=CHART_GGAL).mock(return_value=httpx.Response(200, json=chart()))
    respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
    respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
    respx.get(url__startswith=PERFIL_GGAL).mock(return_value=httpx.Response(200, json=perfil()))


async def test_camino_feliz_trae_los_dos_bloques_con_su_fuente(app_con_ficha) -> None:
    """GWT-1: el nombre de la empresa según Yahoo, el precio de BYMA, y cada bloque rotulado."""
    with respx.mock:
        _montar_yahoo_entero()
        async with cliente(app_con_ficha(renta_variable=[GGAL, AAPL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["fuente"] == "BYMA"
    assert cuerpo["propio"]["precio"] == 5000.0
    assert cuerpo["propio"]["px_bid"] == 4995.0
    assert cuerpo["propio"]["operaciones"] == 120
    assert cuerpo["externo"]["fuente"] == "Yahoo Finance"
    assert cuerpo["externo"]["disponible"] is True
    assert cuerpo["externo"]["cotizacion"]["nombre_largo"] == "Grupo Financiero Galicia S.A."
    assert cuerpo["externo"]["cotizacion"]["capturado_en"] is not None
    assert cuerpo["externo"]["perfil"]["sector"] == "Financial Services"


async def test_yahoo_caido_responde_igual_con_el_bloque_propio(app_con_ficha) -> None:
    """GWT-4: ninguna pantalla del producto se rompe porque la fuente externa no esté."""
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(side_effect=httpx.ConnectError("sin red"))
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["precio"] == 5000.0
    assert cuerpo["externo"]["disponible"] is False
    assert cuerpo["externo"]["motivo"]
    assert cuerpo["externo"]["cotizacion"] is None


async def test_crumb_roto_deja_cotizacion_y_declara_el_perfil_ausente(app_con_ficha) -> None:
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(401, text="Unauthorized"))
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    cuerpo = respuesta.json()["externo"]
    assert cuerpo["disponible"] is True
    assert cuerpo["cotizacion"]["precio"] == 5000.0
    assert cuerpo["perfil"] is None
    assert cuerpo["perfil_motivo"]


async def test_bolsa_distinta_de_bue_no_muestra_el_dato_recibido(app_con_ficha) -> None:
    """GWT-3: en ningún caso se muestran los datos de otro instrumento."""
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(
            return_value=httpx.Response(200, json=chart(exchangeName="NMS", longName="Otra Cosa"))
        )
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    cuerpo = respuesta.json()
    assert cuerpo["externo"]["disponible"] is False
    assert cuerpo["externo"]["cotizacion"] is None
    assert "Otra Cosa" not in respuesta.text


async def test_ningun_campo_de_opinion_viaja_en_la_respuesta(app_con_ficha) -> None:
    """GWT-5: recomendación, precio objetivo y consenso no aparecen ni aunque la fuente los mande.

    Se mira el texto crudo de la respuesta y no el objeto ya parseado: el punto es que ninguno de
    esos valores salga del proceso, no que estén en otro campo.
    """
    con_opinion = perfil(
        recommendationKey="STRONG_BUY", targetMeanPrice=9000.0, numberOfAnalystOpinions=17
    )
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
        respx.get(url__startswith=PERFIL_GGAL).mock(
            return_value=httpx.Response(200, json=con_opinion)
        )
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    texto = respuesta.text
    assert "STRONG_BUY" not in texto
    assert "recommendation" not in texto
    assert "targetMeanPrice" not in texto and "9000" not in texto


async def test_ticker_que_no_es_renta_variable_da_404(app_con_ficha) -> None:
    """Es también cómo el frontend distingue una acción de un bono sin adivinarlo por el ticker."""
    with respx.mock:
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="AL30"))

    assert respuesta.status_code == 404


async def test_la_ficha_no_trae_rendimiento(app_con_ficha) -> None:
    """Una acción no tiene TIR (regla 2) y este contrato tampoco le hace lugar."""
    with respx.mock:
        _montar_yahoo_entero()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert "rendimiento" not in respuesta.json()["propio"]


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 503
