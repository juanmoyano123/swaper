"""Cliente de la SEC para el patrón mensual de presentación de balances de un CEDEAR — F-027.

## Por qué es un cliente aparte de `sec_ficha.py`

`ClienteSecFicha._filings()` corta el recorrido de `filings.recent` apenas junta un anual y tres
intermedios: es lo que necesita la ficha (mostrar los últimos documentos), y tocarlo para que
además sirva acá le agregaría una segunda responsabilidad a un método ya usado en producción.
Éste recorre la lista completa para derivar un patrón, que es un problema distinto.

Se reusa de `sec_ficha.py` el patrón entero: mismo `USER_AGENT`/`BASE_DATOS` (importados de
`sec.py`, nunca redefinidos), mismo `CacheConTTL` de 24 h por papel más caché de fallos de 60 s,
mismo contrato "nunca lanza, degrada con `motivo_ausente` en castellano", y la misma regla de
búsqueda por **papel** (`emision or ticker`), no por especie — `AALD` no existe en el mapa de la
SEC, `AAL` sí.

## Qué formulario cuenta como "presentación de balance"

Un código estándar se lee (regla 11): `10-K` y `10-Q` para filers domésticos, `20-F` y `40-F`
(éste último, el régimen MJDS canadiense) para emisores extranjeros. Las enmiendas (`10-K/A`,
`20-F/A`, ...) no cuentan — re-presentan un balance viejo, su fecha no es patrón.

## Por qué el patrón intermedio no existe para foreign private issuers

Verificado en vivo (16/08/2026) contra Vale: de 840 `6-K` en la ventana, `core_type` vale "6-K"
en 839 de ellos y `isXBRLNumeric` viene en 0 o `None` en todos — la SEC no expone ninguna forma
estructurada de distinguir qué `6-K` trae un estado contable de cuál es un hecho relevante
cualquiera. Clasificarlos por texto sería interpretar, así que quedan **fuera y declarados**:
`solo_anual=True` con su nota, mismo concepto que ya usa la ficha F-053 para el mismo tipo de
emisor.

## Por qué `filings.recent` alcanza y no se pagina

Medido en vivo: para Vale (el caso más ruidoso posible, ~840 `6-K` en la ventana) los 1.000
filings recientes cubren igual los últimos cinco `20-F` (~5 años); para un filer con pocos `6-K`
(Apple) cubren 11 años. `filings.files[]` (los shards con historia más vieja) no se lee — la
ventana efectivamente cubierta se declara en la respuesta (`ventana`), así que no hay ningún
patrón mostrado por fuera de lo que la fuente realmente entregó.

## Persistencia

Ninguna. El contrato del paquete (`app/externos/__init__.py`) es "se consulta en vivo, nunca se
persiste ni se mezcla con nuestro dato" — este cliente lo cumple igual que sus hermanos.
"""

import asyncio
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
import structlog

from app.externos.cache import CacheConTTL
from app.externos.sec import BASE_DATOS, BASE_WEB, USER_AGENT
from app.ingesta.http import ErrorDeFuente, Reintentos, con_reintentos, pedir

logger = structlog.get_logger()

FUENTE = "SEC EDGAR"

URL_TICKERS = f"{BASE_WEB}/files/company_tickers.json"
URL_SUBMISSIONS = f"{BASE_DATOS}/submissions/CIK{{cik:010d}}.json"

# Formularios que declaran un estado contable, por definición del propio formulario — no una
# clasificación nuestra. `40-F` es el régimen MJDS canadiense: anual, mismo rol que `20-F`.
FORMS_ANUAL = ("10-K", "20-F", "40-F")
FORMS_TRIMESTRAL = ("10-Q",)
FORMS_BALANCE = frozenset(FORMS_ANUAL + FORMS_TRIMESTRAL)

TIMEOUT_SEGUNDOS = 8.0
POLITICA = Reintentos(intentos=2, espera_base=1)

# Mismos TTL que `sec_ficha.py`: el mapa de tickers no cambia en el día, y el patrón de
# presentación de una empresa tampoco — cambia a lo sumo una vez por trimestre.
TTL_TICKERS_SEGUNDOS = 24 * 3600.0
TTL_DATOS_SEGUNDOS = 24 * 3600.0
TTL_FALLO_SEGUNDOS = 60.0

