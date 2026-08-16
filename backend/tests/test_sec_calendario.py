"""`ClienteSecCalendario` y `POST /renta-variable/balances` — F-027.

Los fixtures de `submissions` son sintéticos: lo que importa es ejercitar una regla puntual del
cliente (qué formulario cuenta, qué mes le corresponde, cuándo se declara `solo_anual`), no
parecerse a una empresa real — la SEC real ya se sondeó a mano en la investigación previa al plan.
"""

from typing import Any

import httpx
import pytest
import respx

from app.api.v1 import renta_variable as modulo_endpoint
from app.externos.sec_calendario import (
    MOTIVO_NO_CEDEAR,
    MOTIVO_SIN_CIK,
    MOTIVO_SIN_PRESENTACIONES,
    URL_SUBMISSIONS,
    URL_TICKERS,
    ClienteSecCalendario,
)
from app.ingesta.http import Reintentos
from tests.conftest import cliente

CIK = 1234567
CIK_AAL = 6201


async def _no_dormir(_: float) -> None:
    return None


def _cliente() -> ClienteSecCalendario:
    """Una instancia nueva por test: sin caché compartida entre casos."""
    return ClienteSecCalendario(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))


def _mapa(**tickers: int) -> dict[str, Any]:
    return {
        str(i): {"cik_str": cik, "ticker": ticker, "title": ticker}
        for i, (ticker, cik) in enumerate(tickers.items())
    }


def _submissions(*forms_fechas: tuple[str, str]) -> dict[str, Any]:
    return {
        "filings": {
            "recent": {
                "form": [f[0] for f in forms_fechas],
                "filingDate": [f[1] for f in forms_fechas],
            }
        }
    }


# --- El cliente -----------------------------------------------------------------------------


async def test_filer_domestico_deriva_patron_trimestral_con_frecuencia_por_mes() -> None:
    """10-K + 10-Q repetidos: cada mes con presentaciones lleva su conteo, y `solo_anual` da
    `False` porque hay trimestrales."""
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(DOM=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200,
                json=_submissions(
                    ("10-Q", "2026-07-31"),
                    ("10-Q", "2026-05-01"),
                    ("10-Q", "2026-01-30"),
                    ("10-K", "2025-10-31"),
                    ("10-Q", "2025-08-01"),
                    ("10-Q", "2025-05-02"),
                    ("10-Q", "2025-01-31"),
                    ("10-K", "2024-11-01"),
                ),
            )
        )
        calendario = await _cliente().calendario_de("DOM", "cedear", None)

    assert calendario.disponible is True
    assert calendario.solo_anual is False
    assert calendario.nota_solo_anual is None
    assert calendario.cik == str(CIK)
    por_mes = {m.mes: m.presentaciones for m in calendario.meses}
    assert por_mes == {1: 2, 5: 2, 7: 1, 8: 1, 10: 1, 11: 1}
    formularios_de_octubre = next(m.formularios for m in calendario.meses if m.mes == 10)
    assert formularios_de_octubre == ("10-K",)
    assert calendario.ventana is not None
    assert calendario.ventana.desde == "2024-11-01"
    assert calendario.ventana.hasta == "2026-07-31"


async def test_foreign_private_issuer_solo_20f_declara_solo_anual() -> None:
    """Sólo 20-F en la ventana: no hay ningún 10-Q, así que el patrón intermedio no es derivable
    y se declara — mismo concepto que ya usa la ficha F-053 (`solo_anual`)."""
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(FPI=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200,
                json=_submissions(
                    ("20-F", "2026-03-27"),
                    ("20-F", "2025-03-28"),
                    ("20-F", "2024-04-19"),
                    ("6-K", "2026-08-13"),
                    ("6-K", "2026-08-06"),
                ),
            )
        )
        calendario = await _cliente().calendario_de("FPI", "cedear", None)

    assert calendario.disponible is True
    assert calendario.solo_anual is True
    assert calendario.nota_solo_anual is not None
    por_mes = {m.mes: m.presentaciones for m in calendario.meses}
    # Los 6-K no clasificados no aparecen: sólo marzo y abril, de los 20-F.
    assert por_mes == {3: 2, 4: 1}


async def test_enmiendas_no_cuentan_como_presentacion() -> None:
    """`10-K/A` re-presenta un balance viejo: su fecha no es patrón y se excluye."""
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(ENM=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200,
                json=_submissions(
                    ("10-K", "2026-02-01"),
                    ("10-K/A", "2026-04-15"),
                ),
            )
        )
        calendario = await _cliente().calendario_de("ENM", "cedear", None)

    assert calendario.disponible is True
    assert [m.mes for m in calendario.meses] == [2]


async def test_40f_cuenta_como_anual_del_regimen_mjds_canadiense() -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(CAN=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=_submissions(("40-F", "2026-03-15")))
        )
        calendario = await _cliente().calendario_de("CAN", "cedear", None)

    assert calendario.disponible is True
    assert calendario.solo_anual is True
    assert [m.mes for m in calendario.meses] == [3]


async def test_ticker_no_cedear_declara_ausente_sin_pedirle_nada_a_la_sec() -> None:
    """`respx.mock` sin ninguna ruta montada: si el cliente intentara red, el test explotaría solo."""
    with respx.mock:
        calendario = await _cliente().calendario_de("GGAL", "accion", None)

    assert calendario.disponible is False
    assert calendario.motivo_ausente == MOTIVO_NO_CEDEAR
    assert calendario.cik is None
    assert calendario.meses == ()


