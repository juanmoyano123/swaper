"""Cliente de la SEC para el paquete de estados contables de la ficha de un CEDEAR.

## Por qué existe, y por qué no es lo mismo que `app/externos/sec.py`

`sec.py::ClienteSec` es el cliente del job **batch** de clasificación (`app/renta_variable/
clasificacion.py`): recorre todo el universo una vez, con pausa entre pedidos pensada para no
pasarse del ritmo que tolera la fuente. Éste es otro ciclo de vida — **on-demand, un papel por
ficha abierta**, dos o tres pedidos, sin pausa entre ellos (nunca hay una tanda), con caché propia
de TTL largo (el balance de una empresa no cambia en el día). Mezclar los dos en un mismo cliente
acoplaría un job programado con un request síncrono de la ficha.

Sí se reusa de `sec.py` el `User-Agent` (política pública de la SEC, no un truco) y la base de la
API.

## Alcance: sólo CEDEARs

Por decisión del dueño del producto (14/08/2026): las acciones argentinas dejaron de ser
descubribles desde la UI, y este paquete es sólo para lo que sí queda — `bloque_sec` declara
ausente cualquier ticker cuya clase no sea `cedear`, sin pedirle nada a la SEC.

## Se busca por PAPEL, no por especie

`AALD` (la especie MEP) no existe en el mapa de tickers de la SEC — el que existe es `AAL`. La
ficha ya tiene `especie.emision` resuelto por el agrupamiento (`app/renta_variable/agrupamiento.
py`); acá se usa `emision or ticker`.

## Qué se pide, y qué se arma con eso

1. El mapa completo ticker→CIK (`sec.gov/files/company_tickers.json`) — se cachea entero, TTL
   largo: son ~10.000 filas y volver a bajarlo en cada ficha sería pagar ese costo por cada clic.
2. `submissions/CIK{cik}.json` — de `filings.recent` se arma la lista de documentos: el último
   anual (`10-K` o `20-F`) y hasta tres intermedios (`10-Q` o `6-K`), con la URL construida como
   `sec.gov/Archives/edgar/data/{cik sin ceros}/{accession sin guiones}/{primaryDocument}` —
   patrón confirmado con curl real (200) el 13-14/08/2026.
3. `xbrl/companyfacts/CIK{cik}.json` — se parsea con `sec_ficha_parser.datos_del_ejercicio` y se
   calculan los ratios con `app.renta_variable.ratios_sec.calcular_ratios`.

Nunca lanza: cualquier fallo (sin CIK, companyfacts vacío, timeout, 429) vuelve como un bloque
declarado ausente con su motivo — mismo contrato que `ClienteData912Historico.bloque_historico`.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import structlog

from app.externos.cache import CacheConTTL
from app.externos.sec import BASE_DATOS, BASE_WEB, USER_AGENT
from app.externos.sec_ficha_parser import datos_del_ejercicio
from app.ingesta.http import ErrorDeFuente, Reintentos, con_reintentos, pedir
from app.renta_variable.ratios_sec import RatiosSec, calcular_ratios

logger = structlog.get_logger()

FUENTE = "SEC EDGAR"

URL_TICKERS = f"{BASE_WEB}/files/company_tickers.json"
URL_SUBMISSIONS = f"{BASE_DATOS}/submissions/CIK{{cik:010d}}.json"
URL_COMPANYFACTS = f"{BASE_DATOS}/api/xbrl/companyfacts/CIK{{cik:010d}}.json"
URL_DOCUMENTO = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{documento}"

FORMS_ANUAL = ("10-K", "20-F")
FORMS_INTERMEDIO = ("10-Q", "6-K")
MAX_FILINGS_INTERMEDIOS = 3

TIMEOUT_SEGUNDOS = 8.0
POLITICA = Reintentos(intentos=2, espera_base=1)

# El mapa de tickers es ~10.000 filas y no cambia en el día: TTL largo, una descarga por proceso
# (con margen) en vez de una por ficha. Los datos financieros tampoco cambian en el día: mismo
# criterio que el histórico de data912, TTL de 24 h.
TTL_TICKERS_SEGUNDOS = 24 * 3600.0
TTL_DATOS_SEGUNDOS = 24 * 3600.0
TTL_FALLO_SEGUNDOS = 60.0

MOTIVO_NO_CEDEAR = "no es un CEDEAR: el paquete de estados contables sólo cubre CEDEARs"
MOTIVO_SIN_CIK = "la SEC no lista este papel: no tiene CIK asociado"
MOTIVO_SIN_EJERCICIO = "la SEC no publica un ejercicio con resultado y patrimonio para este papel"


@dataclass(frozen=True, slots=True)
class Filing:
    """Un documento presentado ante la SEC, con el link directo."""

    form: str
    fecha: str
    url_documento: str

    def como_dict(self) -> dict[str, object]:
        return {"form": self.form, "fecha": self.fecha, "url_documento": self.url_documento}


@dataclass(frozen=True, slots=True)
class BloqueSec:
    """El paquete de estados contables de la ficha, disponible o declarado ausente."""

    fuente: str
    disponible: bool
    motivo_ausente: str | None
    solo_anual: bool
    nota_solo_anual: str | None
    cik: str | None
    filings: tuple[Filing, ...]
    ratios: RatiosSec | None

    def como_dict(self) -> dict[str, object]:
        return {
            "fuente": self.fuente,
            "disponible": self.disponible,
            "motivo_ausente": self.motivo_ausente,
            "solo_anual": self.solo_anual,
            "nota_solo_anual": self.nota_solo_anual,
            "cik": self.cik,
            "filings": [f.como_dict() for f in self.filings],
            "ratios": _ratios_como_dict(self.ratios),
        }


def _ratios_como_dict(ratios: RatiosSec | None) -> dict[str, object] | None:
    if ratios is None:
        return None

    def _r(campo: object) -> dict[str, object] | None:
        if campo is None:
            return None
        return {"valor": campo.valor, "unidad": campo.unidad, "periodo": campo.periodo}

    return {
        "roe": _r(ratios.roe),
        "margen_operativo": _r(ratios.margen_operativo),
        "crecimiento_ingresos": _r(ratios.crecimiento_ingresos),
        "eps": _r(ratios.eps),
        "deuda_patrimonio": _r(ratios.deuda_patrimonio),
        "liquidez_corriente": _r(ratios.liquidez_corriente),
    }


NOTA_SOLO_ANUAL = (
    "Esta empresa reporta ante la SEC como emisor privado extranjero: sus estados sólo se "
    "publican con detalle anual, sin trimestral consistente."
)


def _ausente(motivo: str, *, cik: str | None = None) -> BloqueSec:
    return BloqueSec(
        fuente=FUENTE,
        disponible=False,
        motivo_ausente=motivo,
        solo_anual=False,
        nota_solo_anual=None,
        cik=cik,
        filings=(),
        ratios=None,
    )


class ClienteSecFicha:
    """El paquete de estados contables, on-demand por papel. Nunca lanza.

    `dormir` y `reloj` son inyectables para que los tests no esperen de verdad ni dependan del
    reloj de pared.
    """

    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SEGUNDOS,
        politica: Reintentos | None = None,
        dormir: Callable[[float], Any] = asyncio.sleep,
        reloj: Callable[[], float] = time.monotonic,
        ttl_tickers: float = TTL_TICKERS_SEGUNDOS,
        ttl_datos: float = TTL_DATOS_SEGUNDOS,
        ttl_fallo: float = TTL_FALLO_SEGUNDOS,
    ) -> None:
        self._timeout = timeout
        self._politica = politica or POLITICA
        self._dormir = dormir
        self._tickers: CacheConTTL[dict[str, int]] = CacheConTTL(ttl_tickers, reloj)
        self._datos: CacheConTTL[BloqueSec] = CacheConTTL(ttl_datos, reloj)
        self._fallos: CacheConTTL[str] = CacheConTTL(ttl_fallo, reloj)

    async def bloque_sec(self, ticker: str, clase_activo: str, emision: str | None) -> BloqueSec:
        if clase_activo != "cedear":
            return _ausente(MOTIVO_NO_CEDEAR)

        papel = (emision or ticker).strip().upper()

        cacheado = self._datos.obtener(papel)
        if cacheado is not None:
            return cacheado

        fallo = self._fallos.obtener(papel)
        if fallo is not None:
            return _ausente(fallo)

        async with self._abrir() as cliente:
            try:
                mapa = await self._mapa_de_tickers(cliente)
            except ErrorDeFuente as exc:
                motivo = f"{FUENTE} no respondió el mapa de tickers ({exc.motivo})"
                self._fallos.guardar(papel, motivo)
                return _ausente(motivo)

            cik = mapa.get(papel)
            if cik is None:
                self._fallos.guardar(papel, MOTIVO_SIN_CIK)
                return _ausente(MOTIVO_SIN_CIK)
            cik_texto = str(cik)

            try:
                filings = await self._filings(cliente, cik)
                companyfacts = await self._companyfacts(cliente, cik)
            except ErrorDeFuente as exc:
                motivo = f"{FUENTE} no respondió los estados contables ({exc.motivo})"
                self._fallos.guardar(papel, motivo)
                return _ausente(motivo, cik=cik_texto)

        datos = datos_del_ejercicio(companyfacts)
        if datos is None:
            self._fallos.guardar(papel, MOTIVO_SIN_EJERCICIO)
            return _ausente(MOTIVO_SIN_EJERCICIO, cik=cik_texto)

        bloque = BloqueSec(
            fuente=FUENTE,
            disponible=True,
            motivo_ausente=None,
            solo_anual=datos.solo_anual,
            nota_solo_anual=NOTA_SOLO_ANUAL if datos.solo_anual else None,
            cik=cik_texto,
            filings=filings,
            ratios=calcular_ratios(datos),
        )
        self._datos.guardar(papel, bloque)
        return bloque

    async def _mapa_de_tickers(self, cliente: httpx.AsyncClient) -> dict[str, int]:
        cacheado = self._tickers.obtener("mapa")
        if cacheado is not None:
            return cacheado

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", URL_TICKERS, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento,
            descripcion=f"{FUENTE} mapa de tickers",
            politica=self._politica,
            dormir=self._dormir,
        )
        datos = _json(respuesta) or {}
        mapa: dict[str, int] = {}
        if isinstance(datos, dict):
            for fila in datos.values():
                if not isinstance(fila, dict):
                    continue
                ticker = str(fila.get("ticker", "")).strip().upper()
                cik = fila.get("cik_str")
                if ticker and isinstance(cik, int):
                    mapa[ticker] = cik
        self._tickers.guardar("mapa", mapa)
        return mapa

    async def _filings(self, cliente: httpx.AsyncClient, cik: int) -> tuple[Filing, ...]:
        url = URL_SUBMISSIONS.format(cik=cik)

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", url, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento,
            descripcion=f"{FUENTE} submissions",
            politica=self._politica,
            dormir=self._dormir,
        )
        datos = _json(respuesta) or {}
        recientes = datos.get("filings", {}).get("recent", {}) if isinstance(datos, dict) else {}
        forms = recientes.get("form", [])
        fechas = recientes.get("filingDate", [])
        accessions = recientes.get("accessionNumber", [])
        documentos = recientes.get("primaryDocument", [])

        anual: Filing | None = None
        intermedios: list[Filing] = []
        for i, form in enumerate(forms):
            if len(intermedios) >= MAX_FILINGS_INTERMEDIOS and anual is not None:
                break
            if form in FORMS_ANUAL and anual is None:
                anual = _filing_de(form, fechas, accessions, documentos, i, cik)
            elif form in FORMS_INTERMEDIO and len(intermedios) < MAX_FILINGS_INTERMEDIOS:
                filing = _filing_de(form, fechas, accessions, documentos, i, cik)
                if filing is not None:
                    intermedios.append(filing)

        filings = ([anual] if anual is not None else []) + intermedios
        return tuple(filings)

    async def _companyfacts(self, cliente: httpx.AsyncClient, cik: int) -> dict:
        url = URL_COMPANYFACTS.format(cik=cik)

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", url, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento,
            descripcion=f"{FUENTE} companyfacts",
            politica=self._politica,
            dormir=self._dormir,
        )
        datos = _json(respuesta)
        return datos if isinstance(datos, dict) else {}

    def _abrir(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )


def _filing_de(
    form: str, fechas: list[Any], accessions: list[Any], documentos: list[Any], i: int, cik: int
) -> Filing | None:
    if i >= len(fechas) or i >= len(accessions) or i >= len(documentos):
        return None
    fecha = fechas[i]
    accession = accessions[i]
    documento = documentos[i]
    if (
        not isinstance(fecha, str)
        or not isinstance(accession, str)
        or not isinstance(documento, str)
    ):
        return None
    url = URL_DOCUMENTO.format(cik=cik, accession=accession.replace("-", ""), documento=documento)
    return Filing(form=form, fecha=fecha, url_documento=url)


def _json(respuesta: httpx.Response) -> object:
    """El cuerpo como JSON, o `None`. Un cuerpo ilegible es ausencia de dato, no un 500 nuestro."""
    try:
        return respuesta.json()
    except ValueError:
        return None


@lru_cache(maxsize=1)
def cliente_sec_ficha() -> ClienteSecFicha:
    """El cliente compartido por todo el proceso: la caché de TTL sólo sirve si es una sola."""
    return ClienteSecFicha()
