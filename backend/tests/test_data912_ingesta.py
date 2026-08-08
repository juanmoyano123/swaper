"""Los cinco tramos de data912 orquestados: conteo por tramo, un tramo caído no corta a los demás,
sin demora declarada.
"""

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.ingesta.alertas import CODIGO_FUENTE_CAIDA
from app.ingesta.data912.ingesta import ingerir_live

BASE_URL = "https://data912-test.local"


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def settings_de_prueba():
    return get_settings().model_copy(update={"data912_base_url": BASE_URL})


async def test_la_ingesta_registra_el_conteo_de_filas_de_los_cinco_tramos(
    settings_de_prueba,
) -> None:
    with respx.mock:
        respx.get(f"{BASE_URL}/live/arg_bonds").mock(
            return_value=httpx.Response(200, json=[{"symbol": "AL30D", "c": 56.5}])
        )
        respx.get(f"{BASE_URL}/live/arg_corp").mock(
            return_value=httpx.Response(
                200, json=[{"symbol": f"ON{i}", "c": 100.0} for i in range(3)]
            )
        )
        respx.get(f"{BASE_URL}/live/arg_notes").mock(
            return_value=httpx.Response(200, json=[{"symbol": "S31O6", "c": 100.0}])
        )
        respx.get(f"{BASE_URL}/live/arg_cedears").mock(
            return_value=httpx.Response(200, json=[{"symbol": "AAPL", "c": 200.0}])
        )
        respx.get(f"{BASE_URL}/live/arg_stocks").mock(
            return_value=httpx.Response(200, json=[{"symbol": "GGAL", "c": 5000.0}])
        )

        resultado = await ingerir_live(settings=settings_de_prueba, dormir=_no_dormir)

    assert resultado.snapshot.fuente == "data912"
    assert resultado.snapshot.filas_por_tramo == {
        "arg_bonds": 1,
        "arg_corp": 3,
        "arg_notes": 1,
        "arg_cedears": 1,
        "arg_stocks": 1,
    }
    assert resultado.snapshot.alertas == []
    assert {tramo: len(filas) for tramo, filas in resultado.filas_por_tramo.items()} == {
        "arg_bonds": 1,
        "arg_corp": 3,
        "arg_notes": 1,
        "arg_cedears": 1,
        "arg_stocks": 1,
    }


async def test_un_tramo_caido_no_impide_ingerir_los_demas(settings_de_prueba) -> None:
    with respx.mock:
        respx.get(f"{BASE_URL}/live/arg_bonds").mock(return_value=httpx.Response(401))
        for tramo in ("arg_corp", "arg_notes", "arg_cedears", "arg_stocks"):
            respx.get(f"{BASE_URL}/live/{tramo}").mock(
                return_value=httpx.Response(200, json=[{"symbol": "X", "c": 1.0}])
            )

        resultado = await ingerir_live(settings=settings_de_prueba, dormir=_no_dormir)

    assert resultado.snapshot.filas_por_tramo["arg_bonds"] == 0
    assert "arg_bonds" not in resultado.filas_por_tramo
    assert len(resultado.filas_por_tramo) == 4

    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_FUENTE_CAIDA
    assert alerta.detalle["tramo"] == "arg_bonds"
    assert alerta.detalle["status"] == 401
    assert resultado.snapshot.completo is False


async def test_un_tramo_vacio_se_reintenta_como_respuesta_vacia(settings_de_prueba) -> None:
    """A diferencia de BYMA (que pagina), un tramo `live/` nunca es una lista vacía legítima: se
    trata como inestabilidad de la fuente, no como "hoy no hay nada"."""
    respuestas = [httpx.Response(200, json=[])] * 5

    with respx.mock:
        ruta_vacia = respx.get(f"{BASE_URL}/live/arg_notes").mock(side_effect=respuestas)
        for tramo in ("arg_bonds", "arg_corp", "arg_cedears", "arg_stocks"):
            respx.get(f"{BASE_URL}/live/{tramo}").mock(
                return_value=httpx.Response(200, json=[{"symbol": "X", "c": 1.0}])
            )

        resultado = await ingerir_live(settings=settings_de_prueba, dormir=_no_dormir)

    assert ruta_vacia.call_count == 5
    assert resultado.snapshot.filas_por_tramo["arg_notes"] == 0
    (alerta,) = [a for a in resultado.snapshot.alertas if a.detalle.get("tramo") == "arg_notes"]
    from app.ingesta.alertas import CODIGO_RESPUESTA_VACIA

    assert alerta.codigo == CODIGO_RESPUESTA_VACIA


async def test_sin_demora_declarada(settings_de_prueba) -> None:
    """data912 no publica cuánto atrasa respecto del mercado, y no se le inventa una (regla 11)."""
    with respx.mock:
        for tramo in ("arg_bonds", "arg_corp", "arg_notes", "arg_cedears", "arg_stocks"):
            respx.get(f"{BASE_URL}/live/{tramo}").mock(
                return_value=httpx.Response(200, json=[{"symbol": "X", "c": 1.0}])
            )
        resultado = await ingerir_live(settings=settings_de_prueba, dormir=_no_dormir)

    assert resultado.snapshot.demora_declarada_minutos == 0
    assert resultado.snapshot.dato_valido_hasta == resultado.snapshot.capturado_en
