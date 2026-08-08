"""Mecánica de `descargar_tramo`: sin paginación, y el caso propio de data912 — un objeto en vez
de una lista, verificado en vivo contra `historical/bonds/{ticker}` con un ticker inexistente
(`{"Error": "Nahh no tengo ese ticker loko"}`, HTTP 200). Los tramos `live/` no lo hicieron en las
pruebas manuales, pero nada garantiza que nunca lo hagan, así que se cubre igual que BYMA cubre su
objeto no reconocible.
"""

import httpx
import respx

from app.ingesta.alertas import CODIGO_FORMATO_INESPERADO
from app.ingesta.data912.cliente import descargar_tramo
from app.ingesta.http import crear_cliente

BASE_URL = "https://data912-test.local"


async def _no_dormir(_: float) -> None:
    return None


async def test_una_lista_plana_se_ingiere_entera() -> None:
    filas = [{"symbol": "AL30D", "c": 56.5}, {"symbol": "GD30D", "c": 58.0}]

    with respx.mock:
        ruta = respx.get(f"{BASE_URL}/live/arg_bonds").mock(
            return_value=httpx.Response(200, json=filas)
        )

        async with crear_cliente() as cliente:
            resultado = await descargar_tramo(cliente, BASE_URL, "arg_bonds", dormir=_no_dormir)

        assert resultado.filas == filas
        assert resultado.alertas == []
        assert ruta.call_count == 1


async def test_un_objeto_en_vez_de_lista_es_formato_inesperado_sin_excepcion() -> None:
    """`{"Error": "..."}` con HTTP 200 — verificado en vivo contra el histórico de un ticker
    inexistente. Un tramo con esta forma no debe tumbar la corrida ni cortar a los otros tramos."""
    with respx.mock:
        respx.get(f"{BASE_URL}/live/arg_corp").mock(
            return_value=httpx.Response(200, json={"Error": "Nahh no tengo ese ticker loko"})
        )

        async with crear_cliente() as cliente:
            resultado = await descargar_tramo(cliente, BASE_URL, "arg_corp", dormir=_no_dormir)

    assert resultado.filas == []
    (alerta,) = resultado.alertas
    assert alerta.codigo == CODIGO_FORMATO_INESPERADO
    assert alerta.detalle["tramo"] == "arg_corp"
    assert alerta.detalle["cuerpo"] == {"Error": "Nahh no tengo ese ticker loko"}


async def test_una_lista_vacia_se_reintenta_antes_de_declarar_el_fallo() -> None:
    """Un tramo `live/` nunca es una lista vacía legítima: data912 arrastra el último cierre
    conocido, así que hasta un sábado con el mercado cerrado devuelve el universo entero."""
    respuestas = [
        httpx.Response(200, json=[]),
        httpx.Response(200, json=[{"symbol": "AL30D", "c": 56.5}]),
    ]

    with respx.mock:
        ruta = respx.get(f"{BASE_URL}/live/arg_bonds").mock(side_effect=respuestas)

        async with crear_cliente() as cliente:
            resultado = await descargar_tramo(cliente, BASE_URL, "arg_bonds", dormir=_no_dormir)

        assert resultado.filas == [{"symbol": "AL30D", "c": 56.5}]
        assert resultado.alertas == []
        assert ruta.call_count == 2


async def test_un_500_persistente_se_agota_y_lanza() -> None:
    from app.ingesta.http import ErrorDeFuente

    with respx.mock:
        respx.get(f"{BASE_URL}/live/arg_stocks").mock(return_value=httpx.Response(500))

        async with crear_cliente() as cliente:
            lanzo = False
            try:
                await descargar_tramo(cliente, BASE_URL, "arg_stocks", dormir=_no_dormir)
            except ErrorDeFuente:
                lanzo = True
        assert lanzo
