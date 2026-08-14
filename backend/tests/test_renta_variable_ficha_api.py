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
from app.externos.sec_ficha import URL_COMPANYFACTS, URL_SUBMISSIONS, URL_TICKERS, ClienteSecFicha
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
HISTORICO_AAPL = URL_HISTORICO.format(base=DATA912_BASE_URL, tramo="cedears", ticker="AAPL")
SUBMISSIONS_AAPL = URL_SUBMISSIONS.format(cik=320193)
COMPANYFACTS_AAPL = URL_COMPANYFACTS.format(cik=320193)


async def _no_dormir(_: float) -> None:
    return None


def _barra(fecha: str, cierre: float) -> dict[str, Any]:
    """Una barra cruda de data912, con los campos no documentados incluidos: el parser tiene que
    ignorar `dr`/`sa` y no romper si están."""
    return {"date": fecha, "o": cierre, "h": cierre, "l": cierre, "c": cierre, "v": 100.0}


@pytest.fixture
def app_con_ficha(crear_app, monkeypatch):
    """App con el universo pedido y clientes de Yahoo, data912 y la SEC que no esperan ni
    comparten caché entre tests.

    Los tres clientes del proceso son singletons (`lru_cache`) justamente para que sus cachés de
    TTL sirvan; acá se reemplazan por instancias nuevas en cada test para que el resultado de uno
    no filtre al siguiente — el caché de fallos de 60 s es el más traicionero, y el de la SEC
    además cachea el mapa de tickers entero.
    """

    def _crear(**kwargs: Any):
        yahoo = ClienteYahoo(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))
        monkeypatch.setattr(modulo_endpoint, "cliente_yahoo", lambda: yahoo)
        historico = ClienteData912Historico(
            dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0)
        )
        monkeypatch.setattr(modulo_endpoint, "cliente_data912_historico", lambda: historico)
        sec = ClienteSecFicha(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))
        monkeypatch.setattr(modulo_endpoint, "cliente_sec_ficha", lambda: sec)
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


def _company_tickers() -> dict[str, Any]:
    return {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}


def _companyfacts_aapl() -> dict[str, Any]:
    """Un filer doméstico (us-gaap, con `frame` trimestral y anual) recortado a los conceptos que
    `sec_ficha_parser` conoce — alcanza para que `datos_del_ejercicio` ancle un ejercicio y
    `calcular_ratios` devuelva los seis ratios, sin pretender ser un companyfacts real de Apple."""

    def _instante(valor: float) -> dict[str, Any]:
        return {"units": {"USD": [{"end": "2025-09-27", "val": valor}]}}

    def _flujo_anual(valor: float, *, unidad: str = "USD") -> dict[str, Any]:
        return {
            "units": {
                unidad: [
                    {
                        "start": "2024-09-29",
                        "end": "2025-09-27",
                        "val": valor,
                        "frame": "CY2025",
                    },
                    {
                        "start": "2023-10-01",
                        "end": "2024-09-28",
                        "val": valor * 0.8,
                        "frame": "CY2024",
                    },
                ]
            }
        }

    return {
        "facts": {
            "us-gaap": {
                "Assets": _instante(100.0),
                "StockholdersEquity": _instante(50.0),
                "AssetsCurrent": _instante(60.0),
                "LiabilitiesCurrent": _instante(30.0),
                "CashAndCashEquivalentsAtCarryingValue": _instante(15.0),
                "LongTermDebt": _instante(40.0),
                "Revenues": _flujo_anual(120.0),
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            *_flujo_anual(20.0)["units"]["USD"],
                            {
                                "start": "2025-06-29",
                                "end": "2025-09-27",
                                "val": 6.0,
                                "frame": "CY2025Q3",
                            },
                        ]
                    }
                },
                "OperatingIncomeLoss": _flujo_anual(30.0),
                "EarningsPerShareDiluted": _flujo_anual(1.25, unidad="USD/shares"),
            }
        }
    }


def _submissions_aapl() -> dict[str, Any]:
    return {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q"],
                "filingDate": ["2025-10-31", "2025-08-01"],
                "accessionNumber": ["0000320193-25-000123", "0000320193-25-000098"],
                "primaryDocument": ["aapl-20250927.htm", "aapl-20250628.htm"],
            }
        }
    }


