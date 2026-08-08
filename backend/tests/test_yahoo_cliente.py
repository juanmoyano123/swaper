"""El cliente de Yahoo Finance — F-053, sin salir a la red.

Todo se mockea con `respx`, igual que el cliente de BYMA: la fuente no es contractual y una suite
que dependiera de que Yahoo esté vivo fallaría por motivos que no son nuestros. Lo que se prueba acá
es exactamente lo que la ficha necesita que sea cierto el día que la fuente cambie:

- el nivel 1 y el nivel 2 fallan por separado y ninguno tumba al otro;
- una respuesta de otra bolsa o de otro símbolo no se muestra, se declara (regla 11);
- los campos de opinión de Yahoo no entran ni aunque la fuente los mande (regla 6).
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from app.externos.yahoo import (
    URL_CHART,
    URL_COOKIE,
    URL_CRUMB,
    URL_PERFIL,
    ClienteYahoo,
    Reintentos,
)

SIMBOLO = "GGAL.BA"
CHART = URL_CHART.format(simbolo=SIMBOLO)
PERFIL = URL_PERFIL.format(simbolo=SIMBOLO)

# Epoch de dos ruedas consecutivas, y el desfase de Buenos Aires que la propia respuesta declara.
RUEDA_1 = 1_786_024_800  # 06/08/2026, 11:00 en Buenos Aires
RUEDA_2 = 1_786_111_200  # 07/08/2026, 11:00 en Buenos Aires
GMT_OFFSET = -10_800


def chart(**meta: Any) -> dict[str, Any]:
    base = {
        "currency": "ARS",
        "symbol": SIMBOLO,
        "exchangeName": "BUE",
        "fullExchangeName": "Buenos Aires",
        "instrumentType": "EQUITY",
        "longName": "Grupo Financiero Galicia S.A.",
        "shortName": "GRUPO FINANCIERO GALICIA",
        "regularMarketPrice": 5000.0,
        "chartPreviousClose": 4850.0,
        "regularMarketDayHigh": 5100.0,
        "regularMarketDayLow": 4900.0,
        "fiftyTwoWeekHigh": 7000.0,
        "fiftyTwoWeekLow": 3000.0,
        "regularMarketVolume": 1_500_000,
        "gmtoffset": GMT_OFFSET,
    }
    base.update(meta)
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": base,
                    "timestamp": [RUEDA_1, RUEDA_2],
                    # El `None` del medio es un día sin cierre publicado: se saltea, no se rellena.
                    "indicators": {"quote": [{"close": [4850.0, None]}]},
                }
            ],
        }
    }


def perfil(**campos: Any) -> dict[str, Any]:
    base = {
        "country": "Argentina",
        "sector": "Financial Services",
        "industry": "Banks - Regional",
        "website": "https://www.gfgsa.com",
        "fullTimeEmployees": 12000,
    }
    base.update(campos)
    return {"quoteSummary": {"error": None, "result": [{"assetProfile": base}]}}


async def _no_dormir(_: float) -> None:
    return None


def cliente(**kwargs: Any) -> ClienteYahoo:
    """Cliente que no espera de verdad y con reloj de pared fijo, para comparar el sello."""
    kwargs.setdefault("dormir", _no_dormir)
    kwargs.setdefault("politica", Reintentos(intentos=2, espera_base=0))
    kwargs.setdefault("ahora", lambda: datetime(2026, 8, 8, 14, 30, tzinfo=UTC))
    return ClienteYahoo(**kwargs)


def _montar_nivel_2() -> None:
    respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
    respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
    respx.get(url__startswith=PERFIL).mock(return_value=httpx.Response(200, json=perfil()))


# --- Camino feliz ---------------------------------------------------------------------------------


async def test_camino_feliz_trae_cotizacion_perfil_e_historico() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is True
    assert bloque.motivo is None
    assert bloque.cotizacion is not None
    assert bloque.cotizacion.precio == 5000.0
    assert bloque.cotizacion.moneda == "ARS"
    assert bloque.cotizacion.nombre_largo == "Grupo Financiero Galicia S.A."
    assert bloque.cotizacion.capturado_en == "2026-08-08T14:30:00+00:00"
    assert bloque.perfil is not None
    assert bloque.perfil.sector == "Financial Services"
    assert bloque.perfil_motivo is None


async def test_el_historico_saltea_los_dias_sin_cierre_y_fecha_en_el_huso_de_la_bolsa() -> None:
    """Un día sin cierre no se interpola ni se arrastra: no está y punto (regla 1)."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.cotizacion is not None
    assert [(p.fecha, p.cierre) for p in bloque.cotizacion.historico] == [("2026-08-06", 4850.0)]


