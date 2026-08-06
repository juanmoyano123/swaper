"""Mecánica de `descargar_endpoint`: paginación, detección de forma, verificación de totales.

Cubre los hallazgos empíricos del plan de F-004: los conteos de la ficha original mezclan el
tamaño de página con el total real (`public-bonds` no tiene 189 filas, tiene 1106 en 6 páginas), y
un cliente que no verificara el total pedido contra `content.total_elements_count` perdería el
faltante en silencio.
"""

import json
from collections.abc import Callable, Iterable

import httpx
import respx

from app.ingesta.alertas import CODIGO_FORMATO_INESPERADO
from app.ingesta.byma.cliente import (
    CODIGO_PAGINACION_INCOMPLETA,
    TAMANO_PAGINA,
    descargar_endpoint,
)
from app.ingesta.http import crear_cliente

BASE_URL = "https://byma-test.local/free"


async def _no_dormir(_: float) -> None:
    return None


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


def _armar_respondedor(
    paginas: dict[int, httpx.Response],
) -> Callable[[httpx.Request], httpx.Response]:
    def _responder(request: httpx.Request) -> httpx.Response:
        cuerpo = json.loads(request.content)
        return paginas[cuerpo["page_number"]]

    return _responder


def _numeros_de_pagina_pedidos(llamadas: Iterable) -> list[int]:
    return [json.loads(llamada.request.content)["page_number"] for llamada in llamadas]


async def test_una_respuesta_paginada_se_pide_hasta_agotar_las_paginas() -> None:
    filas_1 = [{"symbol": f"ON{i}"} for i in range(500)]
    filas_2 = [{"symbol": f"ON{i}"} for i in range(500, 1000)]
    filas_3 = [{"symbol": f"ON{i}"} for i in range(1000, 1106)]
    paginas = {
        1: _pagina(filas_1, 1, 3, 1106),
        2: _pagina(filas_2, 2, 3, 1106),
        3: _pagina(filas_3, 3, 3, 1106),
    }

    with respx.mock:
        ruta = respx.post(f"{BASE_URL}/public-bonds").mock(side_effect=_armar_respondedor(paginas))

        async with crear_cliente() as cliente:
            resultado = await descargar_endpoint(
                cliente, BASE_URL, "public-bonds", dormir=_no_dormir
            )

        assert len(resultado.filas) == 1106
        assert resultado.alertas == []
        assert ruta.call_count == 3
        assert _numeros_de_pagina_pedidos(ruta.calls) == [1, 2, 3]
        tamanos_pedidos = {
            json.loads(llamada.request.content)["page_size"] for llamada in ruta.calls
        }
        assert tamanos_pedidos == {TAMANO_PAGINA}


async def test_si_el_total_ingerido_no_coincide_con_el_declarado_se_alerta() -> None:
    """La página 3 trae menos filas que las declaradas: se alerta, pero se entregan las 1050."""
    filas_1 = [{"symbol": f"ON{i}"} for i in range(500)]
    filas_2 = [{"symbol": f"ON{i}"} for i in range(500, 1000)]
    filas_3 = [{"symbol": f"ON{i}"} for i in range(1000, 1050)]
    paginas = {
        1: _pagina(filas_1, 1, 3, 1106),
        2: _pagina(filas_2, 2, 3, 1106),
        3: _pagina(filas_3, 3, 3, 1106),
    }

    with respx.mock:
        respx.post(f"{BASE_URL}/public-bonds").mock(side_effect=_armar_respondedor(paginas))

        async with crear_cliente() as cliente:
            resultado = await descargar_endpoint(
                cliente, BASE_URL, "public-bonds", dormir=_no_dormir
            )

    assert len(resultado.filas) == 1050
    (alerta,) = resultado.alertas
    assert alerta.codigo == CODIGO_PAGINACION_INCOMPLETA
    assert alerta.detalle == {
        "endpoint": "public-bonds",
        "esperadas": 1106,
        "obtenidas": 1050,
        "paginas": 3,
    }


async def test_una_lista_plana_se_ingiere_entera_sin_pedir_mas_paginas() -> None:
    filas = [{"symbol": "ONX"}, {"symbol": "ONY"}]

    with respx.mock:
        ruta = respx.post(f"{BASE_URL}/negociable-obligations").mock(
            return_value=httpx.Response(200, json=filas)
        )

        async with crear_cliente() as cliente:
            resultado = await descargar_endpoint(
                cliente, BASE_URL, "negociable-obligations", dormir=_no_dormir
            )

        assert resultado.filas == filas
        assert resultado.alertas == []
        assert ruta.call_count == 1


async def test_un_objeto_sin_data_es_formato_inesperado() -> None:
    with respx.mock:
        respx.post(f"{BASE_URL}/public-bonds").mock(
            return_value=httpx.Response(200, json={"content": {"page_count": 1}})
        )

        async with crear_cliente() as cliente:
            resultado = await descargar_endpoint(
                cliente, BASE_URL, "public-bonds", dormir=_no_dormir
            )

    assert resultado.filas == []
    (alerta,) = resultado.alertas
    assert alerta.codigo == CODIGO_FORMATO_INESPERADO
    assert alerta.detalle["endpoint"] == "public-bonds"


async def test_una_respuesta_vacia_se_reintenta_antes_de_declarar_el_fallo() -> None:
    """La consulta que da cero filas trae datos segundos después: la política de la base común."""
    respuestas = [
        httpx.Response(200, json=[]),
        httpx.Response(200, json=[]),
        httpx.Response(200, json=[{"symbol": "ONX"}]),
    ]

    with respx.mock:
        ruta = respx.post(f"{BASE_URL}/negociable-obligations").mock(side_effect=respuestas)

        async with crear_cliente() as cliente:
            resultado = await descargar_endpoint(
                cliente, BASE_URL, "negociable-obligations", dormir=_no_dormir
            )

        assert resultado.filas == [{"symbol": "ONX"}]
        assert resultado.alertas == []
        assert ruta.call_count == 3