def _montar_sec_aapl() -> None:
    respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_company_tickers()))
    respx.get(SUBMISSIONS_AAPL).mock(return_value=httpx.Response(200, json=_submissions_aapl()))
    respx.get(COMPANYFACTS_AAPL).mock(return_value=httpx.Response(200, json=_companyfacts_aapl()))


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
    # GGAL es 'accion': el bloque sec se declara ausente sin pedirle nada a la SEC — si hubiera
    # intentado red, `respx.mock` (sin ninguna ruta de la SEC montada) haría fallar el test entero.
    assert cuerpo["sec"]["fuente"] == "SEC EDGAR"
    assert cuerpo["sec"]["disponible"] is False
    assert "no es un CEDEAR" in cuerpo["sec"]["motivo_ausente"]


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


# --- El paquete de estados contables de la SEC (14/08/2026) --------------------------------------


async def test_un_cedear_trae_el_paquete_sec_con_ratios(app_con_ficha, monkeypatch) -> None:
    """AAPL es cedear: la ficha pide el mapa de tickers, submissions y companyfacts, y arma los
    ratios sobre el mismo ejercicio ancla. Yahoo se pausa para no tener que montar además un chart
    de AAPL — el bloque `sec` no depende de Yahoo."""
    monkeypatch.setenv("YAHOO_HABILITADO", "false")
    get_settings.cache_clear()

    with respx.mock:
        respx.get(HISTORICO_AAPL).mock(return_value=httpx.Response(200, json=[]))
        _montar_sec_aapl()
        async with cliente(app_con_ficha(renta_variable=[AAPL])) as http:
            respuesta = await http.get(RUTA.format(ticker="AAPL"))

    assert respuesta.status_code == 200
    sec = respuesta.json()["sec"]
    assert sec["fuente"] == "SEC EDGAR"
    assert sec["disponible"] is True
    assert sec["motivo_ausente"] is None
    assert sec["solo_anual"] is False, "hay un punto trimestral con frame CY2025Q3 en el fixture"
    assert sec["cik"] == "320193"
    assert {f["form"] for f in sec["filings"]} == {"10-K", "10-Q"}
    assert all(
        f["url_documento"].startswith("https://www.sec.gov/Archives/edgar/data/320193/")
        for f in sec["filings"]
    )

    ratios = sec["ratios"]
    assert ratios["roe"] == {"valor": 20.0 / 50.0, "unidad": None, "periodo": "2025-09-27"}
    assert ratios["margen_operativo"] == {
        "valor": 30.0 / 120.0,
        "unidad": None,
        "periodo": "2025-09-27",
    }
    assert ratios["crecimiento_ingresos"]["valor"] == pytest.approx((120.0 - 96.0) / 96.0)
    assert ratios["eps"] == {"valor": 1.25, "unidad": "USD/shares", "periodo": "2025-09-27"}
    assert ratios["deuda_patrimonio"] == {
        "valor": 40.0 / 50.0,
        "unidad": None,
        "periodo": "2025-09-27",
    }
    assert ratios["liquidez_corriente"] == {
        "valor": 60.0 / 30.0,
        "unidad": None,
        "periodo": "2025-09-27",
    }


async def test_la_sec_caida_no_tumba_la_ficha_ni_arrastra_a_los_otros_bloques(
    app_con_ficha, monkeypatch
) -> None:
    monkeypatch.setenv("YAHOO_HABILITADO", "false")
    get_settings.cache_clear()

    with respx.mock:
        respx.get(HISTORICO_AAPL).mock(
            return_value=httpx.Response(200, json=[_barra("2026-08-13", 43.0)])
        )
        respx.get(URL_TICKERS).mock(side_effect=httpx.ConnectError("sin red"))
        async with cliente(app_con_ficha(renta_variable=[AAPL])) as http:
            respuesta = await http.get(RUTA.format(ticker="AAPL"))

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["propio"]["precio"] == 43.0
    assert cuerpo["historico"]["disponible"] is True, "un fallo de la SEC no arrastra al histórico"
    assert cuerpo["sec"]["disponible"] is False
    assert cuerpo["sec"]["motivo_ausente"]
    assert cuerpo["sec"]["ratios"] is None
