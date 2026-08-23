"""Cliente de la API pública de la SEC — a qué se dedica la empresa detrás de un CEDEAR.

Es el único origen de perfil de empresa del proyecto desde el 13/08/2026, y se lo eligió por su
naturaleza y no por su cobertura: **publica una API con contrato**, documentada y con política de
acceso escrita. Cubre el 74 % de los CEDEARs y el 9 % de las acciones argentinas; lo que no alcanza
queda declarado faltante y no se completa desde ningún otro lado.

## Los tres pedidos, y qué da cada uno

1. `sec.gov/files/company_tickers.json` — ticker a CIK. **Una sola descarga para todo el universo**:
   son ~10.000 empresas en un JSON, y pedirlo por ticker sería multiplicar por mil el trabajo.
2. `data.sec.gov/submissions/CIK{cik:010d}.json` — el perfil: `name`, `sic`, `sicDescription`.
   Ojo: `description` y `website` vienen **vacíos** en este endpoint, así que el nombre y el código
   de actividad es todo lo que hay. Alcanza para lo que se pide.
3. La lista oficial de códigos SIC (HTML servido) — el título de la actividad y la **oficina de la
   SEC** que la revisa, que es una agrupación por rubro hecha por la propia fuente. 444 códigos.

## Lo que la SEC pide a cambio

Un `User-Agent` que identifique a quien consulta. **No es un truco para pasar un bloqueo**: es su
política de acceso publicada, y mandar uno falso sería usar la fuente en contra de sus términos.
Va con el mail del dueño del producto, como la propia SEC indica.

El límite es ~10 pedidos por segundo. Un 429 corta la corrida y se declara: la fuente está pidiendo
que paremos, y seguir insistiendo ticker por ticker sólo alarga el bloqueo.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

BASE_DATOS = "https://data.sec.gov"
BASE_WEB = "https://www.sec.gov"

URL_TICKERS = f"{BASE_WEB}/files/company_tickers.json"
URL_CATALOGO_SIC = f"{BASE_WEB}/search-filings/standard-industrial-classification-sic-code-list"

# La SEC pide identificarse. Va el contacto real del dueño del producto, como su política indica.
USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"

TIMEOUT_SEGUNDOS = 20.0

# La fuente admite ~10 pedidos por segundo. Se pide a la mitad de ese ritmo: el job es incremental
# y no tiene apuro, y quedarse corto no cuesta nada mientras que pasarse cuesta un bloqueo.
PAUSA_ENTRE_PEDIDOS_SEGUNDOS = 0.2


class LimiteDeLaFuente(Exception):
    """La SEC está limitando los pedidos (429). No es un error nuestro ni un dato que falte."""


@dataclass(frozen=True, slots=True)
class PerfilSec:
    """Lo que la SEC declara de una empresa. Cada campo puede faltar y ninguno se completa."""

    cik: int
    nombre: str | None
    sic: str | None
    sic_titulo: str | None
    """La descripción que la SEC devuelve junto al código, en el mismo pedido."""


@dataclass(frozen=True, slots=True)
class EntradaSic:
    """Una fila del catálogo oficial de códigos SIC."""

    codigo: str
    titulo: str
    oficina: str
    """La oficina de la SEC que revisa esa industria. Es una agrupación por rubro de la propia
    fuente, no una que hayamos armado nosotros."""


class ClienteSec:
    """Los tres pedidos, cada uno degradando por su cuenta.

    `dormir` es inyectable para que los tests no esperen de verdad.
    """

    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SEGUNDOS,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        pausa: float = PAUSA_ENTRE_PEDIDOS_SEGUNDOS,
    ) -> None:
        self._timeout = timeout
        self._dormir = dormir
        self._pausa = pausa

    async def _pedir(self, cliente: httpx.AsyncClient, url: str) -> httpx.Response:
        respuesta = await cliente.get(url, headers={"User-Agent": USER_AGENT})
        if respuesta.status_code == 429:
            raise LimiteDeLaFuente(
                "La SEC está limitando los pedidos desde esta conexión (HTTP 429): el bloque "
                "vuelve solo cuando la fuente deje de limitarnos."
            )
        respuesta.raise_for_status()
        return respuesta

    async def mapa_de_tickers(self) -> dict[str, int]:
        """`{'AAPL': 320193, ...}` — el ticker tal como lo publica la SEC, en mayúsculas.

        Un ticker que la SEC no lista simplemente no está en el dict: no tener CIK es no tener
        perfil, y eso se declara río arriba en vez de resolverse acá con un parecido.
        """
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            datos = (await self._pedir(cliente, URL_TICKERS)).json()
        mapa: dict[str, int] = {}
        for fila in datos.values():
            ticker = str(fila.get("ticker", "")).strip().upper()
            cik = fila.get("cik_str")
            if ticker and isinstance(cik, int):
                mapa[ticker] = cik
        return mapa

    async def perfil_de(self, cik: int) -> PerfilSec | None:
        """El perfil de una empresa por su CIK. `None` si la SEC no lo sirve.

        Los campos vacíos viajan como `None` y no como cadena vacía: quien los muestre tiene que
        poder distinguir "la fuente no lo declara" de "la fuente declara una cadena vacía", que
        para el asesor son lo mismo pero para auditar el dato no.
        """
        url = f"{BASE_DATOS}/submissions/CIK{cik:010d}.json"
        async with httpx.AsyncClient(timeout=self._timeout) as cliente:
            try:
                datos = (await self._pedir(cliente, url)).json()
            except httpx.HTTPStatusError as exc:
                logger.warning("sec_perfil_sin_respuesta", cik=cik, status=exc.response.status_code)
                return None
        return PerfilSec(
            cik=cik,
            nombre=_texto(datos.get("name")),
            sic=_texto(datos.get("sic")),
            sic_titulo=_texto(datos.get("sicDescription")),
        )

    async def catalogo_sic(self) -> dict[str, EntradaSic]:
        """Los 444 códigos SIC con su título y su oficina, del listado que publica la SEC.

        Se parsea el HTML servido —la SEC no lo ofrece como JSON— con una expresión sobre las filas
        de la tabla. Una fila que no tiene las tres celdas se saltea sin romper el resto: un
        catálogo incompleto sigue sirviendo, y lo que falte se declara donde se use.
        """
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as cliente:
            html = (await self._pedir(cliente, URL_CATALOGO_SIC)).text
        catalogo: dict[str, EntradaSic] = {}
        for fila in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
            celdas = [
                _limpiar_html(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", fila, re.S)
            ]
            celdas = [c for c in celdas if c]
            if len(celdas) < 3 or not celdas[0].isdigit():
                continue
            catalogo[celdas[0]] = EntradaSic(codigo=celdas[0], oficina=celdas[1], titulo=celdas[2])
        return catalogo

    async def pausar(self) -> None:
        """La pausa entre pedidos del job. Vive acá y no en el job para que el ritmo lo fije quien
        conoce el límite de la fuente."""
        await self._dormir(self._pausa)


def _texto(valor: Any) -> str | None:
    """Un texto de la fuente, recortado, o `None` si viene vacío o no es texto."""
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None


def _limpiar_html(bruto: str) -> str:
    """El contenido de una celda sin etiquetas y con las entidades básicas resueltas."""
    sin_tags = re.sub(r"<[^>]+>", "", bruto)
    return (
        sin_tags.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .strip()
    )
