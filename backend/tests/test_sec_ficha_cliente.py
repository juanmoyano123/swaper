"""`ClienteSecFicha` — el paquete de estados contables on-demand para la ficha de un CEDEAR.

Contra la SEC real, no contra `app/externos/sec.py` (ese es el cliente batch del job de
clasificación). Cada test arma su propio `companyfacts` recortado: lo que importa acá no es que se
parezca a una empresa real, sino que ejercite una regla puntual del parser/cliente — la cobertura de
cómo se arman esos fixtures de verdad, contra companyfacts reales, ya se hizo a mano en la
investigación previa a este archivo (ver el plan de la tanda).
"""

from typing import Any

import httpx
import pytest
import respx

from app.externos.sec_ficha import (
    MOTIVO_NO_CEDEAR,
    MOTIVO_SIN_CIK,
    MOTIVO_SIN_EJERCICIO,
    URL_COMPANYFACTS,
    URL_SUBMISSIONS,
    URL_TICKERS,
    ClienteSecFicha,
)
from app.ingesta.http import Reintentos

CIK = 1234567
CIK_AAL = 6201


async def _no_dormir(_: float) -> None:
    return None


def _cliente() -> ClienteSecFicha:
    """Una instancia nueva por test: sin caché compartida entre casos."""
    return ClienteSecFicha(dormir=_no_dormir, politica=Reintentos(intentos=2, espera_base=0))


def _mapa(**tickers: int) -> dict[str, Any]:
    return {
        str(i): {"cik_str": cik, "ticker": ticker, "title": ticker}
        for i, (ticker, cik) in enumerate(tickers.items())
    }


def _submissions(*forms_fechas_acc_doc: tuple[str, str, str, str]) -> dict[str, Any]:
    return {
        "filings": {
            "recent": {
                "form": [f[0] for f in forms_fechas_acc_doc],
                "filingDate": [f[1] for f in forms_fechas_acc_doc],
                "accessionNumber": [f[2] for f in forms_fechas_acc_doc],
                "primaryDocument": [f[3] for f in forms_fechas_acc_doc],
            }
        }
    }


def _instante(valor: float, *, unidad: str = "USD", fin: str = "2025-12-31") -> dict[str, Any]:
    return {"units": {unidad: [{"end": fin, "val": valor}]}}


def _hecho(valor: float, inicio: str, fin: str, *, frame: str | None = None) -> dict[str, Any]:
    hecho: dict[str, Any] = {"start": inicio, "end": fin, "val": valor}
    if frame is not None:
        hecho["frame"] = frame
    return hecho


def _flujo(*hechos: dict[str, Any], unidad: str = "USD") -> dict[str, Any]:
    return {"units": {unidad: list(hechos)}}


def _companyfacts(taxonomia: str, conceptos: dict[str, Any]) -> dict[str, Any]:
    return {"facts": {taxonomia: conceptos}}