MOTIVO_NO_CEDEAR = "no es un CEDEAR: el calendario de balances sólo cubre CEDEARs"
MOTIVO_SIN_CIK = "la SEC no lista este papel: no tiene CIK asociado"
MOTIVO_SIN_PRESENTACIONES = "la SEC no lista presentaciones de balance (10-K/10-Q/20-F/40-F)"

NOTA_SOLO_ANUAL = (
    "Esta empresa reporta ante la SEC como emisor privado extranjero: sólo se detecta el patrón "
    "anual. Presenta además informes 6-K a lo largo del año, pero la SEC no distingue cuáles "
    "traen un estado contable, así que no se clasifican."
)


@dataclass(frozen=True, slots=True)
class MesDeBalance:
    """Un mes del año calendario con al menos una presentación en la ventana medida."""

    mes: int
    """1 = enero .. 12 = diciembre."""
    presentaciones: int
    formularios: tuple[str, ...]
    """Los formularios distintos vistos ese mes, en el orden en que la SEC los lista."""

    def como_dict(self) -> dict[str, object]:
        return {
            "mes": self.mes,
            "presentaciones": self.presentaciones,
            "formularios": list(self.formularios),
        }


@dataclass(frozen=True, slots=True)
class VentanaCalendario:
    """El rango de fechas realmente cubierto por las presentaciones consideradas."""

    desde: str
    hasta: str

    def como_dict(self) -> dict[str, object]:
        return {"desde": self.desde, "hasta": self.hasta}


@dataclass(frozen=True, slots=True)
class CalendarioBalances:
    """El patrón mensual de un papel, disponible o declarado ausente. Nunca una fecha confirmada."""

    papel: str
    fuente: str
    disponible: bool
    motivo_ausente: str | None
    solo_anual: bool
    nota_solo_anual: str | None
    cik: str | None
    ventana: VentanaCalendario | None
    meses: tuple[MesDeBalance, ...]
    capturado_en: str

    def como_dict(self) -> dict[str, object]:
        return {
            "papel": self.papel,
            "fuente": self.fuente,
            "disponible": self.disponible,
            "motivo_ausente": self.motivo_ausente,
            "solo_anual": self.solo_anual,
            "nota_solo_anual": self.nota_solo_anual,
            "cik": self.cik,
            "ventana": self.ventana.como_dict() if self.ventana is not None else None,
            "meses": [m.como_dict() for m in self.meses],
            "capturado_en": self.capturado_en,
        }


def _ausente(
    papel: str, motivo: str, *, cik: str | None = None, capturado_en: str
) -> CalendarioBalances:
    return CalendarioBalances(
        papel=papel,
        fuente=FUENTE,
        disponible=False,
        motivo_ausente=motivo,
        solo_anual=False,
        nota_solo_anual=None,
        cik=cik,
        ventana=None,
        meses=(),
        capturado_en=capturado_en,
    )