async def test_el_simbolo_es_el_ticker_con_sufijo_y_nada_mas() -> None:
    """GWT-2: un CEDEAR se consulta como `{ticker}.BA`, sin derivar el símbolo del subyacente."""
    with respx.mock:
        ruta = respx.get(url__startswith=URL_CHART.format(simbolo="MSFT.BA")).mock(
            return_value=httpx.Response(200, json=chart(symbol="MSFT.BA"))
        )
        _montar_nivel_2()
        respx.get(url__startswith=URL_PERFIL.format(simbolo="MSFT.BA")).mock(
            return_value=httpx.Response(200, json=perfil(country="United States"))
        )
        bloque = await cliente().bloque_externo("msft")

    assert ruta.called
    assert bloque.simbolo_consultado == "MSFT.BA"
    assert bloque.perfil is not None
    assert bloque.perfil.pais == "United States"


# --- Los guardias de la regla 11 ------------------------------------------------------------------


async def test_bolsa_distinta_de_bue_deja_el_bloque_vacio_y_declarado() -> None:
    """GWT-3: el papel de otro mercado no se muestra con nuestro ticker en el título."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(
            return_value=httpx.Response(200, json=chart(exchangeName="NMS", currency="USD"))
        )
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is False
    assert bloque.cotizacion is None
    assert bloque.motivo is not None and "otra bolsa" in bloque.motivo


async def test_simbolo_distinto_del_pedido_deja_el_bloque_vacio_y_declarado() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(
            return_value=httpx.Response(200, json=chart(symbol="GGAL"))
        )
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is False
    assert bloque.cotizacion is None


# --- Degradación ----------------------------------------------------------------------------------


async def test_yahoo_caido_no_lanza_y_declara_el_bloque_no_disponible() -> None:
    """GWT-4: la fuente entera abajo devuelve un bloque declarado, nunca una excepción."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(side_effect=httpx.ConnectError("sin red"))
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is False
    assert bloque.cotizacion is None and bloque.perfil is None
    assert bloque.motivo is not None


async def test_crumb_roto_conserva_el_nivel_1_y_declara_vacio_el_nivel_2() -> None:
    """El 401 de 2023 otra vez: la cotización sigue, el perfil se declara ausente."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(401, text="Unauthorized"))
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is True
    assert bloque.cotizacion is not None
    assert bloque.perfil is None
    assert bloque.perfil_motivo is not None


async def test_crumb_que_vuelve_como_html_no_se_usa_como_crumb() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="<html>Error</html>"))
        ruta_perfil = respx.get(url__startswith=PERFIL).mock(
            return_value=httpx.Response(200, json=perfil())
        )
        bloque = await cliente().bloque_externo("GGAL")

    assert ruta_perfil.called is False
    assert bloque.cotizacion is not None
    assert bloque.perfil is None


async def test_perfil_caido_conserva_la_cotizacion() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
        respx.get(url__startswith=PERFIL).mock(return_value=httpx.Response(500))
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.cotizacion is not None
    assert bloque.perfil is None and bloque.perfil_motivo is not None


async def test_la_fuente_limitando_lo_dice_en_castellano_y_no_se_le_insiste() -> None:
    """429 medido el 08/08/2026 contra esta IP: se declara y no se vuelve a golpear por un rato."""
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(url__startswith=CHART).mock(return_value=httpx.Response(429))
        yahoo = cliente(reloj=reloj)
        primero = await yahoo.bloque_externo("GGAL")
        segundo = await yahoo.bloque_externo("GGAL")

    assert ruta.call_count == 1
    assert primero.motivo == segundo.motivo
    assert primero.motivo is not None and "limitando los pedidos" in primero.motivo


async def test_vencida_la_anotacion_del_fallo_se_vuelve_a_intentar() -> None:
    """La anotación no puede convertirse en "no disponible" para siempre."""
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(url__startswith=CHART).mock(
            side_effect=[httpx.Response(429), httpx.Response(200, json=chart())]
        )
        _montar_nivel_2()
        yahoo = cliente(reloj=reloj, ttl_fallo=60.0)
        await yahoo.bloque_externo("GGAL")
        reloj.t = 90.0
        bloque = await yahoo.bloque_externo("GGAL")

    assert ruta.call_count == 2
    assert bloque.disponible is True


async def test_cuerpo_que_no_es_json_no_rompe() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, text="no soy json"))
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.disponible is False


async def test_un_500_se_reintenta_y_la_segunda_vuelta_sirve() -> None:
    with respx.mock:
        respx.get(url__startswith=CHART).mock(
            side_effect=[httpx.Response(500), httpx.Response(200, json=chart())]
        )
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.cotizacion is not None


# --- Lo que no se pide ni se muestra --------------------------------------------------------------


async def test_solo_se_pide_el_modulo_de_perfil() -> None:
    """GWT-5: los módulos de opinión no se piden. El que no se pide no se puede filtrar mal."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
        ruta = respx.get(url__startswith=PERFIL).mock(
            return_value=httpx.Response(200, json=perfil())
        )
        await cliente().bloque_externo("GGAL")

    pedida = str(ruta.calls.last.request.url)
    assert "modules=assetProfile" in pedida
    assert "financialData" not in pedida and "recommendationTrend" not in pedida


