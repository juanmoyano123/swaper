"""La ficha técnica de una especie en BYMA — de dónde sale el emisor que el universo no tiene.

`public.instrumentos` tiene 4.761 filas y sólo 742 con emisor (medido el 28/08/2026). El emisor
venía de dos lados y los dos se apagaron: el CSV curado de F-009 (823 tickers, sin fuente viva) y
IAMC, cuya ingesta se eliminó el 26/08/2026. Un instrumento sin emisor no se puede analizar, así
que hacía falta una fuente viva, y ésta lo es.

## El pedido

`POST .../bnown/fichatecnica/especies/general` con `{"symbol": "YMCXO"}`. **Sin token, sin cookie y
con `verify=True`** — a diferencia de los paneles de cotizaciones del mismo host, que sí necesitan
saltear la verificación del certificado. Responde `{"content":{...},"data":[{...}],"empty":bool}` y
el objeto útil es `data[0]`.

**No hay modo bulk.** Probados el 28/08/2026 `{}`, `page_size:5000`, `symbol:""`, `"%"`, `"*"`,
listas y CSV: todos devuelven vacío. Es un POST por símbolo, ~80 ms, sin límite de ritmo visible
con concurrencia 8-10.

## Qué se lee y qué no

Sólo cuatro campos: emisor, ley, denominación y el ticker que se preguntó. La ficha trae más
—ISIN, garantía, montos nominal y residual, fechas, los textos de interés y amortización—, y
quedan **deliberadamente afuera**: cada uno necesita su propia verificación contra la fuente antes
de mostrarse, y traerlos "ya que estamos" es cómo un dato sin verificar termina en pantalla.

**La ley viaja cruda.** La ficha declara `'Nacional'`, `'Extranjera'` o vacío, que no es el
vocabulario de la columna `law`. Traducir es decisión de quien escribe en la base —está en
`app/instrumentos/emisores.py`, con la evidencia medida—, no de este cliente: acá se transporta lo
que la fuente dijo, tal cual (regla 11).

## Un `data` vacío no es un fallo

`pedir()` puede tratar el vacío como error reintentable, y para los paneles de cotizaciones lo es
—inestabilidad medida—. Acá **no**: la fuente simplemente no tiene ficha de esa especie, y es un
resultado normal y estable (las opciones no tienen ninguna, y TY36O tampoco). Reintentar cinco
veces cada símbolo sin ficha multiplicaría por cinco el barrido para llegar a la misma respuesta.
Ese caso devuelve `None`, que es distinto de "no se pudo preguntar": un símbolo que falló **no
aparece en el dict** de `traer_fichas`, para que quien escriba no lo marque como preguntado.
"""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.ingesta.http import ErrorDeFuente, con_reintentos, crear_cliente, pedir

logger = structlog.get_logger()

FUENTE = "BYMA ficha técnica"

URL_FICHA = (
    "https://open.bymadata.com.ar/vanoms-be-core/rest/api/bymadata/free"
    "/bnown/fichatecnica/especies/general"
)

# Mismo criterio que `app/externos/sec.py`: quien consulta se identifica con el contacto real del
# dueño del producto. BYMA no lo exige —el endpoint responde sin headers—, y se manda igual: es la
# forma de que, si el volumen les molesta, sepan a quién escribirle en vez de bloquear a ciegas.
USER_AGENT = "10-Swaper (asesor ALyC Argentina) moyanojjeronimo@gmail.com"

TIMEOUT_SEGUNDOS = 30.0

# Concurrencia por defecto del barrido. Medido el 28/08/2026: con 8-10 pedidos en vuelo la fuente
# responde a ~80 ms sin devolver un solo 429. Se deja en 8 y no en 10 porque el barrido es
# incremental y no tiene apuro; quedarse corto no cuesta nada.
CONCURRENCIA_POR_DEFECTO = 8


