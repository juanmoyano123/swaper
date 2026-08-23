"""Cliente de data912 para el histórico de cierres de una acción o un CEDEAR.

## Por qué existe, y por qué no es lo mismo que `app/ingesta/data912/`

`ingesta/data912/` trae la rueda **en vivo** (`/live/...`), entra a la base y se consolida —el
overlay puede pisar el último precio de una especie con lo que trae ese payload. Este módulo es otra
cosa: se consulta **por especie, al hacer clic**, se muestra rotulado con su fuente y su hora, y
**nunca se persiste ni se mezcla con nuestro dato** — mismo contrato que el resto de `app/externos/`
(ver el docstring de `app/externos/__init__.py`).

## Qué cubre la serie

Cubre el 88 % de las acciones argentinas que operan (hasta 23 años de historia) y el 53 % de los
CEDEARs (mediana ~6 años) — medido el 13/08/2026 sobre los papeles de mayor volumen, con una serie
continua (cero saltos diarios mayores al 30 % en 14 años de AAPL; el split 4:1 de Apple de 2020 no
la parte).

## El endpoint, y sus dos formas de decir "no hay serie"

`GET /historical/{tramo}/{ticker}`, con `tramo` según la clase: `stocks` para una acción, `cedears`
para un CEDEAR — **nunca se cruza el tramo**: si BYMA clasifica un papel de una forma y data912 no
lo tiene bajo esa ruta, es un faltante que se declara, no algo que se adivina probando el otro
tramo.

Un ticker que la fuente no tiene responde **HTTP 200** con `{"Error": "..."}` en vez de una lista —
verificado en vivo el 13/08/2026, tanto para un ticker inexistente como para el tramo cruzado. Por
eso `bloque_historico` nunca deja que `pedir()` trate esto como fallo reintentable: HTTP 200 no es
un error de la fuente, es la fuente contestando que no tiene el dato. Una lista vacía se trata
igual.

## Qué se lee de cada barra, y qué no

Cada barra trae `{date, o, h, l, c, v, dr, sa}`. Sólo se leen `date` (ya viene en ISO) y `c`
(cierre): `dr` y `sa` no están documentados por la fuente, y mostrar un número sin saber qué
significa sería inventarle una interpretación (regla 11). `o`, `h`, `l`, `v` no hacen falta para el
sparkline de cierres — si algún día hace falta el resto del OHLC, se suma explícitamente.

La fuente no declara la moneda de la serie: el bloque no lleva ese campo, y quien lo muestre tiene
que decirlo en la leyenda en vez de heredar la moneda de la especie (podría no ser la misma).
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Any

import httpx
import structlog

from app.externos.cache import CacheConTTL
from app.ingesta.http import ErrorDeFuente, Reintentos, con_reintentos, crear_cliente, pedir

logger = structlog.get_logger()

FUENTE = "data912"

BASE_URL = "https://data912.com"
URL_HISTORICO = "{base}/historical/{tramo}/{ticker}"

# `cedear` es la clase que ya usa el resto del backend (`EspecieRentaVariable.clase_activo`);
# `stocks`/`cedears` son los nombres de tramo que publica data912. No hay tercera opción: una
# especie que no sea ninguna de las dos clases (no debería llegar acá) no tiene tramo que probar.
TRAMO_POR_CLASE: dict[str, str] = {"accion": "stocks", "cedear": "cedears"}

DIAS_DE_SERIE = 366

TIMEOUT_SEGUNDOS = 8.0
POLITICA = Reintentos(intentos=2, espera_base=1)

# Es una serie de cierres diarios, no un precio vivo: no hace falta refrescarla en cada clic.
TTL_SERIE_SEGUNDOS = 3600.0
TTL_FALLO_SEGUNDOS = 60.0

MOTIVO_SIN_TRAMO = "esta especie no es una acción ni un CEDEAR: no hay tramo de data912 que pedir"


@dataclass(frozen=True, slots=True)
class PuntoHistorico:
    """Un cierre diario de la serie. `fecha` en ISO, `cierre` en la moneda que declara la fuente."""

    fecha: str
    cierre: float

    def como_dict(self) -> dict[str, object]:
        return {"fecha": self.fecha, "cierre": self.cierre}


@dataclass(frozen=True, slots=True)
class BloqueHistorico:
    """El histórico de cierres para el panel de la ficha, disponible o declarado ausente."""

    fuente: str
    disponible: bool
    motivo: str | None
    puntos: tuple[PuntoHistorico, ...]

    def como_dict(self) -> dict[str, object]:
        return {
            "fuente": self.fuente,
            "disponible": self.disponible,
            "motivo": self.motivo,
            "puntos": [p.como_dict() for p in self.puntos],
        }


def _sin_serie(motivo: str) -> BloqueHistorico:
    return BloqueHistorico(fuente=FUENTE, disponible=False, motivo=motivo, puntos=())


def _json(respuesta: httpx.Response) -> object:
    """El cuerpo como JSON, o `None`. Un cuerpo ilegible es ausencia de dato, no un 500 nuestro."""
    try:
        return respuesta.json()
    except ValueError:
        return None


def _puntos_de(crudo: object, *, desde: date) -> tuple[PuntoHistorico, ...]:
    """Las barras válidas del último año, ordenadas por fecha. `crudo` no es una lista cuando la
    fuente no tiene el ticker (`{"Error": ...}` con HTTP 200) — eso no es un punto, es cero
    puntos."""
    if not isinstance(crudo, list):
        return ()

    puntos: list[PuntoHistorico] = []
    for barra in crudo:
        if not isinstance(barra, dict):
            continue
        fecha_cruda = barra.get("date")
        cierre_crudo = barra.get("c")
        if not isinstance(fecha_cruda, str) or not isinstance(cierre_crudo, (int, float)):
            continue
        try:
            fecha = date.fromisoformat(fecha_cruda)
        except ValueError:
            continue
        if fecha < desde:
            continue
        puntos.append(PuntoHistorico(fecha=fecha_cruda, cierre=float(cierre_crudo)))

    puntos.sort(key=lambda p: p.fecha)
    return tuple(puntos)


class ClienteData912Historico:
    """El histórico de cierres, por ticker y por clase. Nunca lanza: todo fallo vuelve declarado.

    `dormir` y `ahora` son inyectables para que los tests no esperen de verdad ni dependan del
    reloj de pared.
    """

    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SEGUNDOS,
        politica: Reintentos | None = None,
        dormir: Callable[[float], Any] = asyncio.sleep,
        ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
        ttl_serie: float = TTL_SERIE_SEGUNDOS,
        ttl_fallo: float = TTL_FALLO_SEGUNDOS,
        reloj: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout = timeout
        self._politica = politica or POLITICA
        self._dormir = dormir
        self._ahora = ahora
        self._serie: CacheConTTL[tuple[PuntoHistorico, ...]] = CacheConTTL(ttl_serie, reloj)
        self._fallos: CacheConTTL[str] = CacheConTTL(ttl_fallo, reloj)

    async def bloque_historico(self, ticker: str, clase_activo: str) -> BloqueHistorico:
        tramo = TRAMO_POR_CLASE.get(clase_activo)
        if tramo is None:
            return _sin_serie(MOTIVO_SIN_TRAMO)

        clave = f"{tramo}:{ticker.strip().upper()}"

        puntos = self._serie.obtener(clave)
        if puntos is not None:
            return BloqueHistorico(fuente=FUENTE, disponible=True, motivo=None, puntos=puntos)

        fallo = self._fallos.obtener(clave)
        if fallo is not None:
            return _sin_serie(fallo)

        url = URL_HISTORICO.format(base=BASE_URL, tramo=tramo, ticker=ticker.strip().upper())

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", url, fuente=FUENTE)

        async with crear_cliente(timeout=self._timeout) as cliente:
            try:
                respuesta = await con_reintentos(
                    intento,
                    descripcion=f"{FUENTE} histórico ({tramo})",
                    politica=self._politica,
                    dormir=self._dormir,
                )
            except ErrorDeFuente as exc:
                logger.info(
                    "data912_historico_sin_respuesta", ticker=ticker, tramo=tramo, motivo=exc.motivo
                )
                motivo = f"{FUENTE} no respondió el histórico de {ticker} ({exc.motivo})"
                self._fallos.guardar(clave, motivo)
                return _sin_serie(motivo)

        desde = self._ahora().date() - timedelta(days=DIAS_DE_SERIE)
        puntos = _puntos_de(_json(respuesta), desde=desde)

        if not puntos:
            motivo = f"{FUENTE} no publica serie histórica para {ticker} en historical/{tramo}"
            self._fallos.guardar(clave, motivo)
            return _sin_serie(motivo)

        self._serie.guardar(clave, puntos)
        return BloqueHistorico(fuente=FUENTE, disponible=True, motivo=None, puntos=puntos)


@lru_cache(maxsize=1)
def cliente_data912_historico() -> ClienteData912Historico:
    """El cliente compartido por todo el proceso: la caché de TTL sólo sirve si es una sola."""
    return ClienteData912Historico()
