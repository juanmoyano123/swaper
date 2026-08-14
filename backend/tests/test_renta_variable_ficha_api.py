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
from app.core.config import get_settings
from app.externos.data912 import BASE_URL as DATA912_BASE_URL
from app.externos.data912 import URL_HISTORICO, ClienteData912Historico
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
from tests.test_yahoo_cliente import chart, empresa, estadisticas, perfil

RUTA = "/api/v1/renta-variable/{ticker}/ficha"
CHART_GGAL = URL_CHART.format(simbolo="GGAL.BA")
PERFIL_GGAL = URL_PERFIL.format(simbolo="GGAL.BA")
HISTORICO_GGAL = URL_HISTORICO.format(base=DATA912_BASE_URL, tramo="stocks", ticker="GGAL")


async def _no_dormir(_: float) -> None:
    return None


def _barra(fecha: str, cierre: float) -> dict[str, Any]:
    """Una barra cruda de data912, con los campos no documentados incluidos: el parser tiene que
    ignorar `dr`/`sa` y no romper si están."""
    return {"date": fecha, "o": cierre, "h": cierre, "l": cierre, "c": cierre, "v": 100.0}


@pytest.fixture
def app_con_ficha(crear_app, monkeypatch):
    """App con el universo pedido y clientes de Yahoo y de data912 que no esperan ni comparten
    caché entre tests.

    Los dos clientes del proceso son singletons (`lru_cache`) justamente para que sus cachés de
    TTL sirvan; acá se reemplazan por instancias nuevas en cada test para que el resultado de uno
    no filtre al siguiente — el caché de fallos de 60 s del histórico es el más traicionero.
    """

    def _crear(**kwargs: Any):
        yahoo = ClienteYahoo(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))
        monkeypatch.setattr(modulo_endpoint, "cliente_yahoo", lambda: yahoo)
        historico = ClienteData912Historico(
            dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0)
        )
        monkeypatch.setattr(modulo_endpoint, "cliente_data912_historico", lambda: historico)
        return crear_app(FakeConexionRentaVariable(**kwargs))

    return _crear


def _montar_yahoo_entero(nivel_2: dict[str, Any] | None = None) -> None:
    respx.get(url__startswith=CHART_GGAL).mock(return_value=httpx.Response(200, json=chart()))
    respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
    respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
    respx.get(url__startswith=PERFIL_GGAL).mock(
        return_value=httpx.Response(200, json=nivel_2 if nivel_2 is not None else perfil())
    )


def _montar_data912_historico(disponible: bool = True) -> None:
    """El histórico de data912 para GGAL. La mayoría de los tests de este archivo no prueban el
    histórico: lo montan sólo para que la ficha no revienta pidiéndolo (`bloque_historico` es la
    tercera llamada de red del endpoint desde la Etapa 5)."""
    cuerpo = [_barra("2026-08-12", 5000.0), _barra("2026-08-13", 5100.0)] if disponible else []
    respx.get(HISTORICO_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))


async def test_camino_feliz_trae_los_dos_bloques_con_su_fuente(app_con_ficha) -> None:
    """GWT-1: el nombre de la empresa según Yahoo, el precio de BYMA, y cada bloque rotulado."""
    with respx.mock:
        _montar_yahoo_entero()
        _montar_data912_historico()
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
    assert cuerpo["historico"]["fuente"] == "data912"
    assert cuerpo["historico"]["disponible"] is True
    assert cuerpo["historico"]["puntos"] == [
        {"fecha": "2026-08-12", "cierre": 5000.0},
        {"fecha": "2026-08-13", "cierre": 5100.0},
    ]


async def test_yahoo_caido_responde_igual_con_el_bloque_propio(app_con_ficha) -> None:
    """GWT-4: ninguna pantalla del producto se rompe porque la fuente externa no esté."""
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(side_effect=httpx.ConnectError("sin red"))
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["precio"] == 5000.0
    assert cuerpo["externo"]["disponible"] is False
    assert cuerpo["externo"]["motivo"]
    assert cuerpo["externo"]["cotizacion"] is None
    assert cuerpo["historico"]["disponible"] is True, "un fallo de Yahoo no arrastra al histórico"


async def test_crumb_roto_deja_cotizacion_y_declara_el_perfil_ausente(app_con_ficha) -> None:
    with respx.mock:
        respx.get(url__startswith=CHART_GGAL).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(401, text="Unauthorized"))
        _montar_data912_historico()
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
        _montar_data912_historico()
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
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    texto = respuesta.text
    assert "STRONG_BUY" not in texto
    assert "recommendation" not in texto
    assert "targetMeanPrice" not in texto and "9000" not in texto