@dataclass(frozen=True, slots=True)
class FichaEspecie:
    """Lo que la ficha declara de una especie. Cada campo puede faltar y ninguno se completa."""

    ticker: str
    emisor: str | None
    ley_cruda: str | None
    """La ley **tal cual la escribe la fuente** (`'Nacional'`, `'Extranjera'`). El cliente no
    traduce: el vocabulario de la columna `law` es otro y el mapeo vive donde está su evidencia."""
    denominacion: str | None


async def traer_ficha(
    cliente: httpx.AsyncClient,
    symbol: str,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> FichaEspecie | None:
    """La ficha de un símbolo. `None` = la fuente no tiene ficha para éste.

    Un fallo de red o un HTTP de error **se propaga** como `ErrorDeFuente` después de los
    reintentos. La diferencia con `None` es la que separa "BYMA no lo publica" de "BYMA no
    contestó", y borrarla haría que un corte de red se persistiera como un faltante definitivo.

    `dormir` es inyectable para que los tests no esperen de verdad los 30 segundos de la escalera
    de reintentos.
    """

    async def intento() -> httpx.Response:
        return await pedir(cliente, "POST", URL_FICHA, fuente=FUENTE, json={"symbol": symbol})

    respuesta = await con_reintentos(intento, descripcion=f"{FUENTE} ({symbol})", dormir=dormir)
    try:
        cuerpo = respuesta.json()
    except ValueError:
        # La fuente contestó 200 con algo que no es JSON. No se adivina qué quiso decir.
        logger.warning("byma_ficha_respuesta_no_json", symbol=symbol)
        return None

    filas = cuerpo.get("data") if isinstance(cuerpo, dict) else None
    if not filas or not isinstance(filas[0], dict):
        return None
    return _normalizar(symbol, filas[0])


async def traer_fichas(
    symbols: Iterable[str],
    *,
    concurrencia: int = CONCURRENCIA_POR_DEFECTO,
    cliente: httpx.AsyncClient | None = None,
    timeout: float = TIMEOUT_SEGUNDOS,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, FichaEspecie | None]:
    """Las fichas de una tanda de símbolos, en paralelo acotado.

    Tres resultados distintos y hay que poder separarlos:

    - `{symbol: FichaEspecie}` — la fuente la publica.
    - `{symbol: None}` — la fuente contestó y no tiene ficha de esa especie.
    - **el símbolo no está en el dict** — no se pudo preguntar (la fuente falló). Quien escriba no
      tiene que marcarlo como consultado, porque no lo fue.
    """
    simbolos = list(symbols)
    if not simbolos:
        return {}

    semaforo = asyncio.Semaphore(concurrencia)
    propio = cliente is None
    cliente = cliente or crear_cliente(timeout=timeout, headers={"User-Agent": USER_AGENT})

    async def una(symbol: str) -> tuple[str, FichaEspecie | None] | None:
        async with semaforo:
            try:
                return symbol, await traer_ficha(cliente, symbol, dormir=dormir)
            except ErrorDeFuente as exc:
                logger.warning("byma_ficha_sin_respuesta", symbol=symbol, motivo=exc.motivo)
                return None

    try:
        resultados = await asyncio.gather(*(una(s) for s in simbolos))
    finally:
        if propio:
            await cliente.aclose()

    return {symbol: ficha for symbol, ficha in (r for r in resultados if r is not None)}


def _normalizar(symbol: str, fila: dict[str, Any]) -> FichaEspecie:
    return FichaEspecie(
        ticker=symbol,
        emisor=_texto(fila.get("emisor")),
        ley_cruda=_texto(fila.get("ley")),
        denominacion=_texto(fila.get("denominacion")),
    )


def _texto(valor: Any) -> str | None:
    """El texto de la fuente, recortado, o `None` si viene vacío.

    La ficha usa la cadena vacía —no `null`— para lo que no declara: `ley` vale `''` en 587 de las
    692 especies medidas el 28/08/2026. Las dos cosas significan lo mismo para el asesor, y hacia
    adentro conviene que sean un solo valor: `None`.
    """
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None
