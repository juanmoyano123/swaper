"""`ClienteCnv` — F-072: documentos de un emisor y el PDF real detrás de cada uno.

Todo se mockea con `respx`, mismo criterio que `test_yahoo_cliente.py`: la CNV no es una fuente
contractual y una suite que le pegara de verdad sería lenta y frágil. Los fragmentos de HTML/XML
son shapes mínimos, recortados de páginas reales verificadas en vivo el 17/08/2026 — no inventados.
"""

import pytest
import respx
from httpx import Response

from app.externos.cnv import (
    BASE_AIF,
    BASE_BLOB,
    BASE_SITIO,
    ClienteCnv,
    RespuestaInesperadaDeCnv,
    url_emisor,
)

CUIT = "30714128309"
UUID_PROSPECTO = "96bad10a-713b-46e1-a9ac-04fa19f3a8cd"
UUID_SUPLEMENTO = "8dcb94d8-001c-4d99-b03e-264c546b86a3"
GUID_ARCHIVO = "4ce6fe56-f5f7-428b-f6ac-ef4ece785218"

# Dos grupos, cada uno con una fila — mismo shape que la página real (`<div class="panel">` por
# grupo, `<strong>` con el título, una tabla con fecha/hora/descripción/documento/link).
HTML_CON_RESULTADOS = f"""
<html><body>
<h2 class="title-resultados">Resultados de búsqueda:</h2>
<div class="panel">
    <div class="panel-heading">
        <h4><a><strong>Prospectos</strong></a></h4>
    </div>
    <div class="panel-body">
        <table><tbody>
        <tr>
            <td>11 ago. 2026</td>
            <td>15:34</td>
            <td>Un prospecto de prueba</td>
            <td>3557195</td>
            <td><a href="{BASE_AIF}/presentations/publicview/{UUID_PROSPECTO}" target="_blank">
                <i class="material-icons">add_circle_outline</i></a></td>
        </tr>
        </tbody></table>
    </div>
</div>
<div class="panel">
    <div class="panel-heading">
        <h4><a><strong>Suplementos</strong></a></h4>
    </div>
    <div class="panel-body">
        <table><tbody>
        <tr>
            <td>09 dic. 2025</td>
            <td>15:18</td>
            <td>Un suplemento con &amp; en el medio</td>
            <td>3452781</td>
            <td><a href="{BASE_AIF}/presentations/publicview/{UUID_SUPLEMENTO}" target="_blank">
                <i class="material-icons">add_circle_outline</i></a></td>
        </tr>
        </tbody></table>
    </div>
</div>
</body></html>
"""

# La CNV responde 200 con esto cuando el CUIT/fecha no matchea — el fallback genérico de "últimas
# colocaciones", sin acordeón de grupos. Verificado en vivo: 0 `<div class="panel">` acá, 12 en la
# página real.
HTML_GENERICA = """
<html><body>
<h2 class="title-resultados">Resultados de búsqueda:</h2>
<table><tbody>
<tr><td>YPF LUZ</td><td onclick="ObtenerSerieID_Para_DetallesFormularios(1,'x','y','z')"></td></tr>
</tbody></table>
</body></html>
"""

# El nombre trae corchetes propios ("[EXE]") — el caso real que rompía el parser cuando se cortaba
# en el primer `]` en vez de en `</propiedad>`.
HTML_PUBLICVIEW = (
    '<html><head><script>var blobHost = "https://blob.cnv.gov.ar/BlobWebService.svc/";'
    "var presentation ='<modeloDatos><entidad>"
    '<propiedad id="ArchSupCom" visible="true">'
    '[{"idUploader":"1","nombreArchivo":"Suplemento [EXE].pdf","tamano":"1.33 MB",'
    f'"guid":"{GUID_ARCHIVO}","hash":"abc"}}]'
    "</propiedad></entidad></modeloDatos>';"
    "</script></head><body></body></html>"
)

HTML_PUBLICVIEW_SIN_ARCHIVO = (
    "<html><head><script>"
    "var presentation ='<modeloDatos><entidad>"
    '<propiedad id="FechPu" visible="true">2026-08-11</propiedad>'
    "</entidad></modeloDatos>';"
    "</script></head><body></body></html>"
)


# --- documentos_de ---------------------------------------------------------------------------


async def test_documentos_de_agrupa_y_declara_el_grupo_tal_como_lo_trae_la_fuente() -> None:
    with respx.mock:
        respx.get(f"{BASE_SITIO}/Empresas/Empresa/{CUIT}").mock(
            return_value=Response(200, text=HTML_CON_RESULTADOS)
        )
        documentos = await ClienteCnv().documentos_de(CUIT)

    assert documentos is not None
    assert len(documentos) == 2
    prospecto, suplemento = documentos
    assert prospecto.grupo == "Prospectos"
    assert prospecto.uuid == UUID_PROSPECTO
    assert prospecto.documento_id == "3557195"
    assert prospecto.fecha is not None
    assert prospecto.fecha.isoformat() == "2026-08-11"
    assert suplemento.grupo == "Suplementos"
    # Las entidades HTML básicas se resuelven — el "&amp;" real que trae la fuente en descripciones
    # como "ON CLASE XIX & XX".
    assert "&" in suplemento.descripcion
    assert "&amp;" not in suplemento.descripcion


async def test_documentos_de_normaliza_el_cuit_sacando_guiones() -> None:
    with respx.mock:
        ruta = respx.get(f"{BASE_SITIO}/Empresas/Empresa/{CUIT}").mock(
            return_value=Response(200, text=HTML_CON_RESULTADOS)
        )
        documentos = await ClienteCnv().documentos_de("30-71412830-9")

    assert documentos is not None
    assert ruta.called