class ClienteSecCalendario:
    """El patrón mensual de balances, on-demand por papel. Nunca lanza.

    `dormir`, `reloj` y `ahora` son inyectables para que los tests no esperen de verdad ni
    dependan del reloj de pared.
    """

    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SEGUNDOS,
        politica: Reintentos | None = None,
        dormir: Callable[[float], Any] = asyncio.sleep,
        reloj: Callable[[], float] = time.monotonic,
        ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
        ttl_tickers: float = TTL_TICKERS_SEGUNDOS,
        ttl_datos: float = TTL_DATOS_SEGUNDOS,
        ttl_fallo: float = TTL_FALLO_SEGUNDOS,
    ) -> None:
        self._timeout = timeout
        self._politica = politica or POLITICA
        self._dormir = dormir
        self._ahora = ahora
        self._tickers: CacheConTTL[dict[str, int]] = CacheConTTL(ttl_tickers, reloj)
        self._datos: CacheConTTL[CalendarioBalances] = CacheConTTL(ttl_datos, reloj)
        self._fallos: CacheConTTL[str] = CacheConTTL(ttl_fallo, reloj)

    async def calendario_de(
        self, ticker: str, clase_activo: str, emision: str | None
    ) -> CalendarioBalances:
        if clase_activo != "cedear":
            return _ausente(ticker, MOTIVO_NO_CEDEAR, capturado_en=self._ahora().isoformat())

        papel = (emision or ticker).strip().upper()
        capturado_en = self._ahora().isoformat()

        cacheado = self._datos.obtener(papel)
        if cacheado is not None:
            return cacheado

        fallo = self._fallos.obtener(papel)
        if fallo is not None:
            return _ausente(papel, fallo, capturado_en=capturado_en)

        async with self._abrir() as cliente:
            try:
                mapa = await self._mapa_de_tickers(cliente)
            except ErrorDeFuente as exc:
                motivo = f"{FUENTE} no respondió el mapa de tickers ({exc.motivo})"
                self._fallos.guardar(papel, motivo)
                return _ausente(papel, motivo, capturado_en=capturado_en)

            cik = mapa.get(papel)
            if cik is None:
                self._fallos.guardar(papel, MOTIVO_SIN_CIK)
                return _ausente(papel, MOTIVO_SIN_CIK, capturado_en=capturado_en)
            cik_texto = str(cik)

            try:
                formularios_fechas = await self._presentaciones(cliente, cik)
            except ErrorDeFuente as exc:
                motivo = f"{FUENTE} no respondió el historial de presentaciones ({exc.motivo})"
                self._fallos.guardar(papel, motivo)
                return _ausente(papel, motivo, cik=cik_texto, capturado_en=capturado_en)

        if not formularios_fechas:
            self._fallos.guardar(papel, MOTIVO_SIN_PRESENTACIONES)
            return _ausente(papel, MOTIVO_SIN_PRESENTACIONES, cik=cik_texto, capturado_en=capturado_en)

        calendario = _derivar_calendario(
            papel, formularios_fechas, cik=cik_texto, capturado_en=capturado_en
        )
        self._datos.guardar(papel, calendario)
        return calendario

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

    async def _presentaciones(
        self, cliente: httpx.AsyncClient, cik: int
    ) -> tuple[tuple[str, str], ...]:
        """`(formulario, fecha)` de cada presentación de balance en `filings.recent`, sin cortar.

        A diferencia de `ClienteSecFicha._filings`, recorre la lista entera: acá no interesan los
        documentos más recientes sino el patrón completo que la ventana disponible permite medir.
        """
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

        vistos: list[tuple[str, str]] = []
        for form, fecha in zip(forms, fechas, strict=False):
            if form in FORMS_BALANCE and isinstance(fecha, str) and len(fecha) == 10:
                vistos.append((form, fecha))
        return tuple(vistos)

    def _abrir(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )


def _derivar_calendario(
    papel: str,
    formularios_fechas: tuple[tuple[str, str], ...],
    *,
    cik: str,
    capturado_en: str,
) -> CalendarioBalances:
    por_mes: dict[int, Counter[str]] = {}
    for form, fecha in formularios_fechas:
        mes = int(fecha[5:7])
        por_mes.setdefault(mes, Counter())[form] += 1

    meses = tuple(
        MesDeBalance(
            mes=mes,
            presentaciones=sum(contador.values()),
            formularios=tuple(contador.keys()),
        )
        for mes, contador in sorted(por_mes.items())
    )

    formularios_hallados = {form for form, _ in formularios_fechas}
    solo_anual = formularios_hallados.isdisjoint(FORMS_TRIMESTRAL)

    fechas = sorted(fecha for _, fecha in formularios_fechas)
    ventana = VentanaCalendario(desde=fechas[0], hasta=fechas[-1])

    return CalendarioBalances(
        papel=papel,
        fuente=FUENTE,
        disponible=True,
        motivo_ausente=None,
        solo_anual=solo_anual,
        nota_solo_anual=NOTA_SOLO_ANUAL if solo_anual else None,
        cik=cik,
        ventana=ventana,
        meses=meses,
        capturado_en=capturado_en,
    )


def _json(respuesta: httpx.Response) -> object:
    """El cuerpo como JSON, o `None`. Un cuerpo ilegible es ausencia de dato, no un 500 nuestro."""
    try:
        return respuesta.json()
    except ValueError:
        return None


@lru_cache(maxsize=1)
def cliente_sec_calendario() -> ClienteSecCalendario:
    """El cliente compartido por todo el proceso: la caché de TTL sólo sirve si es una sola."""
    return ClienteSecCalendario()
