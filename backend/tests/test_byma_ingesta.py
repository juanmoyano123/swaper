"""GWT-1, GWT-3 y GWT-4 de la spec (`claude-docs/planning/plan.md:260-299`), orquestados.

GWT-2 (moneda por campo declarado) se prueba en `test_byma_normalizacion.py`, donde vive la
normalización. Acá se prueba lo que sólo se ve con los seis endpoints juntos: que el conteo por
endpoint quede en el snapshot, que uno caído no corte a los demás, y que la demora declarada sea un
atributo del snapshot.
"""

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.ingesta.alertas import CODIGO_FUENTE_CAIDA
from app.ingesta.byma.cliente import TAMANO_PAGINA
from app.ingesta.byma.ingesta import ingerir_rueda

BASE_URL = "https://byma-test.local/free"


async def _no_dormir(_: float) -> None:
    return None


@pytest.fixture
def settings_de_prueba():
    """La configuración real de test (env_de_prueba, autouse en conftest.py) con la base de BYMA
    apuntando al host que mockea respx, para no depender de qué host trae el .env real."""
    return get_settings().model_copy(update={"byma_base_url": BASE_URL, "byma_demora_minutos": 20})


def _pagina(datos: list[dict], numero: int, page_count: int, total: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "content": {
                "page_number": numero,
                "page_count": page_count,
                "page_size": TAMANO_PAGINA,
                "total_elements_count": total,
            },
            "data": datos,
        },
    )


async def test_la_ingesta_registra_el_conteo_de_filas_de_los_seis_endpoints(
    settings_de_prueba,
) -> None:
    """Dos endpoints como lista plana, dos como objeto paginado multi-página, dos de una página."""
    with respx.mock:
        respx.post(f"{BASE_URL}/leading-equity").mock(
            return_value=_pagina([{"symbol": "ALUA"}], 1, 1, 1)
        )
        respx.post(f"{BASE_URL}/negociable-obligations").mock(
            return_value=httpx.Response(200, json=[{"symbol": f"ON{i}"} for i in range(3)])
        )
        respx.post(f"{BASE_URL}/cedears").mock(
            return_value=httpx.Response(200, json=[{"symbol": f"CE{i}"} for i in range(4)])
        )

        def _public_bonds(request: httpx.Request) -> httpx.Response:
            pagina = json.loads(request.content)["page_number"]
            if pagina == 1:
                return _pagina([{"symbol": "AL30"}], 1, 2, 2)
            return _pagina([{"symbol": "GD30"}], 2, 2, 2)

        respx.post(f"{BASE_URL}/public-bonds").mock(side_effect=_public_bonds)

        def _general_equity(request: httpx.Request) -> httpx.Response:
            pagina = json.loads(request.content)["page_number"]
            if pagina == 1:
                return _pagina([{"symbol": "GGAL"}], 1, 2, 2)
            return _pagina([{"symbol": "YPFD"}], 2, 2, 2)

        respx.post(f"{BASE_URL}/general-equity").mock(side_effect=_general_equity)
        respx.post(f"{BASE_URL}/index-price").mock(
            return_value=_pagina([{"symbol": "IDD"}, {"symbol": "IDDG"}], 1, 1, 2)
        )

        resultado = await ingerir_rueda(settings=settings_de_prueba, dormir=_no_dormir)

        assert resultado.snapshot.filas_por_tramo == {
            "negociable-obligations": 3,
            "public-bonds": 2,
            "cedears": 4,
            "general-equity": 2,
            "leading-equity": 1,
            "index-price": 2,
        }
        assert resultado.snapshot.alertas == []
        # El endpoint de origen es lo que declara la clase de activo, así que F-007 lo necesita
        # sin reconstruirlo por orden de recorrido.
        assert {ep: len(f) for ep, f in resultado.especies_por_endpoint.items()} == {
            "negociable-obligations": 3,
            "public-bonds": 2,
            "cedears": 4,
            "general-equity": 2,
            "leading-equity": 1,
        }
        assert sum(len(f) for f in resultado.especies_por_endpoint.values()) == len(
            resultado.especies
        ), "la partición por endpoint y la lista aplanada tienen que contener lo mismo"
        for llamada in respx.calls:
            assert llamada.request.method == "POST"
            assert "authorization" not in llamada.request.headers
            assert llamada.request.headers["content-type"].startswith("application/json")


