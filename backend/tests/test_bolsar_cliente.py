"""El fallback de Bolsar: lee el emisor del HTML o no devuelve nada.

Los fragmentos son recortes literales de `bolsar.info/infoObligacion.php?on=TSC3O`, bajado el
28/08/2026. Importa que sean literales: lo que se prueba es una expresión regular contra un HTML
que nadie nos garantiza, y un fragmento "limpiado" a mano probaría el parser contra un ideal en vez
de contra la página real —los atributos `class="odd"` alternados y el `<th>` doble en vez de
`<th>`/`<td>` son exactamente lo que hay que absorber—.
"""

import respx
from httpx import Response

from app.externos.bolsar import URL_OBLIGACION, emisor_bolsar
from app.ingesta.http import crear_cliente

# Recorte literal de la tabla real, con la fila anterior y la siguiente para que la expresión tenga
# que elegir la correcta y no quedarse con la primera que aparezca.
HTML_REAL = """
<tbody id="titulo-table">
    <tr><th style="width: 25%;">Especie</th><th>TSC3O</th></tr>
    <tr><th class="odd">Emisor</th><th class="odd">TRANSPORTADORA DE GAS DEL SUR S.A.</th></tr>
    <tr><th>Denominación de la especie</th><th>CLASE 3</th></tr>
    <tr><th class="odd">Tipo de Especie</th><th class="odd"></th></tr>
</tbody>
"""


def _url(ticker: str) -> str:
    return f"{URL_OBLIGACION}?on={ticker}"


async def test_extrae_el_emisor_del_html() -> None:
    with respx.mock:
        respx.get(_url("TSC3O")).mock(return_value=Response(200, text=HTML_REAL))
        async with crear_cliente() as cliente:
            assert await emisor_bolsar(cliente, "TSC3O") == "TRANSPORTADORA DE GAS DEL SUR S.A."


async def test_resuelve_las_entidades_html() -> None:
    html = '<tr><th class="odd">Emisor</th><th class="odd">PAMPA &amp; CIA S.A.</th></tr>'
    with respx.mock:
        respx.get(_url("PAMPA")).mock(return_value=Response(200, text=html))
        async with crear_cliente() as cliente:
            assert await emisor_bolsar(cliente, "PAMPA") == "PAMPA & CIA S.A."


async def test_html_inesperado_devuelve_none() -> None:
    """Un emisor a medias es peor que ninguno: se muestra como si fuera el dato y nadie lo
    audita."""
    with respx.mock:
        respx.get(_url("TSC3O")).mock(
            return_value=Response(200, text="<html><body>Sitio en mantenimiento</body></html>")
        )
        async with crear_cliente() as cliente:
            assert await emisor_bolsar(cliente, "TSC3O") is None


async def test_la_fila_sin_valor_devuelve_none() -> None:
    """Bolsar sirve la misma página para un ticker que no conoce, a veces con la fila vacía."""
    html = '<tr><th class="odd">Emisor</th><th class="odd">   </th></tr>'
    with respx.mock:
        respx.get(_url("XXXXO")).mock(return_value=Response(200, text=html))
        async with crear_cliente() as cliente:
            assert await emisor_bolsar(cliente, "XXXXO") is None


async def test_una_caida_de_bolsar_devuelve_none_y_no_lanza() -> None:
    """A diferencia de la ficha de BYMA, acá una caída no se propaga: es el fallback del fallback y
    no puede abortar un barrido que ya trajo cientos de emisores."""
    with respx.mock:
        respx.get(_url("TSC3O")).mock(return_value=Response(500))
        async with crear_cliente() as cliente:
            assert await emisor_bolsar(cliente, "TSC3O") is None
