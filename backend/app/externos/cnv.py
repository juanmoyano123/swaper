"""Cliente de la CNV — los documentos filed por un emisor y el PDF real detrás de cada uno.

## Por qué esto y no lo que decía la investigación original

`claude-docs/planning/investigacion-cnv-sec.md` dejaba pendiente el prospecto de emisión: dos
intentos de `GET blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{id}` dieron 503, sin
diagnosticar la causa. **No era un bloqueo de la fuente**: era la forma de pedirlo. Reconstruido
leyendo el JS que sirve `aif2.cnv.gov.ar` (`site.bo.min.js`, función `getPublicBlob`), verificado
en vivo el 17/08/2026 con un PDF real de 1,33 MB bajado por `curl` puro, sin sesión:

1. `GET Empresas/AutoComplete?term={nombre}` — nombre de emisor a CUIT. JSON, sin scraping.
2. `GET Empresas/Empresa/{cuit}?formType=EMISIO&fdesde=1/1/2015` — los documentos del emisor,
   agrupados por tipo tal como la CNV los declara (Prospectos, Suplementos, Avisos...), cada uno con
   un link a `aif2.cnv.gov.ar/presentations/publicview/{uuid}`. **El CUIT va sin guiones y el
   parámetro `fdesde` es obligatorio** — sin eso la ruta devuelve 200 con la página genérica de
   "últimas colocaciones" de toda la CNV en vez de los documentos del emisor pedido: un fallo
   silencioso, no un error.
3. Dentro de esa `publicview`, el documento adjunto (el PDF real) trae su propio `guid` — no es el
   mismo `uuid` de la presentación — en una propiedad del formulario (`ArchSupCom`/`ArchSupRes`,
   según el tipo de formulario).
4. `GET api/ValetKeyProvider/GetPublicValetKey/{guid}?operation=DownloadBlob` → un token temporal
   ("valet key"), público, sin login.
5. `POST blob.cnv.gov.ar/BlobWebService.svc/DownloadBlob/{guid}` con ese token como body
   **form-urlencoded** (`ValetKey=...`) — no JSON, eso da 400 — devuelve el PDF crudo.

## El drill-down a la serie, en el sentido que sí se puede recorrer

Sigue sin haber forma de derivar la serie desde el ticker. Pero **cada documento declara la suya**:
dentro de la misma `publicview` que ya se lee para el adjunto hay una grilla de filas con
`DesplegableSerie` (el id numérico) y `DescripcionDeLaSerie` (cómo la nombra la fuente). Con ese id,
`Empresas/DetallesDeFormularios?serieID={id}` lista los 3-5 documentos de esa serie sola en vez de
la carpeta entera del emisor.

La dirección importa: no resuelve "qué serie es mi ticker" —eso seguiría siendo un invento— sino
"qué serie es este documento que el asesor ya tiene delante". De ahí en adelante es una cadena de
ids sin ambigüedad. Verificado el 18/08/2026 contra Telecom: el Suplemento del 26/05/2026 declara
**dos** series a la vez (Clase 29 = 88539 y Clase 30 = 88540), lo que confirma desde la fuente lo
que la investigación original ya sospechaba de los "Clase XIX & XX". Por eso se devuelven todas las
que el documento declare y nunca "la primera": elegir una sería exactamente el juicio inventado que
la regla 1 prohíbe.

`serieID` es la única clave real de `DetallesDeFormularios` — verificado pasando un `serieID` con el
`idfiscal`/`nombresociedad` de otro emisor: la página igual devuelve los documentos del `serieID`
pedido. Los otros tres parámetros sólo arman el encabezado que se ve en pantalla.

## Contrato de `app/externos/`

Todo esto se consulta en vivo y nunca se persiste (ver `sec.py`, el mismo contrato). No se
adivina qué documento corresponde a qué clase/serie de ON: la investigación original ya midió que no
hay una regla general para derivarlo del ticker (funciona para Cresud, no para IRSA). Los documentos
se listan tal como la CNV los agrupa, y el asesor elige a ojo cuál corresponde.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from urllib.parse import urlencode

import httpx
import structlog

from app.externos.cache import CacheConTTL

logger = structlog.get_logger()

BASE_SITIO = "https://www.cnv.gov.ar/SitioWeb"
BASE_AIF = "https://aif2.cnv.gov.ar"
BASE_BLOB = "https://blob.cnv.gov.ar/BlobWebService.svc"

USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"

# 30 s y no 15: la página de un emisor grande pesa cientos de KB y la CNV la sirve lenta. Con 15 s
# los emisores más pesados daban ReadTimeout de a ratos —verificado con Telecom (508 documentos),
# que falla y al reintentar responde—, y el bloque mostraba "la CNV no respondió" por un límite
# nuestro, no por un problema de la fuente. Esperar el doble es barato: el bloque carga aparte del
# resto de la ficha y no bloquea nada más de la pantalla.
TIMEOUT_SEGUNDOS = 30.0

# La ventana vieja está tolerada (verificado: 307 documentos de un emisor real con esta fecha,
# contra 185 con la ventana de 4 años). Fija y amplia: no hay razón de negocio para acotarla, y
# variarla por request sólo agrega una superficie de fallo (una fecha mal formada = página
# genérica, el mismo fallo silencioso que el CUIT sin normalizar).
FDESDE_FIJO = "1/1/2015"

TTL_SEGUNDOS_CACHE_EMISOR = 60 * 60 * 24  # un día — la página pesa hasta ~430 KB.

_MESES_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}  # fmt: skip

# Un grupo del accordion: `<div class="panel">...<strong>{titulo}</strong>...` hasta el próximo
# `<div class="panel">` (o el final del documento). Split, no un parser HTML completo — mismo
# criterio que `sec.py::catalogo_sic`: HTML servido y estable, no vale la pena una dependencia nueva
# para esto.
_PANEL_SPLIT_RE = re.compile(r'<div class="panel">\s*<div class="panel-heading"')
_TITULO_RE = re.compile(r"<strong>\s*(.*?)\s*</strong>", re.S)
_FILA_RE = re.compile(
    r"<tr>\s*<td>\s*(?P<fecha>[^<]*?)\s*</td>\s*<td>\s*(?P<hora>[^<]*?)\s*</td>\s*"
    r"<td>\s*(?P<descripcion>.*?)\s*</td>\s*<td>\s*(?P<documento_id>[^<]*?)\s*</td>\s*"
    r'<td[^>]*>\s*<a href="(?P<href>[^"]+)"',
    re.S,
)
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

# El marcador que distingue la página de resultados de la genérica. El título "Resultados de
# búsqueda" **no sirve**: aparece en las dos (es parte del template del buscador, vacío o lleno) —
# verificado el 17/08/2026 contra un CUIT real y contra el fallback. Lo que sólo aparece cuando hay
# resultados es el acordeón de grupos (`<div class="panel">`): 12 en la página real, 0 en la
# genérica. Si un emisor real tuviera cero documentos, esto también daría "sin confirmar" en vez de
# "cero documentos" — la distinción correcta según la regla 1: no se afirma una ausencia que no se
# puede probar distinta de un fallo de la fuente.
_MARCADOR_RESULTADOS = '<div class="panel">'

# Las propiedades del formulario que traen un archivo adjunto. Varían por tipo de formulario —un
# Suplemento trae `ArchSupCom`/`ArchSupRes`, otros formularios otras claves— así que se prueban
# todas y se toma la primera que aparezca con al menos un archivo.
_PROPIEDADES_CON_ARCHIVO = ("ArchSupCom", "ArchSupRes", "ArchProsp", "Archivo")

# La serie viene declarada en dos formas distintas según el tipo de formulario, las dos verificadas
# el 18/08/2026 contra Telecom: un Aviso de Pago (una sola serie) la trae como propiedades sueltas
# dentro de su entidad, y un Suplemento que cubre dos clases la trae en una entidad `Grilla` con una
# `<fila>` por serie. Por eso se recorre bloque a bloque en vez de buscar las propiedades sueltas en
# todo el XML: con dos ids y dos descripciones, buscarlas por separado las emparejaría por orden de
# aparición en vez de por pertenencia.
_ENTIDAD_XML_RE = re.compile(r"<entidad\b[^>]*>(.*?)</entidad>", re.S)
_FILA_XML_RE = re.compile(r"<fila\b[^>]*>(.*?)</fila>", re.S)

# El valor de una propiedad del XML. `[^<]*` y no `.*?` a propósito: una propiedad sin valor viene
# autocerrada (`<propiedad id="X" claveinformativa="X" />`) y sin esto el `.*?` se comería el tag
# siguiente hasta el próximo `</propiedad>`, devolviendo el valor de otra propiedad como si fuera
# de ésta. Es el mismo bug que ya se corrigió con los corchetes del nombre de archivo.
_VALOR_PROPIEDAD_TPL = r'<propiedad id="{clave}"(?:\s[^>]*?)?>([^<]*)</propiedad>'

# El id se pide con la comilla de cierre pegada: sin eso `DesplegableSerie` también matchearía
# `DesplegableSerieIndividual`, que es otra propiedad (vale -1 en las filas verificadas).
_SERIE_ID_RE = re.compile(_VALOR_PROPIEDAD_TPL.format(clave="DesplegableSerie"))
_SERIE_NOMBRE_RE = re.compile(_VALOR_PROPIEDAD_TPL.format(clave="DescripcionDeLaSerie"))

# El encabezado de `DetallesDeFormularios`, en el orden exacto en que la página sirve las columnas.
# Es el marcador de que la respuesta es la tabla esperada **y** la licencia para leer las celdas por
# posición: si la CNV reordena o renombra una columna esto deja de matchear y el parseo se declara
# fallido en vez de devolver la hora en el lugar de la fecha.
_ENCABEZADO_DETALLES_RE = re.compile(
    r"<thead>.*?>\s*Fecha\s*</th>.*?>\s*Hora\s*</th>.*?>\s*Documento\s*</th>"
    r".*?>\s*Formulario\s*</th>.*?>\s*Ver\s*</th>.*?</thead>",
    re.S,
)

# Una fila de esa tabla. `<tr class="text-center">` y no el `<tr>` pelado de la página del emisor:
# son dos plantillas distintas de la CNV, con distinto orden de columnas y distinto formato de
# fecha.
_FILA_DETALLES_RE = re.compile(
    r'<tr class="text-center">\s*<td>\s*(?P<fecha>[^<]*?)\s*</td>\s*<td>\s*(?P<hora>[^<]*?)\s*</td>'
    r"\s*<td>\s*(?P<documento_id>[^<]*?)\s*</td>\s*<td>\s*(?P<formulario>[^<]*?)\s*</td>\s*"
    r'<td[^>]*>\s*<a href="(?P<href>[^"]+)"',
    re.S,
)


class RespuestaInesperadaDeCnv(Exception):
    """La CNV respondió 200 pero no con lo que se pidió (fallo silencioso de la fuente)."""


def url_emisor(cuit: str) -> str:
    """La ficha pública del emisor en la CNV — construible con sólo el CUIT, sin depender del
    parser. Es la salida de emergencia que el endpoint de la ficha siempre entrega: si el parseo de
    `documentos_de` falla o la CNV cambia el HTML, este link sigue funcionando igual."""
    cuit_normalizado = re.sub(r"\D", "", cuit)
    return f"{BASE_SITIO}/Empresas/Empresa/{cuit_normalizado}?formType=EMISIO&fdesde={FDESDE_FIJO}"


@dataclass(frozen=True, slots=True)
class DocumentoCnv:
    """Una fila de la tabla de documentos de un emisor, agrupada por `grupo` tal como la CNV lo
    declara (Prospectos, Suplementos, Aviso de Suscripción...)."""

    grupo: str
    fecha: date | None
    """`None` si la fuente trae una fecha que no se pudo leer — nunca se inventa una."""
    hora: str
    descripcion: str
    documento_id: str
    uuid: str
    """El id de la presentación (`aif2.cnv.gov.ar/presentations/publicview/{uuid}`) — no es el guid
    del archivo adjunto, que sale de `ClienteCnv.archivo_de`."""

    def url_publicview(self) -> str:
        return f"{BASE_AIF}/presentations/publicview/{self.uuid}"


@dataclass(frozen=True, slots=True)
class ArchivoAdjunto:
    """El archivo real (PDF) adjunto a una presentación, tal como la CNV lo declara."""

    guid: str
    nombre_archivo: str
    tamano_declarado: str
    """El tamaño tal como la fuente lo declara (ej. "1.33 MB") — texto, no se reinterpreta."""
    total_en_la_presentacion: int
    """Cuántos archivos tiene la presentación en total. 1 en el caso normal; cuando es más de uno
    se sirve el primero y se declara el resto — nunca se combinan ni se elige "el correcto"."""


@dataclass(frozen=True, slots=True)
class SerieDeclarada:
    """Una serie/clase que **este documento** declara cubrir, tal como la CNV la nombra.

    Un mismo documento puede declarar varias (verificado: el Suplemento de Telecom del 26/05/2026
    declara Clase 29 y Clase 30). Nunca se elige una como "la" serie del documento.
    """

    serie_id: str
    nombre: str | None
    """`None` cuando la fila trae el id pero no la descripción — se muestra el id pelado antes que
    inventarle un nombre."""


@dataclass(frozen=True, slots=True)
class DocumentoDeSerieCnv:
    """Una fila de `DetallesDeFormularios`: un documento de una serie puntual.

    No es un `DocumentoCnv`: esa otra tabla trae `descripcion` (el texto largo que arma la CNV con
    fechas y programa) y ésta trae `formulario` (el tipo, corto). Son campos distintos de plantillas
    distintas y no se normalizan a uno solo.
    """

    fecha: date | None
    hora: str
    documento_id: str
    formulario: str
    uuid: str

    def url_publicview(self) -> str:
        return f"{BASE_AIF}/presentations/publicview/{self.uuid}"


@dataclass(frozen=True, slots=True)
class PdfDescargado:
    contenido: bytes
    nombre_archivo: str
    content_type: str = "application/pdf"


def _fecha_es(texto: str) -> date | None:
    """"11 ago. 2026" -> date(2026, 8, 11). `None` si el formato no matchea — no se adivina."""
    m = re.match(r"(\d{1,2})\s+([a-zA-Z]{3})\.?\s+(\d{4})", texto.strip())
    if not m:
        return None
    dia, mes_abrev, anio = m.groups()
    mes = _MESES_ES.get(mes_abrev.lower())
    if mes is None:
        return None
    try:
        return date(int(anio), mes, int(dia))
    except ValueError:
        return None


def _fecha_dmy(texto: str) -> date | None:
    """"24-05-2026" -> date(2026, 5, 24). `None` si no matchea — no se adivina.

    `DetallesDeFormularios` sirve la fecha en numérico con guiones, no en el "24 may. 2026" de la
    página del emisor que lee `_fecha_es`. Son dos plantillas distintas de la misma fuente.
    """
    m = re.match(r"(\d{1,2})-(\d{1,2})-(\d{4})$", texto.strip())
    if not m:
        return None
    dia, mes, anio = m.groups()
    try:
        return date(int(anio), int(mes), int(dia))
    except ValueError:
        return None


def url_detalles_formulario(
    serie_id: str, nombre_serie: str | None, cuit: str | None, nombre_sociedad: str | None
) -> str:
    """La página de la CNV con los documentos de esta serie sola.

    Sólo `serieID` filtra; los otros tres arman el encabezado. Van igual —y vacíos cuando no se
    pudieron resolver— para que el asesor caiga en una página que se identifica, no en una anónima.
    """
    parametros = {
        "serieID": serie_id,
        "nombreserie": nombre_serie or "",
        "idfiscal": re.sub(r"\D", "", cuit) if cuit else "",
        "nombresociedad": nombre_sociedad or "",
    }
    return f"{BASE_SITIO}/Empresas/DetallesDeFormularios?{urlencode(parametros)}"


def _limpiar_html(bruto: str) -> str:
    sin_tags = re.sub(r"<[^>]+>", "", bruto)
    return (
        sin_tags.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .strip()
    )


class ClienteCnv:
    """Documentos de un emisor y el PDF real de cada uno. `dormir`/reloj no hacen falta acá: no hay
    límite de tasa publicado por la CNV, a diferencia de la SEC."""

    def __init__(self, *, timeout: float = TIMEOUT_SEGUNDOS) -> None:
        self._timeout = timeout
        # Sólo se cachea el resultado bueno (una lista, eventualmente vacía). El fallo silencioso
        # de la fuente (página genérica) nunca se cachea: `CacheConTTL.obtener` no distingue "no
        # hay entrada" de "la entrada guardada es None", así que cachear ese caso lo volvería
        # indistinguible de un cache miss — y de paso, un CUIT mal tipeado en una corrida de
        # curación quedaría "roto" durante todo el TTL en vez de poder reintentarse.
        self._cache_emisor: CacheConTTL[list[DocumentoCnv]] = CacheConTTL(
            TTL_SEGUNDOS_CACHE_EMISOR
        )

    async def documentos_de(self, cuit: str) -> list[DocumentoCnv] | None:
        """Los documentos de un emisor, agrupados. `None` cuando la CNV devolvió la página
        genérica en vez de los resultados de este CUIT (fallo silencioso de la fuente, se declara
        río arriba) — nunca una lista vacía disfrazando ese caso."""
        cuit_normalizado = re.sub(r"\D", "", cuit)
        cacheado = self._cache_emisor.obtener(cuit_normalizado)
        if cacheado is not None:
            return cacheado

        url = f"{BASE_SITIO}/Empresas/Empresa/{cuit_normalizado}"
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cliente:
            respuesta = await cliente.get(
                url,
                params={"formType": "EMISIO", "fdesde": FDESDE_FIJO},
                headers={"User-Agent": USER_AGENT},
            )
        respuesta.raise_for_status()
        html = respuesta.text

        if _MARCADOR_RESULTADOS not in html:
            logger.warning("cnv_pagina_generica", cuit=cuit_normalizado)
            return None

        documentos = _parsear_documentos(html)
        self._cache_emisor.guardar(cuit_normalizado, documentos)
        return documentos

    async def archivo_de(self, uuid: str) -> ArchivoAdjunto | None:
        """El primer archivo adjunto de una presentación, leyendo su `publicview`. `None` si la
        presentación no tiene ningún archivo adjunto (hay formularios que son sólo datos, sin
        documento — un Aviso puede no traer PDF propio)."""
        return _extraer_primer_archivo(await self._publicview(uuid))

    async def series_de(self, uuid: str) -> list[SerieDeclarada]:
        """Las series/clases que este documento declara cubrir, leyendo su `publicview`.

        Lista vacía cuando el formulario no trae la grilla de series: hay tipos que no la declaran,
        y eso se informa como ausente río arriba en vez de suponerle una.
        """
        return _extraer_series(await self._publicview(uuid))

    async def _publicview(self, uuid: str) -> str:
        if not _UUID_RE.fullmatch(uuid):
            raise ValueError(f"uuid con formato inesperado: {uuid!r}")

        url = f"{BASE_AIF}/presentations/publicview/{uuid}"
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            respuesta = await cliente.get(url, headers={"User-Agent": USER_AGENT})
        respuesta.raise_for_status()
        return respuesta.text

    async def documentos_de_la_serie(
        self,
        serie_id: str,
        *,
        nombre_serie: str | None = None,
        cuit: str | None = None,
        nombre_sociedad: str | None = None,
    ) -> list[DocumentoDeSerieCnv] | None:
        """Los documentos de una serie puntual. `None` cuando la respuesta no es la tabla esperada.

        Ojo con la diferencia entre `None` y `[]`: un `serieID` inexistente devuelve **200 con la
        tabla vacía**, no un error ni una página distinta (verificado con `serieID=0` y con uno de
        nueve dígitos). Así que la lista vacía es la respuesta de la fuente —"no listé documentos
        para esta serie"— y no se puede leer como "esta serie no existe". El `None` queda para el
        caso en que la CNV sirva algo que no es esta tabla, que es cuando el parseo no puede
        afirmar nada.
        """
        if not serie_id.isdigit():
            raise ValueError(f"serie_id con formato inesperado: {serie_id!r}")

        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cliente:
            respuesta = await cliente.get(
                f"{BASE_SITIO}/Empresas/DetallesDeFormularios",
                params={
                    "serieID": serie_id,
                    "nombreserie": nombre_serie or "",
                    "idfiscal": re.sub(r"\D", "", cuit) if cuit else "",
                    "nombresociedad": nombre_sociedad or "",
                },
                headers={"User-Agent": USER_AGENT},
            )
        respuesta.raise_for_status()
        html = respuesta.text

        if _ENCABEZADO_DETALLES_RE.search(html) is None:
            logger.warning("cnv_detalles_sin_encabezado_esperado", serie_id=serie_id)
            return None
        return _parsear_documentos_de_serie(html)

    async def descargar(self, guid: str) -> bytes:
        """El PDF crudo, por el intercambio de dos pasos verificado en vivo. Nunca se cachea: es
        contenido binario potencialmente grande, y el pedido es a demanda (un clic del asesor)."""
        if not _UUID_RE.fullmatch(guid):
            raise ValueError(f"guid con formato inesperado: {guid!r}")

        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            valet = await cliente.get(
                f"{BASE_AIF}/api/ValetKeyProvider/GetPublicValetKey/{guid}",
                params={"operation": "DownloadBlob"},
                headers={"User-Agent": USER_AGENT},
            )
            valet.raise_for_status()
            token = valet.json().get("valetKeyData")
            if not token:
                raise RespuestaInesperadaDeCnv(
                    f"GetPublicValetKey no trajo valetKeyData para {guid}"
                )

            descarga = await cliente.post(
                f"{BASE_BLOB}/DownloadBlob/{guid}",
                data={"ValetKey": token},  # form-urlencoded: en JSON la CNV devuelve 400.
                headers={"User-Agent": USER_AGENT},
            )
            descarga.raise_for_status()
            # Se valida el contenido, no el `content-type` declarado: el WCF de la CNV devuelve su
            # página de error con `text/html` cuando algo sale mal (el 400 verificado en vivo), pero
            # confiar sólo en la cabecera es más frágil que confirmar que el archivo empieza como un
            # PDF de verdad.
            if not descarga.content.startswith(b"%PDF"):
                raise RespuestaInesperadaDeCnv(
                    f"DownloadBlob no devolvió un PDF para {guid} (empieza con "
                    f"{descarga.content[:20]!r})"
                )
            return descarga.content


def _parsear_documentos(html: str) -> list[DocumentoCnv]:
    documentos: list[DocumentoCnv] = []
    for bloque in _PANEL_SPLIT_RE.split(html)[1:]:
        titulo_match = _TITULO_RE.search(bloque)
        if titulo_match is None:
            continue
        grupo = _limpiar_html(titulo_match.group(1))
        for fila in _FILA_RE.finditer(bloque):
            uuid_match = _UUID_RE.search(fila.group("href"))
            if uuid_match is None:
                # Un link que no tiene la forma esperada no se re-emite arbitrario (regla 1): se
                # descarta esa fila y se sigue con el resto.
                logger.warning("cnv_fila_sin_uuid_valido", href=fila.group("href"))
                continue
            documentos.append(
                DocumentoCnv(
                    grupo=grupo,
                    fecha=_fecha_es(fila.group("fecha")),
                    hora=fila.group("hora").strip(),
                    descripcion=_limpiar_html(fila.group("descripcion")),
                    documento_id=fila.group("documento_id").strip(),
                    uuid=uuid_match.group(0),
                )
            )
    return documentos


def _parsear_documentos_de_serie(html: str) -> list[DocumentoDeSerieCnv]:
    documentos: list[DocumentoDeSerieCnv] = []
    for fila in _FILA_DETALLES_RE.finditer(html):
        uuid_match = _UUID_RE.search(fila.group("href"))
        if uuid_match is None:
            logger.warning("cnv_fila_serie_sin_uuid_valido", href=fila.group("href"))
            continue
        documentos.append(
            DocumentoDeSerieCnv(
                fecha=_fecha_dmy(fila.group("fecha")),
                hora=fila.group("hora").strip(),
                documento_id=fila.group("documento_id").strip(),
                formulario=_limpiar_html(fila.group("formulario")),
                uuid=uuid_match.group(0),
            )
        )
    return documentos


def _xml_de_la_presentacion(html_publicview: str) -> str | None:
    m = re.search(r"var presentation ='(.*?)';", html_publicview, re.S)
    return m.group(1) if m is not None else None


def _bloques_con_serie(xml: str) -> Iterator[str]:
    """Los fragmentos donde un id de serie y una descripción son de la misma serie: cada `<fila>` de
    una entidad con grilla, o el cuerpo entero de la entidad cuando no tiene grilla."""
    for entidad in _ENTIDAD_XML_RE.finditer(xml):
        cuerpo = entidad.group(1)
        filas = _FILA_XML_RE.findall(cuerpo)
        yield from (filas or [cuerpo])


def _extraer_series(html_publicview: str) -> list[SerieDeclarada]:
    xml = _xml_de_la_presentacion(html_publicview)
    if xml is None:
        return []

    series: list[SerieDeclarada] = []
    vistas: set[str] = set()
    for bloque in _bloques_con_serie(xml):
        id_match = _SERIE_ID_RE.search(bloque)
        if id_match is None:
            continue
        serie_id = id_match.group(1).strip()
        # La grilla usa -1 y 0 como "ninguna" en los desplegables que quedaron sin elegir
        # (verificado en `DesplegableSerieIndividual`). Un id que no es un número positivo no
        # identifica ninguna serie y no se re-emite como si lo hiciera.
        if not serie_id.isdigit() or int(serie_id) <= 0 or serie_id in vistas:
            continue
        vistas.add(serie_id)
        nombre_match = _SERIE_NOMBRE_RE.search(bloque)
        nombre = _limpiar_html(nombre_match.group(1)) if nombre_match is not None else ""
        series.append(SerieDeclarada(serie_id=serie_id, nombre=nombre or None))
    return series


def _extraer_primer_archivo(html_publicview: str) -> ArchivoAdjunto | None:
    xml = _xml_de_la_presentacion(html_publicview)
    if xml is None:
        return None

    for propiedad in _PROPIEDADES_CON_ARCHIVO:
        idx = xml.find(f'id="{propiedad}"')
        if idx == -1:
            continue
        # El valor es un array JSON embebido dentro de la propiedad XML. Se recorta hasta el
        # `</propiedad>` que la cierra — **no** hasta el primer `]`: el nombre del archivo puede
        # traer corchetes propios (ej. "Suplemento de Prospecto [EXE].pdf"), que cortarían el
        # fragmento a mitad del array si se buscara el primer `]` literal.
        inicio = xml.find("[", idx)
        fin = xml.find("</propiedad>", idx)
        if inicio == -1 or fin == -1 or fin < inicio:
            continue
        fragmento = xml[inicio:fin]
        archivos = re.findall(
            r'"nombreArchivo":"(?P<nombre>[^"]*)"[^}]*"tamano":"(?P<tamano>[^"]*)"'
            r'[^}]*"guid":"(?P<guid>[0-9a-fA-F-]+)"',
            fragmento,
        )
        if not archivos:
            continue
        nombre, tamano, guid = archivos[0]
        return ArchivoAdjunto(
            guid=guid,
            nombre_archivo=nombre,
            tamano_declarado=tamano,
            total_en_la_presentacion=len(archivos),
        )
    return None


@lru_cache(maxsize=1)
def cliente_cnv() -> ClienteCnv:
    """El cliente compartido por todo el proceso: la caché de documentos por emisor sólo sirve si
    es una sola instancia. Mismo patrón que `cliente_yahoo`/`cliente_sec_ficha`."""
    return ClienteCnv()