async def test_documentos_de_declara_none_cuando_la_fuente_devuelve_la_pagina_generica() -> None:
    """El caso real: CUIT o fecha mal formados dan HTTP 200 con la página de "últimas
    colocaciones" en vez de un 404 — un fallo silencioso que no se puede confundir con "el emisor
    no tiene documentos" (regla 1: se declara la incertidumbre, no se afirma una ausencia)."""
    with respx.mock:
        respx.get(f"{BASE_SITIO}/Empresas/Empresa/{CUIT}").mock(
            return_value=Response(200, text=HTML_GENERICA)
        )
        documentos = await ClienteCnv().documentos_de(CUIT)

    assert documentos is None


async def test_documentos_de_descarta_una_fila_con_uuid_invalido_sin_romper_el_resto() -> None:
    html_con_uuid_roto = HTML_CON_RESULTADOS.replace(UUID_SUPLEMENTO, "no-es-un-uuid")
    with respx.mock:
        respx.get(f"{BASE_SITIO}/Empresas/Empresa/{CUIT}").mock(
            return_value=Response(200, text=html_con_uuid_roto)
        )
        documentos = await ClienteCnv().documentos_de(CUIT)

    assert documentos is not None
    assert len(documentos) == 1
    assert documentos[0].grupo == "Prospectos"


async def test_documentos_de_cachea_por_cuit() -> None:
    with respx.mock:
        ruta = respx.get(f"{BASE_SITIO}/Empresas/Empresa/{CUIT}").mock(
            return_value=Response(200, text=HTML_CON_RESULTADOS)
        )
        cliente = ClienteCnv()
        await cliente.documentos_de(CUIT)
        await cliente.documentos_de(CUIT)

    assert ruta.call_count == 1


# --- archivo_de --------------------------------------------------------------------------------


async def test_archivo_de_extrae_el_guid_del_primer_archivo_adjunto() -> None:
    """El caso que rompía antes del fix: el nombre trae corchetes propios ("[EXE]") y el recorte
    del array JSON tiene que terminar en `</propiedad>`, no en el primer `]` literal."""
    with respx.mock:
        respx.get(f"{BASE_AIF}/presentations/publicview/{UUID_PROSPECTO}").mock(
            return_value=Response(200, text=HTML_PUBLICVIEW)
        )
        archivo = await ClienteCnv().archivo_de(UUID_PROSPECTO)

    assert archivo is not None
    assert archivo.guid == GUID_ARCHIVO
    assert archivo.nombre_archivo == "Suplemento [EXE].pdf"
    assert archivo.tamano_declarado == "1.33 MB"


async def test_archivo_de_none_cuando_la_presentacion_no_tiene_archivo_adjunto() -> None:
    """No todos los formularios traen un PDF — un Aviso puede ser sólo datos. No se inventa uno."""
    with respx.mock:
        respx.get(f"{BASE_AIF}/presentations/publicview/{UUID_PROSPECTO}").mock(
            return_value=Response(200, text=HTML_PUBLICVIEW_SIN_ARCHIVO)
        )
        archivo = await ClienteCnv().archivo_de(UUID_PROSPECTO)

    assert archivo is None


async def test_archivo_de_rechaza_un_uuid_con_formato_inesperado() -> None:
    with pytest.raises(ValueError):
        await ClienteCnv().archivo_de("'; DROP TABLE presentations;--")


# --- descargar -----------------------------------------------------------------------------------


async def test_descargar_hace_el_intercambio_de_dos_pasos_y_devuelve_el_pdf() -> None:
    with respx.mock:
        respx.get(f"{BASE_AIF}/api/ValetKeyProvider/GetPublicValetKey/{GUID_ARCHIVO}").mock(
            return_value=Response(200, json={"valetKeyData": "un-token-largo"})
        )
        descarga = respx.post(f"{BASE_BLOB}/DownloadBlob/{GUID_ARCHIVO}").mock(
            return_value=Response(
                200,
                content=b"%PDF-1.7 contenido",
                headers={"content-type": "application/octet-stream"},
            )
        )
        contenido = await ClienteCnv().descargar(GUID_ARCHIVO)

    assert contenido == b"%PDF-1.7 contenido"
    # El token viaja form-urlencoded, no JSON: la CNV da 400 con el otro formato (verificado en
    # vivo el 17/08/2026).
    enviado = descarga.calls.last.request
    assert enviado.headers["content-type"] == "application/x-www-form-urlencoded"
    assert b"ValetKey=un-token-largo" in enviado.content


async def test_descargar_detecta_cuando_la_cnv_devuelve_html_en_vez_del_archivo() -> None:
    with respx.mock:
        respx.get(f"{BASE_AIF}/api/ValetKeyProvider/GetPublicValetKey/{GUID_ARCHIVO}").mock(
            return_value=Response(200, json={"valetKeyData": "un-token"})
        )
        respx.post(f"{BASE_BLOB}/DownloadBlob/{GUID_ARCHIVO}").mock(
            return_value=Response(200, text="<html>Request Error</html>")
        )
        with pytest.raises(RespuestaInesperadaDeCnv):
            await ClienteCnv().descargar(GUID_ARCHIVO)


# --- url_emisor ------------------------------------------------------------------------------


def test_url_emisor_normaliza_el_cuit_y_fija_la_ventana_de_fecha() -> None:
    url = url_emisor("30-71412830-9")
    assert url == f"{BASE_SITIO}/Empresas/Empresa/30714128309?formType=EMISIO&fdesde=1/1/2015"