async def test_un_endpoint_caido_no_impide_ingerir_los_demas(settings_de_prueba) -> None:
    with respx.mock:
        respx.post(f"{BASE_URL}/public-bonds").mock(return_value=httpx.Response(401))
        respx.post(f"{BASE_URL}/negociable-obligations").mock(
            return_value=httpx.Response(200, json=[{"symbol": "ON1"}])
        )
        respx.post(f"{BASE_URL}/cedears").mock(
            return_value=httpx.Response(200, json=[{"symbol": "CE1"}])
        )
        respx.post(f"{BASE_URL}/general-equity").mock(
            return_value=_pagina([{"symbol": "GGAL"}], 1, 1, 1)
        )
        respx.post(f"{BASE_URL}/leading-equity").mock(
            return_value=_pagina([{"symbol": "ALUA"}], 1, 1, 1)
        )
        respx.post(f"{BASE_URL}/index-price").mock(
            return_value=_pagina([{"symbol": "IDD"}], 1, 1, 1)
        )

        resultado = await ingerir_rueda(settings=settings_de_prueba, dormir=_no_dormir)

    assert resultado.snapshot.filas_por_tramo["public-bonds"] == 0
    assert len(resultado.especies) == 4  # ONs + cedears + panel general + panel líder
    assert len(resultado.indices) == 1
    assert "public-bonds" not in resultado.especies_por_endpoint

    (alerta,) = resultado.snapshot.alertas
    assert alerta.codigo == CODIGO_FUENTE_CAIDA
    assert alerta.detalle["endpoint"] == "public-bonds"
    assert alerta.detalle["status"] == 401
    assert alerta.accion_requerida is None, "BYMA no tiene credencial que renovar"
    assert resultado.snapshot.completo is False


async def test_un_500_persistente_agota_los_reintentos_y_no_corta_la_corrida(
    settings_de_prueba,
) -> None:
    with respx.mock:
        ruta_caida = respx.post(f"{BASE_URL}/public-bonds").mock(return_value=httpx.Response(500))
        respx.post(f"{BASE_URL}/negociable-obligations").mock(
            return_value=httpx.Response(200, json=[{"symbol": "ON1"}])
        )
        respx.post(f"{BASE_URL}/cedears").mock(
            return_value=httpx.Response(200, json=[{"symbol": "CE1"}])
        )
        respx.post(f"{BASE_URL}/general-equity").mock(
            return_value=httpx.Response(200, json=[{"symbol": "GE1"}])
        )
        respx.post(f"{BASE_URL}/leading-equity").mock(
            return_value=httpx.Response(200, json=[{"symbol": "ALUA"}])
        )
        respx.post(f"{BASE_URL}/index-price").mock(
            return_value=_pagina([{"symbol": "IDD"}], 1, 1, 1)
        )

        resultado = await ingerir_rueda(settings=settings_de_prueba, dormir=_no_dormir)

    assert ruta_caida.call_count == 5
    assert resultado.snapshot.filas_por_tramo["public-bonds"] == 0
    alertas_public_bonds = [
        a for a in resultado.snapshot.alertas if a.detalle.get("endpoint") == "public-bonds"
    ]
    assert len(alertas_public_bonds) == 1
    assert alertas_public_bonds[0].codigo == CODIGO_FUENTE_CAIDA
    # Los otros se ingirieron igual.
    assert len(resultado.especies) == 4
    assert len(resultado.indices) == 1


async def test_el_snapshot_declara_la_demora_de_veinte_minutos(settings_de_prueba) -> None:
    with respx.mock:
        for endpoint in ("negociable-obligations", "cedears"):
            respx.post(f"{BASE_URL}/{endpoint}").mock(
                return_value=httpx.Response(200, json=[{"symbol": "X"}])
            )
        for endpoint in ("public-bonds", "general-equity", "leading-equity", "index-price"):
            respx.post(f"{BASE_URL}/{endpoint}").mock(
                return_value=_pagina([{"symbol": "X"}], 1, 1, 1)
            )

        resultado = await ingerir_rueda(settings=settings_de_prueba, dormir=_no_dormir)

    snapshot = resultado.snapshot.como_dict()
    assert snapshot["demora_declarada_minutos"] == 20
    diferencia = resultado.snapshot.capturado_en - resultado.snapshot.dato_valido_hasta
    assert diferencia.total_seconds() == 20 * 60
