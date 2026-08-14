"""`ClienteData912Historico` — el histórico de cierres para el panel de la ficha.

Mismo criterio que `test_yahoo_cliente.py`: `respx` mockea la red, nunca lanza, y todo fallo se
verifica devuelto como bloque declarado, no como excepción.
"""

from datetime import UTC, datetime
from typing import Any

import httpx
import respx

from app.externos.data912 import (
    BASE_URL,
    URL_HISTORICO,
    ClienteData912Historico,
)
from app.ingesta.http import Reintentos

RUTA_STOCKS_GGAL = URL_HISTORICO.format(base=BASE_URL, tramo="stocks", ticker="GGAL")
RUTA_CEDEARS_AAPL = URL_HISTORICO.format(base=BASE_URL, tramo="cedears", ticker="AAPL")


async def _no_dormir(_: float) -> None:
    return None


def cliente(**kwargs: Any) -> ClienteData912Historico:
    """Cliente que no espera de verdad y con fecha de pared fija, para que el recorte a un año sea
    determinístico."""
    kwargs.setdefault("dormir", _no_dormir)
    kwargs.setdefault("politica", Reintentos(intentos=2, espera_base=0))
    kwargs.setdefault("ahora", lambda: datetime(2026, 8, 13, 12, 0, tzinfo=UTC))
    return ClienteData912Historico(**kwargs)


def _barra(fecha: str, cierre: float, **extra: Any) -> dict[str, Any]:
    return {"date": fecha, "o": cierre, "h": cierre, "l": cierre, "c": cierre, "v": 100.0, **extra}


class _Reloj:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


# --- Camino feliz -----------------------------------------------------------------------------


async def test_camino_feliz_ordena_y_recorta_al_ultimo_anio() -> None:
    """Barras desordenadas y una de hace tres años: sólo el último año, ascendente."""
    cuerpo = [
        _barra("2026-08-10", 5100.0),
        _barra("2023-01-01", 1000.0),  # fuera del último año, no entra
        _barra("2026-08-08", 5000.0),
        _barra("2026-08-12", 5200.0),
    ]
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert bloque.disponible is True
    assert bloque.motivo is None
    assert bloque.fuente == "data912"
    assert [(p.fecha, p.cierre) for p in bloque.puntos] == [
        ("2026-08-08", 5000.0),
        ("2026-08-10", 5100.0),
        ("2026-08-12", 5200.0),
    ]


async def test_dr_y_sa_no_documentados_se_ignoran_sin_romper() -> None:
    """`dr` y `sa` viajan en cada barra real de data912 y no están documentados (regla 11): el
    parser los tiene que ignorar, no fallar por su presencia."""
    cuerpo = [_barra("2026-08-12", 5000.0, dr=0.0068, sa=0.477)]
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert bloque.disponible is True
    (punto,) = bloque.puntos
    assert punto.fecha == "2026-08-12"
    assert punto.cierre == 5000.0


# --- Tramo por clase ----------------------------------------------------------------------------


async def test_un_cedear_consulta_historical_cedears() -> None:
    with respx.mock:
        ruta = respx.get(RUTA_CEDEARS_AAPL).mock(
            return_value=httpx.Response(200, json=[_barra("2026-08-12", 250.0)])
        )
        bloque = await cliente().bloque_historico("AAPL", "cedear")

    assert ruta.called
    assert bloque.disponible is True


async def test_una_accion_consulta_historical_stocks() -> None:
    with respx.mock:
        ruta = respx.get(RUTA_STOCKS_GGAL).mock(
            return_value=httpx.Response(200, json=[_barra("2026-08-12", 5000.0)])
        )
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert ruta.called
    assert bloque.disponible is True


async def test_una_clase_que_no_es_accion_ni_cedear_no_pide_nada() -> None:
    with respx.mock:
        bloque = await cliente().bloque_historico("AL30", "bono_soberano")

    assert bloque.disponible is False
    assert bloque.puntos == ()
    assert bloque.motivo is not None and "no es una acción ni un CEDEAR" in bloque.motivo


# --- Las dos formas en que la fuente dice "no tengo esto" ---------------------------------------


async def test_ticker_inexistente_responde_error_con_200_y_se_declara_sin_serie() -> None:
    """Caso real medido el 13/08/2026: HTTP 200 con `{"Error": ...}`, no una lista."""
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(
            return_value=httpx.Response(200, json={"Error": "Nahh no tengo ese ticker loko"})
        )
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert bloque.disponible is False
    assert bloque.puntos == ()
    assert bloque.motivo is not None and "GGAL" in bloque.motivo