async def test_filer_domestico_con_trimestral_y_anual_via_frame() -> None:
    """us-gaap, con `frame` — el caso limpio: ROE y el resto de los ratios se calculan sin
    ambigüedad, y `solo_anual` da `False` porque hay un punto trimestral."""
    companyfacts = _companyfacts(
        "us-gaap",
        {
            "Assets": _instante(100.0),
            "StockholdersEquity": _instante(50.0),
            "AssetsCurrent": _instante(60.0),
            "LiabilitiesCurrent": _instante(30.0),
            "Revenues": _flujo(
                _hecho(120.0, "2025-01-01", "2025-12-31", frame="CY2025"),
                _hecho(96.0, "2024-01-01", "2024-12-31", frame="CY2024"),
            ),
            "NetIncomeLoss": _flujo(
                _hecho(20.0, "2025-01-01", "2025-12-31", frame="CY2025"),
                _hecho(6.0, "2025-10-01", "2025-12-31", frame="CY2025Q4"),
            ),
            "OperatingIncomeLoss": _flujo(_hecho(30.0, "2025-01-01", "2025-12-31", frame="CY2025")),
            "EarningsPerShareDiluted": _flujo(
                _hecho(1.25, "2025-01-01", "2025-12-31", frame="CY2025"), unidad="USD/shares"
            ),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(DOM=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01", "0001-25-000001", "dom-10k.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("DOM", "cedear", None)

    assert bloque.disponible is True
    assert bloque.solo_anual is False
    assert bloque.cik == str(CIK)
    assert bloque.ratios is not None
    assert bloque.ratios.roe.valor == pytest.approx(20.0 / 50.0)
    assert bloque.ratios.margen_operativo.valor == pytest.approx(30.0 / 120.0)
    assert bloque.ratios.crecimiento_ingresos.valor == pytest.approx((120.0 - 96.0) / 96.0)
    assert bloque.ratios.eps.valor == pytest.approx(1.25)
    assert bloque.ratios.eps.unidad == "USD/shares"
    assert bloque.ratios.liquidez_corriente.valor == pytest.approx(60.0 / 30.0)


async def test_fpi_solo_anual_sin_frame_clasifica_por_duracion() -> None:
    """ifrs-full, `fp: FY` únicamente, sin `frame` en ningún hecho: el cliente tiene que clasificar
    por duración (~365 días) para encontrar el período anual limpio, y declarar `solo_anual=True`
    porque no hay ningún trimestral."""
    companyfacts = _companyfacts(
        "ifrs-full",
        {
            "Assets": _instante(500.0),
            "Equity": _instante(200.0),
            "ProfitLoss": _flujo(_hecho(40.0, "2025-01-01", "2025-12-31")),
            "Revenue": _flujo(_hecho(300.0, "2025-01-01", "2025-12-31")),
            "ProfitLossFromOperatingActivities": _flujo(_hecho(60.0, "2025-01-01", "2025-12-31")),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(FPI=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("20-F", "2026-03-01", "0002-25-000001", "fpi-20f.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("FPI", "cedear", None)

    assert bloque.disponible is True
    assert bloque.solo_anual is True
    assert bloque.nota_solo_anual is not None
    assert bloque.ratios.roe.valor == pytest.approx(40.0 / 200.0)
    assert bloque.ratios.margen_operativo.valor == pytest.approx(60.0 / 300.0)


async def test_banco_fpi_sin_revenue_ni_operativo_ni_eps_declara_esos_ratios_ausentes() -> None:
    """Un banco FPI no tiene 'resultado operativo' en su taxonomía — se declara ausente, nunca se
    fuerza un proxy. El resto del bloque se arma igual."""
    companyfacts = _companyfacts(
        "ifrs-full",
        {
            "Assets": _instante(900.0),
            "Equity": _instante(100.0),
            "ProfitLoss": _flujo(_hecho(15.0, "2025-01-01", "2025-12-31")),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(BANCO=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("20-F", "2026-03-01", "0003-25-000001", "banco-20f.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("BANCO", "cedear", None)

    assert bloque.disponible is True
    assert bloque.ratios.roe.valor == pytest.approx(15.0 / 100.0)
    assert bloque.ratios.margen_operativo is None
    assert bloque.ratios.crecimiento_ingresos is None
    assert bloque.ratios.eps is None


async def test_un_concepto_ausente_aislado_no_afecta_al_resto() -> None:
    """Falta sólo la deuda de largo plazo: `deuda_patrimonio` queda ausente, el resto del bloque
    (incluido ROE) se calcula igual."""
    companyfacts = _companyfacts(
        "us-gaap",
        {
            "Assets": _instante(100.0),
            "StockholdersEquity": _instante(50.0),
            "NetIncomeLoss": _flujo(_hecho(20.0, "2025-01-01", "2025-12-31", frame="CY2025")),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(SOLO=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01", "0004-25-000001", "solo-10k.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("SOLO", "cedear", None)

    assert bloque.disponible is True
    assert bloque.ratios.roe.valor == pytest.approx(20.0 / 50.0)
    assert bloque.ratios.deuda_patrimonio is None
    assert bloque.ratios.margen_operativo is None
    assert bloque.ratios.liquidez_corriente is None


async def test_ticker_no_cedear_declara_ausente_sin_pedirle_nada_a_la_sec() -> None:
    """`respx.mock` sin ninguna ruta montada: si el cliente intentara red, el test explotaría solo
    en vez de necesitar un assert de 'no se llamó a nada'."""
    with respx.mock:
        bloque = await _cliente().bloque_sec("GGAL", "accion", None)

    assert bloque.disponible is False
    assert bloque.motivo_ausente == MOTIVO_NO_CEDEAR
    assert bloque.cik is None
    assert bloque.ratios is None


async def test_ticker_sin_cik_declara_ausente() -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(OTRO=CIK)))
        bloque = await _cliente().bloque_sec("NOEXISTE", "cedear", None)

    assert bloque.disponible is False
    assert bloque.motivo_ausente == MOTIVO_SIN_CIK


async def test_timeout_de_red_se_declara_ausente_sin_excepcion() -> None:
    with respx.mock:
        respx.get(URL_TICKERS).mock(side_effect=httpx.ConnectTimeout("timeout"))
        bloque = await _cliente().bloque_sec("AAPL", "cedear", None)

    assert bloque.disponible is False
    assert bloque.motivo_ausente
    assert "mapa de tickers" in bloque.motivo_ausente


async def test_duracion_atipica_se_descarta_y_no_se_fuerza_a_ningun_periodo() -> None:
    """Un año de transición fiscal: la única entrada de `NetIncomeLoss` dura ~200 días, sin
    `frame`. Ni trimestre ni año — se descarta, no queda ningún ejercicio ancla posible, y el
    bloque se declara ausente en vez de mostrar un número con un período inventado."""
    companyfacts = _companyfacts(
        "us-gaap",
        {
            "Assets": _instante(100.0),
            "StockholdersEquity": _instante(50.0),
            "NetIncomeLoss": _flujo(_hecho(20.0, "2025-06-01", "2025-12-18")),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(TRANS=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01", "0005-25-000001", "trans-10k.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("TRANS", "cedear", None)

    assert bloque.disponible is False
    assert bloque.motivo_ausente == MOTIVO_SIN_EJERCICIO


async def test_unidades_mixtas_tipo_ypf_no_cruzan_en_el_ratio() -> None:
    """`Equity` en ARS y `NetIncomeLoss` en USD en el mismo companyfacts (cambio de moneda
    funcional, como YPF real): ROE no se calcula cruzando unidades — regla 3 del dominio."""
    companyfacts = _companyfacts(
        "us-gaap",
        {
            "Assets": _instante(100.0, unidad="USD"),
            "StockholdersEquity": _instante(50.0, unidad="ARS"),
            "NetIncomeLoss": _flujo(
                _hecho(20.0, "2025-01-01", "2025-12-31", frame="CY2025"), unidad="USD"
            ),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(MIX=CIK)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01", "0006-25-000001", "mix-10k.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("MIX", "cedear", None)

    assert bloque.disponible is True
    assert bloque.ratios.roe is None, "ARS contra USD no es un cociente válido"


async def test_una_especie_variante_consulta_a_la_sec_por_el_papel_no_por_la_especie() -> None:
    """`AALD` (especie MEP de AAL) no existe en el mapa de la SEC — sólo `AAL`. La ficha resuelve
    `emision='AAL'` y el cliente tiene que buscar con eso, no con el ticker de la especie."""
    companyfacts = _companyfacts(
        "us-gaap",
        {
            "Assets": _instante(100.0),
            "StockholdersEquity": _instante(50.0),
            "NetIncomeLoss": _flujo(_hecho(20.0, "2025-01-01", "2025-12-31", frame="CY2025")),
        },
    )
    with respx.mock:
        respx.get(URL_TICKERS).mock(return_value=httpx.Response(200, json=_mapa(AAL=CIK_AAL)))
        respx.get(URL_SUBMISSIONS.format(cik=CIK_AAL)).mock(
            return_value=httpx.Response(
                200, json=_submissions(("10-K", "2026-02-01", "0007-25-000001", "aal-10k.htm"))
            )
        )
        respx.get(URL_COMPANYFACTS.format(cik=CIK_AAL)).mock(
            return_value=httpx.Response(200, json=companyfacts)
        )
        bloque = await _cliente().bloque_sec("AALD", "cedear", "AAL")

    assert bloque.disponible is True
    assert bloque.cik == str(CIK_AAL)
