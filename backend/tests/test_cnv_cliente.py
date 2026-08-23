"""`ClienteCnv` — F-072: documentos de un emisor y el PDF real detrás de cada uno.

Todo se mockea con `respx`: la CNV no es una fuente
contractual y una suite que le pegara de verdad sería lenta y frágil. Los fragmentos de HTML/XML
son shapes mínimos, recortados de páginas reales verificadas en vivo el 17/08/2026 — no inventados.
"""

from urllib.parse import parse_qs, urlparse

import pytest
import respx
from httpx import Response

from app.externos.cnv import (
    BASE_AIF,
    BASE_BLOB,
    BASE_SITIO,
    ClienteCnv,
    RespuestaInesperadaDeCnv,
    url_detalles_formulario,
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

# Un Suplemento que cubre dos clases a la vez: la serie viene en una entidad `Grilla`, una `<fila>`
# por serie. Recortado del real de Telecom del 26/05/2026 (Clase 29 = 88539, Clase 30 = 88540).
# `DesplegableSerieIndividual` va a propósito: empieza igual que `DesplegableSerie` y no tiene que
# confundirse con ella, y su valor -1 tampoco tiene que colarse como si fuera un id de serie.
HTML_PUBLICVIEW_DOS_SERIES = (
    "<html><head><script>"
    "var presentation ='<modeloDatos>"
    '<entidad visibilidad="true" id="10004" clave="Grilla" grid="1" numeroelementos="2">'
    '<fila identificador="1" orden="1">'
    '<propiedad id="DesplegableSerie" claveinformativa="DesplegableSerie">88539</propiedad>'
    '<propiedad id="DescripcionDeLaSerie" claveinformativa="DescripcionDeLaSerie">Clase 29'
    "</propiedad>"
    '<propiedad id="DesplegableSerieIndividual" claveinformativa="DesplegableSerieIndividual">-1'
    "</propiedad>"
    '<propiedad id="DescripcionDeLaSerieIndividual" claveinformativa="x" />'
    "</fila>"
    '<fila identificador="2" orden="2">'
    '<propiedad id="DesplegableSerie" claveinformativa="DesplegableSerie">88540</propiedad>'
    '<propiedad id="DescripcionDeLaSerie" claveinformativa="DescripcionDeLaSerie">Clase 30'
    "</propiedad>"
    "</fila>"
    "</entidad></modeloDatos>';"
    "</script></head><body></body></html>"
)

# Un Aviso de Pago: una sola serie, declarada suelta dentro de la entidad, sin grilla. La otra forma
# real que trae la misma fuente — verificada el 18/08/2026 contra Telecom Clase 18.
HTML_PUBLICVIEW_UNA_SERIE_SUELTA = (
    "<html><head><script>"
    "var presentation ='<modeloDatos>"
    '<entidad visibilidad="true" id="10001" clave="Datos">'
    '<propiedad id="DescripcionPrograma" visible="true">Res Nº19,481</propiedad>'
    '<propiedad id="DesplegableSerie" visible="true" claveinformativa="DesplegableSerie">86337'
    "</propiedad>"
    '<propiedad id="DescripcionDeLaSerie" visible="true" claveinformativa="DescripcionDeLaSerie">'
    "Clase 18</propiedad>"
    "</entidad></modeloDatos>';"
    "</script></head><body></body></html>"
)

UUID_DETALLES_A = "bc077304-df6b-4b0e-8320-ee82dfdf520c"
UUID_DETALLES_B = "ac613ae1-04ae-4d55-aa2a-88f3a7db9f29"

# `DetallesDeFormularios`: otra plantilla que la del emisor — `<tr class="text-center">`, fecha en
# `DD-MM-YYYY` y una columna "Formulario" en lugar de la descripción larga.
HTML_DETALLES = f"""
<html><body>
<table class="table container">
<div class="text-center"><h1><b> TELECOM ARGENTINA S.A.</b></h1><h3>30-63945373-8</h3></div>
<div><h3>Detalles De Formularios de <b>Clase 29</b></h3></div>
<thead>
    <tr class="text-uppercase fs-2">
        <th class="text-center">Fecha</th>
        <th class="text-center">Hora</th>
        <th class="text-center">Documento</th>
        <th class="text-center">Formulario</th>
        <th class="text-center">Ver</th>
    </tr>
</thead>
<tbody>
    <tr class="text-center">
        <td>24-05-2026</td>
        <td>10:16 Hs</td>
        <td>3527921</td>
        <td>Aviso de Suscripción</td>
        <td><a href="{BASE_AIF}/Presentations/publicview/{UUID_DETALLES_A}" target="_blank">
            <i class="material-icons">add_circle_outline</i></a></td>
    </tr>
    <tr class="text-center">
        <td>26-05-2026</td>
        <td>08:52 Hs</td>
        <td>3527952</td>
        <td>Suplemento</td>
        <td><a href="{BASE_AIF}/Presentations/publicview/{UUID_DETALLES_B}" target="_blank">
            <i class="material-icons">add_circle_outline</i></a></td>
    </tr>
</tbody>
</table>
</body></html>
"""

# El mismo encabezado, cero filas: lo que devuelve un `serieID` inexistente. HTTP 200, no un error —
# verificado en vivo con `serieID=0` y con uno de nueve dígitos.
HTML_DETALLES_SIN_FILAS = (
    HTML_DETALLES[: HTML_DETALLES.index("<tbody>")] + "<tbody></tbody></table>"
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


# --- series_de ---------------------------------------------------------------------------------


async def _series_desde(html: str) -> list:
    with respx.mock:
        respx.get(f"{BASE_AIF}/presentations/publicview/{UUID_PROSPECTO}").mock(
            return_value=Response(200, text=html)
        )
        return await ClienteCnv().series_de(UUID_PROSPECTO)


async def test_series_de_devuelve_las_dos_clases_que_un_suplemento_declara() -> None:
    """Un documento puede cubrir varias clases a la vez y se devuelven todas: quedarse con la
    primera sería elegir por el asesor cuál importa, que es el juicio inventado que prohíbe la
    regla 1."""
    series = await _series_desde(HTML_PUBLICVIEW_DOS_SERIES)

    assert [(s.serie_id, s.nombre) for s in series] == [
        ("88539", "Clase 29"),
        ("88540", "Clase 30"),
    ]


async def test_series_de_lee_la_serie_declarada_suelta_en_la_entidad_sin_grilla() -> None:
    """La otra forma real de la fuente: un Aviso de Pago no arma grilla y declara su única serie
    como propiedades sueltas."""
    series = await _series_desde(HTML_PUBLICVIEW_UNA_SERIE_SUELTA)

    assert [(s.serie_id, s.nombre) for s in series] == [("86337", "Clase 18")]


async def test_series_de_vacio_cuando_el_documento_no_declara_ninguna() -> None:
    """No todos los formularios declaran serie. Se informa la ausencia; no se le supone la del
    documento de al lado."""
    assert await _series_desde(HTML_PUBLICVIEW_SIN_ARCHIVO) == []


async def test_series_de_rechaza_un_uuid_con_formato_inesperado() -> None:
    with pytest.raises(ValueError):
        await ClienteCnv().series_de("'; DROP TABLE presentations;--")


# --- documentos_de_la_serie --------------------------------------------------------------------


async def test_documentos_de_la_serie_lee_la_tabla_con_su_propio_formato_de_fecha() -> None:
    """`DD-MM-YYYY` con guiones, no el "24 may. 2026" de la página del emisor: son dos plantillas
    distintas de la misma fuente y cada una se parsea con la suya."""
    with respx.mock:
        ruta = respx.get(f"{BASE_SITIO}/Empresas/DetallesDeFormularios").mock(
            return_value=Response(200, text=HTML_DETALLES)
        )
        documentos = await ClienteCnv().documentos_de_la_serie(
            "88539", nombre_serie="Clase 29", cuit="30-63945373-8", nombre_sociedad="TELECOM"
        )

    assert documentos is not None
    assert len(documentos) == 2
    primero = documentos[0]
    assert primero.fecha is not None
    assert primero.fecha.isoformat() == "2026-05-24"
    assert primero.hora == "10:16 Hs"
    assert primero.documento_id == "3527921"
    assert primero.formulario == "Aviso de Suscripción"
    assert primero.uuid == UUID_DETALLES_A
    assert documentos[1].formulario == "Suplemento"
    # El CUIT viaja sin guiones, igual que en el resto del módulo.
    assert ruta.calls.last.request.url.params["idfiscal"] == "30639453738"


async def test_documentos_de_la_serie_lista_vacia_cuando_la_fuente_no_lista_nada() -> None:
    """Lista vacía y no `None`: un `serieID` inexistente devuelve 200 con la tabla vacía, así que
    esto es lo que la fuente contestó — no se puede leer como "la serie no existe"."""
    with respx.mock:
        respx.get(f"{BASE_SITIO}/Empresas/DetallesDeFormularios").mock(
            return_value=Response(200, text=HTML_DETALLES_SIN_FILAS)
        )
        documentos = await ClienteCnv().documentos_de_la_serie("999999999")

    assert documentos == []


async def test_documentos_de_la_serie_none_cuando_la_respuesta_no_es_la_tabla_esperada() -> None:
    """Sin el encabezado en el orden conocido no hay licencia para leer las celdas por posición: se
    declara que no se pudo, en vez de devolver la hora en el lugar de la fecha."""
    with respx.mock:
        respx.get(f"{BASE_SITIO}/Empresas/DetallesDeFormularios").mock(
            return_value=Response(200, text="<html><body>Error</body></html>")
        )
        assert await ClienteCnv().documentos_de_la_serie("88539") is None


async def test_documentos_de_la_serie_rechaza_un_serie_id_que_no_es_numerico() -> None:
    with pytest.raises(ValueError):
        await ClienteCnv().documentos_de_la_serie("88539 OR 1=1")


# --- url_detalles_formulario -------------------------------------------------------------------


def test_url_detalles_formulario_arma_la_url_con_los_cuatro_parametros() -> None:
    url = url_detalles_formulario(
        "88765",
        "Obligaciones Negociables Clase XXIV",
        "30-71412830-9",
        "YPF ENERGÍA ELÉCTRICA S.A.",
    )

    assert url.startswith(f"{BASE_SITIO}/Empresas/DetallesDeFormularios?")
    parametros = parse_qs(urlparse(url).query)
    assert parametros["serieID"] == ["88765"]
    assert parametros["nombreserie"] == ["Obligaciones Negociables Clase XXIV"]
    assert parametros["idfiscal"] == ["30714128309"]
    assert parametros["nombresociedad"] == ["YPF ENERGÍA ELÉCTRICA S.A."]


def test_url_detalles_formulario_deja_vacio_lo_que_no_se_pudo_resolver() -> None:
    """Sólo `serieID` filtra; los otros tres rotulan el encabezado. Si no se resolvió el emisor, el
    link sigue sirviendo y el encabezado va vacío — no se completa con nada supuesto."""
    parametros = parse_qs(
        urlparse(url_detalles_formulario("88765", None, None, None)).query, keep_blank_values=True
    )

    assert parametros["serieID"] == ["88765"]
    assert parametros["nombreserie"] == [""]
    assert parametros["idfiscal"] == [""]