async def test_lista_vacia_se_declara_sin_serie_sin_excepcion() -> None:
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=[]))
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert bloque.disponible is False
    assert bloque.puntos == ()


async def test_una_barra_sin_cierre_numerico_se_omite_sin_inventar() -> None:
    cuerpo = [
        _barra("2026-08-11", 5000.0),
        {"date": "2026-08-12", "o": 1.0, "h": 1.0, "l": 1.0, "c": None, "v": 0.0},
        {"date": "no-es-una-fecha", "c": 5300.0},
    ]
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert [(p.fecha, p.cierre) for p in bloque.puntos] == [("2026-08-11", 5000.0)]


# --- Degradación ----------------------------------------------------------------------------------


async def test_data912_caido_no_lanza_y_declara_el_bloque_no_disponible() -> None:
    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(side_effect=httpx.ConnectError("sin red"))
        bloque = await cliente().bloque_historico("GGAL", "accion")

    assert bloque.disponible is False
    assert bloque.puntos == ()
    assert bloque.motivo is not None


async def test_el_fallo_se_recuerda_un_minuto_y_no_se_insiste() -> None:
    """`politica` con un solo intento: lo que se mide es que la segunda llamada no vuelva a la
    red, no el reintento interno de una sola llamada (eso ya lo prueba `pedir`/`con_reintentos`)."""
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(RUTA_STOCKS_GGAL).mock(side_effect=httpx.ConnectError("sin red"))
        historico = cliente(reloj=reloj, politica=Reintentos(intentos=1, espera_base=0))
        primero = await historico.bloque_historico("GGAL", "accion")
        segundo = await historico.bloque_historico("GGAL", "accion")

    assert ruta.call_count == 1
    assert primero.motivo == segundo.motivo


async def test_vencido_el_minuto_se_vuelve_a_intentar() -> None:
    """La anotación no puede convertirse en "no disponible" para siempre."""
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(RUTA_STOCKS_GGAL).mock(
            side_effect=[
                httpx.ConnectError("sin red"),
                httpx.Response(200, json=[_barra("2026-08-12", 5000.0)]),
            ]
        )
        historico = cliente(
            reloj=reloj, ttl_fallo=60.0, politica=Reintentos(intentos=1, espera_base=0)
        )
        await historico.bloque_historico("GGAL", "accion")
        reloj.t = 90.0
        bloque = await historico.bloque_historico("GGAL", "accion")

    assert ruta.call_count == 2
    assert bloque.disponible is True


# --- Caché ----------------------------------------------------------------------------------------


async def test_la_serie_se_cachea_y_el_segundo_pedido_no_toca_la_red() -> None:
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(RUTA_STOCKS_GGAL).mock(
            return_value=httpx.Response(200, json=[_barra("2026-08-12", 5000.0)])
        )
        historico = cliente(reloj=reloj)
        primero = await historico.bloque_historico("GGAL", "accion")
        segundo = await historico.bloque_historico("GGAL", "accion")

    assert ruta.call_count == 1
    assert primero.puntos == segundo.puntos


async def test_vencida_la_serie_se_vuelve_a_pedir() -> None:
    reloj = _Reloj()
    with respx.mock:
        ruta = respx.get(RUTA_STOCKS_GGAL).mock(
            return_value=httpx.Response(200, json=[_barra("2026-08-12", 5000.0)])
        )
        historico = cliente(reloj=reloj, ttl_serie=3600.0)
        await historico.bloque_historico("GGAL", "accion")
        reloj.t = 4000.0
        await historico.bloque_historico("GGAL", "accion")

    assert ruta.call_count == 2


# --- Fecha de recorte, inyectada --------------------------------------------------------------


async def test_el_recorte_usa_la_fecha_inyectada_no_la_de_pared() -> None:
    """La misma barra, la misma fuente: con `ahora` en 2026 queda dentro del último año: con
    `ahora` un año después, la ventana se corrió y la misma barra quedó afuera."""
    cuerpo = [_barra("2026-06-01", 4000.0)]

    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))
        con_hoy = await cliente(
            ahora=lambda: datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
        ).bloque_historico("GGAL", "accion")

    with respx.mock:
        respx.get(RUTA_STOCKS_GGAL).mock(return_value=httpx.Response(200, json=cuerpo))
        un_anio_despues = await cliente(
            ahora=lambda: datetime(2027, 8, 13, 12, 0, tzinfo=UTC)
        ).bloque_historico("GGAL", "accion")

    assert [p.fecha for p in con_hoy.puntos] == ["2026-06-01"]
    assert un_anio_despues.puntos == ()