async def test_los_campos_de_opinion_no_entran_aunque_la_fuente_los_mande() -> None:
    """GWT-5: el perfil se arma campo por campo, así que un campo nuevo de la fuente no se cuela."""
    con_opinion = perfil(
        recommendationKey="STRONG_BUY", targetMeanPrice=9000.0, numberOfAnalystOpinions=17
    )
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
        respx.get(url__startswith=PERFIL).mock(return_value=httpx.Response(200, json=con_opinion))
        bloque = await cliente().bloque_externo("GGAL")

    serializado = str(bloque.como_dict())
    assert "STRONG_BUY" not in serializado
    assert "9000" not in serializado
    assert "17" not in serializado


async def test_el_vocabulario_de_la_fuente_no_se_traduce() -> None:
    """GWT-6: "Banks - Regional" viaja tal cual; traducirlo sería nuestra interpretación."""
    with respx.mock:
        respx.get(url__startswith=CHART).mock(return_value=httpx.Response(200, json=chart()))
        _montar_nivel_2()
        bloque = await cliente().bloque_externo("GGAL")

    assert bloque.perfil is not None
    assert bloque.perfil.industria == "Banks - Regional"
    assert bloque.perfil.pais == "Argentina"


# --- Caché ----------------------------------------------------------------------------------------


class _Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


async def test_la_segunda_ficha_del_mismo_ticker_no_vuelve_a_pedir_nada() -> None:
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(url__startswith=CHART).mock(
            return_value=httpx.Response(200, json=chart())
        )
        _montar_nivel_2()
        yahoo = cliente(reloj=reloj)
        await yahoo.bloque_externo("GGAL")
        await yahoo.bloque_externo("GGAL")

    assert ruta.call_count == 1


async def test_vencido_el_ttl_de_cotizacion_se_vuelve_a_pedir_el_precio_pero_no_el_perfil() -> None:
    """El precio se mueve con la rueda; el perfil de la empresa no cambia en el día."""
    reloj = _Reloj()
    with respx.mock:
        ruta_chart = respx.get(url__startswith=CHART).mock(
            return_value=httpx.Response(200, json=chart())
        )
        respx.get(URL_COOKIE).mock(return_value=httpx.Response(404))
        respx.get(URL_CRUMB).mock(return_value=httpx.Response(200, text="abc123"))
        ruta_perfil = respx.get(url__startswith=PERFIL).mock(
            return_value=httpx.Response(200, json=perfil())
        )
        yahoo = cliente(reloj=reloj, ttl_cotizacion=300.0, ttl_perfil=86_400.0)
        await yahoo.bloque_externo("GGAL")
        reloj.t = 400.0
        bloque = await yahoo.bloque_externo("GGAL")

    assert ruta_chart.call_count == 2
    assert ruta_perfil.call_count == 1
    assert bloque.perfil is not None


@pytest.mark.parametrize("ticker", ["GGAL", "ggal", " GGAL "])
async def test_el_ticker_se_normaliza_a_un_solo_simbolo(ticker: str) -> None:
    assert cliente().simbolo_de(ticker) == SIMBOLO
