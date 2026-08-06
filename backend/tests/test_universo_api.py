"""Los dos endpoints del universo saneado: el resumen de la corrida y el listado auditable.

Lo que se prueba acá es el contrato HTTP —qué viaja, cómo se pagina y qué pasa sin base—; el
veredicto de las dos capas ya está probado sin levantar nada en `test_universo_sanidad.py`.
"""

from typing import Any

import pytest

from tests.conftest import cliente
from tests.test_universo_servicio import UNIVERSO, FakeConexionLectura

SANIDAD = "/api/v1/universo/sanidad"
DESCARTES = "/api/v1/universo/sanidad/descartes"


@pytest.fixture
def app_con_universo(crear_app):
    def _crear(filas: list[dict[str, Any]] | None = None):
        return crear_app(FakeConexionLectura(UNIVERSO if filas is None else filas))

    return _crear


async def test_el_resumen_declara_los_descartes_y_sus_alertas(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.get(SANIDAD)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["resumen"]["descartados"] == 2
    assert cuerpo["resumen"]["por_capa"]["especie_incoherente"] == 1
    codigos = {a["codigo"] for a in cuerpo["alertas"]}
    assert codigos == {"especie_incoherente", "rendimiento_fuera_de_rango"}


async def test_el_listado_dice_ticker_motivo_y_el_valor_que_lo_disparo(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.get(DESCARTES)

    items = respuesta.json()["items"]
    por_ticker = {i["ticker"]: i for i in items}
    assert set(por_ticker) == {"VSCQD", "TXCER"}
    assert por_ticker["VSCQD"]["motivo"] == "especie_incoherente"
    assert por_ticker["VSCQD"]["ticker_referencia"] == "VSCQO"
    assert por_ticker["TXCER"]["motivo"] == "rendimiento_fuera_de_rango"
    assert por_ticker["TXCER"]["umbral"] == 1.0


async def test_el_listado_se_puede_filtrar_por_capa(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.get(DESCARTES, params={"motivo": "especie_incoherente"})

    assert [i["ticker"] for i in respuesta.json()["items"]] == ["VSCQD"]


async def test_un_motivo_que_no_existe_se_rechaza_con_422(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        respuesta = await http.get(DESCARTES, params={"motivo": "porque-si"})

    assert respuesta.status_code == 422


async def test_el_cursor_avanza_sin_repetir_ni_saltear(app_con_universo) -> None:
    async with cliente(app_con_universo()) as http:
        primera = (await http.get(DESCARTES, params={"limit": 1})).json()
        assert [i["ticker"] for i in primera["items"]] == ["TXCER"]
        assert primera["next_cursor"]

        segunda = (
            await http.get(DESCARTES, params={"limit": 1, "cursor": primera["next_cursor"]})
        ).json()

    assert [i["ticker"] for i in segunda["items"]] == ["VSCQD"]
    assert segunda["next_cursor"] is None


async def test_sin_base_de_datos_responde_503(crear_app) -> None:
    """Un universo que no se puede leer no es un universo sano: no se contesta cero descartes."""
    async with cliente(crear_app(None)) as http:
        respuesta = await http.get(SANIDAD)

    assert respuesta.status_code == 503