async def test_la_valuacion_viaja_con_sus_ratios_y_sus_montos_con_moneda(app_con_ficha) -> None:
    """PER, price-to-book y beta van solos; el EPS va con la moneda que declaró la fuente."""
    with respx.mock:
        _montar_yahoo_entero(empresa(estadisticas()))
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    valuacion = respuesta.json()["externo"]["valuacion"]
    assert valuacion["per_forward"] == 7.70
    assert valuacion["beta"] == 0.315
    assert valuacion["ganancia_por_accion"] == {"valor": 53.4, "moneda": "ARS"}
    assert valuacion["montos_sin_moneda"] == []


async def test_un_monto_sin_moneda_no_viaja_y_el_faltante_se_declara(app_con_ficha) -> None:
    """Regla 11 sobre el CEDEAR: sin moneda declarada, el número no sale — y se dice que faltó."""
    sin_moneda = estadisticas(trailingEps={"raw": 134_603.95}, enterpriseValue={"raw": 4.66e15})
    with respx.mock:
        _montar_yahoo_entero(empresa(sin_moneda))
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    valuacion = respuesta.json()["externo"]["valuacion"]
    assert valuacion["ganancia_por_accion"] is None
    assert set(valuacion["montos_sin_moneda"]) == {"trailingEps", "enterpriseValue"}
    assert "134603.95" not in respuesta.text and "134,603.95" not in respuesta.text
    assert valuacion["precio_sobre_libros"] == 1.37


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
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert "rendimiento" not in respuesta.json()["propio"]


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 503


# --- La pausa de Yahoo (13/08/2026) --------------------------------------------------------------


async def test_con_yahoo_pausado_la_ficha_responde_con_el_bloque_declarado(
    app_con_ficha, monkeypatch
) -> None:
    """Con la pausa activa no se le pide nada a Yahoo: sólo se monta el histórico de data912, y
    cualquier request real a Yahoo revienta el test contra `respx.mock` sin esa ruta."""
    monkeypatch.setenv("YAHOO_HABILITADO", "false")
    get_settings.cache_clear()

    with respx.mock:
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["precio"] == 5000.0, "el bloque propio sostiene la pantalla igual"
    externo = cuerpo["externo"]
    assert externo["disponible"] is False
    assert "pausado" in externo["motivo"]
    assert externo["simbolo_consultado"] == "GGAL.BA"
    assert externo["cotizacion"] is None
    assert externo["perfil"] is None
    assert externo["valuacion"] is None
    assert cuerpo["historico"]["disponible"] is True, "la pausa de Yahoo no afecta a data912"


# --- El histórico de data912 en la ficha ---------------------------------------------------------


async def test_la_ficha_trae_el_bloque_historico_de_data912(app_con_ficha) -> None:
    with respx.mock:
        _montar_yahoo_entero()
        _montar_data912_historico()
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    historico = respuesta.json()["historico"]
    assert historico == {
        "fuente": "data912",
        "disponible": True,
        "motivo": None,
        "puntos": [
            {"fecha": "2026-08-12", "cierre": 5000.0},
            {"fecha": "2026-08-13", "cierre": 5100.0},
        ],
    }


async def test_data912_caido_no_tumba_la_ficha_y_el_historico_se_declara_ausente(
    app_con_ficha,
) -> None:
    with respx.mock:
        _montar_yahoo_entero()
        respx.get(HISTORICO_GGAL).mock(side_effect=httpx.ConnectError("sin red"))
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["precio"] == 5000.0
    assert cuerpo["externo"]["disponible"] is True, "un fallo de data912 no arrastra a Yahoo"
    assert cuerpo["historico"]["disponible"] is False
    assert cuerpo["historico"]["motivo"]
    assert cuerpo["historico"]["puntos"] == []


async def test_data912_sin_serie_para_el_ticker_se_declara_sin_romper_la_ficha(
    app_con_ficha,
) -> None:
    """El caso real medido el 13/08/2026: un ticker inexistente responde HTTP 200 con
    `{"Error": ...}` en vez de una lista."""
    with respx.mock:
        _montar_yahoo_entero()
        respx.get(HISTORICO_GGAL).mock(
            return_value=httpx.Response(200, json={"Error": "Nahh no tengo ese ticker loko"})
        )
        async with cliente(app_con_ficha(renta_variable=[GGAL])) as http:
            respuesta = await http.get(RUTA.format(ticker="GGAL"))

    historico = respuesta.json()["historico"]
    assert historico["disponible"] is False
    assert historico["puntos"] == []
