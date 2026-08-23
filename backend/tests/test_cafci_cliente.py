import httpx
import pytest
import respx

from app.ingesta.cafci.cliente import POLITICA, descargar_planilla
from app.ingesta.http import ErrorDeFuente

URL = "https://api.pub.cafci.org.ar/pb_get"
POLITICA_INTENTOS = POLITICA.intentos


async def _no_dormir(_segundos: float) -> None:
    return None


async def test_descarga_ok_extrae_fecha_del_filename() -> None:
    with respx.mock:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200,
                content=b"contenido-xlsx-simulado",
                headers={"content-disposition": 'attachment; filename="20260821_Planilla_Diaria_A.xlsx"'},
            )
        )
        respuesta = await descargar_planilla(URL)

    assert respuesta.contenido == b"contenido-xlsx-simulado"
    assert respuesta.fecha_planilla_cruda == "20260821"


async def test_sin_content_disposition_es_error_no_reintentable() -> None:
    with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, content=b"algo"))
        with pytest.raises(ErrorDeFuente) as exc_info:
            await descargar_planilla(URL)

    assert exc_info.value.reintentable is False


async def test_filename_con_formato_inesperado_es_error_no_reintentable() -> None:
    with respx.mock:
        respx.get(URL).mock(
            return_value=httpx.Response(
                200,
                content=b"algo",
                headers={"content-disposition": 'attachment; filename="reporte_final.xlsx"'},
            )
        )
        with pytest.raises(ErrorDeFuente) as exc_info:
            await descargar_planilla(URL)

    assert exc_info.value.reintentable is False


async def test_respuesta_vacia_es_reintentable() -> None:
    with respx.mock:
        ruta = respx.get(URL).mock(return_value=httpx.Response(200, content=b""))
        with pytest.raises(ErrorDeFuente):
            await descargar_planilla(URL, dormir=_no_dormir)

    assert ruta.call_count == POLITICA_INTENTOS


async def test_http_500_se_reintenta_y_despues_funciona() -> None:
    with respx.mock:
        respx.get(URL).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(
                    200,
                    content=b"ok-segunda-vez",
                    headers={"content-disposition": 'attachment; filename="20260821_Planilla_Diaria_A.xlsx"'},
                ),
            ]
        )
        respuesta = await descargar_planilla(URL, dormir=_no_dormir)

    assert respuesta.contenido == b"ok-segunda-vez"
