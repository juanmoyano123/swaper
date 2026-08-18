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

## Contrato de `app/externos/`

Todo esto se consulta en vivo y nunca se persiste (ver `sec.py`, el mismo contrato). No se
adivina qué documento corresponde a qué clase/serie de ON: la investigación original ya midió que no
hay una regla general para derivarlo del ticker (funciona para Cresud, no para IRSA), y acá se suma
evidencia nueva — un mismo Suplemento puede cubrir varias clases a la vez ("Clase XIX & XX"). Los
documentos se listan tal como la CNV los agrupa, y el asesor elige a ojo cuál corresponde.
"""

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

import httpx
import structlog

from app.externos.cache import CacheConTTL

logger = structlog.get_logger()

BASE_SITIO = "https://www.cnv.gov.ar/SitioWeb"
BASE_AIF = "https://aif2.cnv.gov.ar"
BASE_BLOB = "https://blob.cnv.gov.ar/BlobWebService.svc"

USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"
TIMEOUT_SEGUNDOS = 15.0

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
        if not _UUID_RE.fullmatch(uuid):
            raise ValueError(f"uuid con formato inesperado: {uuid!r}")

        url = f"{BASE_AIF}/presentations/publicview/{uuid}"
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            respuesta = await cliente.get(url, headers={"User-Agent": USER_AGENT})
        respuesta.raise_for_status()
        return _extraer_primer_archivo(respuesta.text)

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


def _extraer_primer_archivo(html_publicview: str) -> ArchivoAdjunto | None:
    m = re.search(r"var presentation ='(.*?)';", html_publicview, re.S)
    if m is None:
        return None
    xml = m.group(1)

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