async def test_ticker_sin_cik_declara_ausente() -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(OTRO=CIK)))
        calendario = await _cliente().calendario_de("NOEXISTE", "cedear", None)

    assert calendario.disponible is False
    assert calendario.motivo_ausente == MOTIVO_SIN_CIK


async def test_sin_presentaciones_de_balance_declara_ausente_y_no_inventa_patron() -> None:
    """El papel existe en la SEC pero sólo tiene formularios que no son balance (p. ej. `3`/`4` de
    tenencias de insiders): sin `10-K/10-Q/20-F/40-F`, no hay patrón que mostrar."""
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(SOLOINS=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=_submissions(("4", "2026-05-01")))
        )
        calendario = await _cliente().calendario_de("SOLOINS", "cedear", None)

    assert calendario.disponible is False
    assert calendario.motivo_ausente == MOTIVO_SIN_PRESENTACIONES
    assert calendario.cik == str(CIK)


async def test_timeout_de_red_se_declara_ausente_sin_excepcion() -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(side_effect=httpx.ConnectTimeout("timeout"))
        calendario = await _cliente().calendario_de("AAPL", "cedear", None)

    assert calendario.disponible is False
    assert calendario.motivo_ausente
    assert "mapa de tickers" in calendario.motivo_ausente


async def test_fallo_se_cachea_y_no_insiste_en_el_segundo_pedido() -> None:
    """Un 429 en el pedido de submissions se cachea 60 s: el segundo pedido del mismo papel no
    vuelve a golpear la fuente — se verifica con `respx.mock` sin la segunda ruta montada."""
    cliente_sec = _cliente()
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(RATE=CIK)))
        ruta_submissions = respx.get(URL_SUBMISSIONS.format(cik=CIK), name="submissions")
        ruta_submissions.mock(return_value=httpx.Response(429))
        primero = await cliente_sec.calendario_de("RATE", "cedear", None)
        assert primero.disponible is False

        respx.routes["submissions"].side_effect = AssertionError("no debería volver a pedirse")
        segundo = await cliente_sec.calendario_de("RATE", "cedear", None)

    assert segundo.disponible is False
    assert segundo.motivo_ausente == primero.motivo_ausente


async def test_se_busca_por_papel_no_por_especie() -> None:
    """`AALD` (especie MEP de AAL) no existe en el mapa de la SEC — sólo `AAL`."""
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(AAL=CIK_AAL)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK_AAL)).mock(
            return_value=httpx.Response(200, json=_submissions(("10-K", "2026-02-01")))
        )
        calendario = await _cliente().calendario_de("AALD", "cedear", "AAL")

    assert calendario.disponible is True
    assert calendario.papel == "AAL"
    assert calendario.cik == str(CIK_AAL)


# --- El endpoint ------------------------------------------------------------------------------

RUTA = "/api/v1/renta-variable/balances"


@pytest.fixture
def app_con_balances(crear_app, monkeypatch):
    def _crear(**kwargs: Any):
        sec = ClienteSecCalendario(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))
        monkeypatch.setattr(modulo_endpoint, "cliente_sec_calendario", lambda: sec)
        return crear_app(**kwargs)

    return _crear


async def test_endpoint_devuelve_un_calendario_por_papel_pedido(app_con_balances) -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(
            return_value=httpx.Response(200, json=_mapa(AAPL=320193, VALE=917851))
        )
        respx.get(URL_SUBMISSIONS.format(cik=320193)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01"), ("10-Q", "2025-11-01"))
            )
        )
        respx.get(URL_SUBMISSIONS.format(cik=917851)).mock(
            return_value=httpx.Response(200, json=_submissions(("20-F", "2026-03-27")))
        )
        async with cliente(app_con_balances(conn=None)) as http:
            respuesta = await http.post(RUTA, json={"papeles": ["AAPL", "VALE", "XXXX"]})

    assert respuesta.status_code == 200
    calendarios = respuesta.json()["calendarios"]
    assert len(calendarios) == 3
    por_papel = {c["papel"]: c for c in calendarios}
    assert por_papel["AAPL"]["disponible"] is True
    assert por_papel["AAPL"]["solo_anual"] is False
    assert por_papel["VALE"]["disponible"] is True
    assert por_papel["VALE"]["solo_anual"] is True
    assert por_papel["XXXX"]["disponible"] is False
    assert por_papel["XXXX"]["motivo_ausente"] == MOTIVO_SIN_CIK


async def test_endpoint_dedupe_papeles_repetidos(app_con_balances) -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(AAPL=320193)))
        respx.get(URL_SUBMISSIONS.format(cik=320193)).mock(
            return_value=httpx.Response(200, json=_submissions(("10-K", "2026-02-01")))
        )
        async with cliente(app_con_balances(conn=None)) as http:
            respuesta = await http.post(RUTA, json={"papeles": ["AAPL", "aapl", "AAPL"]})

    assert len(respuesta.json()["calendarios"]) == 1


async def test_endpoint_rechaza_lista_vacia_o_sobre_el_tope(app_con_balances) -> None:
    async with cliente(app_con_balances(conn=None)) as http:
        vacia = await http.post(RUTA, json={"papeles": []})
        de_mas = await http.post(RUTA, json={"papeles": [f"T{i}" for i in range(41)]})

    assert vacia.status_code == 422
    assert de_mas.status_code == 422
