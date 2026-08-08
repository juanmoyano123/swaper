"""Cliente de Yahoo Finance para la ficha de renta variable — F-053.

QUÉ ES ESTO, PARA EL QUE LO LEA EN SEIS MESES
---------------------------------------------
Yahoo Finance **no publica una API**. Los tres endpoints que usa este módulo son los que consume su
propio sitio web: no tienen documentación, no tienen contrato y no hay nadie a quien reclamarle si
cambian. Ya cambiaron una vez —en 2023 Yahoo cerró el acceso anónimo a los datos de perfil y lo puso
detrás de un mecanismo de cookie+crumb— y pueden volver a cambiar cualquier día, sin aviso.

Todo lo que sigue está verificado en vivo el 08/08/2026, y está escrito para que el día que se rompa
no se rompa **ninguna pantalla nuestra**: la ficha degrada de a niveles y declara qué le falta.

**Nivel 1 — cotización e histórico, sin autenticación.**
    GET /v8/finance/chart/{SIMBOLO}?range=1y&interval=1d
Devuelve `chart.result[0].meta` (moneda, bolsa, nombre de la empresa, precio, máximos y mínimos del
día y de 52 semanas, volumen, cierre previo) más la serie diaria en `timestamp` +
`indicators.quote[0].close`.

**Nivel 2 — perfil de la empresa, con cookie y crumb.**
    1. GET https://fc.yahoo.com con User-Agent de browser → deja las cookies (su status **no
       importa**: contesta 404 y las cookies vienen igual; por eso este paso no pasa por `pedir`).
    2. GET /v1/test/getcrumb con esas cookies → devuelve el crumb en texto plano.
    3. GET /v10/finance/quoteSummary/{SIMBOLO}?modules=assetProfile&crumb={CRUMB}
Sin cookie+crumb el paso 3 responde 401. Si cualquiera de los tres falla, el nivel 2 queda vacío y
declarado, y el nivel 1 sigue en pie.

**Y hay un tercer modo de fallo, medido acá mismo el 08/08/2026: HTTP 429.** Después de un rato de
consultas, Yahoo empezó a limitar **toda esta conexión** —`curl` sin nuestro código recibe el mismo
429, en `query1` y en `query2`, y hasta el endpoint del crumb—. No es una credencial vencida ni un
símbolo mal armado: es cuota. Por eso un fallo se anota por un minuto (`TTL_FALLO_SEGUNDOS`) y no se
insiste una vez por clic, y por eso el 429 se dice en castellano en la ficha en vez de mostrarse
como un número. Cuando la fuente deja de limitar, el bloque externo vuelve solo.

EL SÍMBOLO NO SE DERIVA
-----------------------
La consulta es siempre `{ticker}.BA` con el ticker que ya tenemos de BYMA, y nada más. Verificado:
`MSFT.BA` en Yahoo **es el CEDEAR** —`currency: ARS`, `exchangeName: BUE`, precio en pesos— y su
perfil es el de Microsoft. No hay que mapear el CEDEAR a su subyacente ni cortar el ticker por
ningún lado: derivar tickers cortando strings es el error que en este proyecto ya costó revertir 121
tickers inexistentes (regla 1 del dominio).

El sufijo `.BA` es la convención pública de Yahoo para Buenos Aires, no una inferencia sobre el
instrumento; y de todos modos la respuesta se verifica: **se acepta sólo si declara la bolsa `BUE` y
el mismo símbolo que se pidió**. Cualquier otra cosa deja el bloque externo vacío y declarado, nunca
mostrando el dato de otro instrumento (regla 11).

LO QUE NO SE TRAE, Y NO ES NEGOCIABLE
-------------------------------------
Yahoo publica recomendación de analistas (`recommendationKey`), precio objetivo (`targetMeanPrice`)
y cantidad de opiniones. Eso es juicio de terceros, no dato duro, y la **regla 6** del dominio
mantiene el análisis determinístico. No se traen: los módulos `financialData` y
`recommendationTrend` ni siquiera se piden, y los objetos de este módulo se arman campo por campo
desde una lista explícita, así que un campo nuevo de la fuente no puede colarse a la respuesta.

Los valores propietarios de Yahoo —"Financial Services", "Banks - Regional", "United States"— se
guardan y se muestran **tal como la fuente los declara**, sin traducir (regla 11). Traducirlos sería
poner nuestra interpretación en el lugar del dato.
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx
import structlog

from app.ingesta.http import ErrorDeFuente, Reintentos, con_reintentos, pedir

logger = structlog.get_logger()

FUENTE = "Yahoo Finance"

URL_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{simbolo}"
URL_COOKIE = "https://fc.yahoo.com"
URL_CRUMB = "https://query1.finance.yahoo.com/v1/test/getcrumb"
URL_PERFIL = "https://query1.finance.yahoo.com/v10/finance/quoteSummary/{simbolo}"

# El único módulo que se pide. Todo lo que no está acá no viaja: ver "LO QUE NO SE TRAE".
MODULOS_PERFIL = "assetProfile"

SUFIJO_BUENOS_AIRES = ".BA"
BOLSA_ESPERADA = "BUE"

RANGO_HISTORICO = "1y"
INTERVALO_HISTORICO = "1d"

# Yahoo responde 429 o directamente nada a un cliente que no se identifica como browser. No es una
# evasión de nada: es el mismo pedido que hace su sitio, con el mismo encabezado.
AGENTE = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

# Timeout corto y dos intentos, al revés que la ingesta nocturna (90 s y cinco intentos): esto
# cuelga de un clic del asesor. Una fuente lenta acá no puede convertirse en una ficha que no abre;
# es preferible declarar el bloque externo no disponible y seguir mostrando lo nuestro.
TIMEOUT_SEGUNDOS = 8.0
POLITICA = Reintentos(intentos=2, espera_base=1)

# La tabla del monitor tiene cientos de filas y cada clic abre una ficha: sin caché, cada ida y
# vuelta sería un pedido a Yahoo. El precio se mueve con la rueda; el perfil de la empresa no cambia
# en el día.
TTL_COTIZACION_SEGUNDOS = 300.0
TTL_PERFIL_SEGUNDOS = 86_400.0

# Un fallo también se recuerda, y por poco tiempo: ver `ClienteYahoo._recordar_fallo`.
TTL_FALLO_SEGUNDOS = 60.0

# Los dos fallos que el asesor va a ver de verdad, dichos en castellano. El resto viaja con el
# motivo técnico: es preferible un "HTTP 502" en pantalla a una frase amable que no dice qué pasó.
MOTIVOS_POR_STATUS: dict[int, str] = {
    404: "no publica este símbolo",
    429: (
        "está limitando los pedidos desde esta conexión (HTTP 429): el bloque externo vuelve "
        "solo cuando la fuente deje de limitarnos"
    ),
}


# --- Lo que se muestra ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PuntoHistorico:
    """Un cierre diario de la serie. `fecha` en ISO, `cierre` en la moneda que declara la fuente."""

    fecha: str
    cierre: float

    def como_dict(self) -> dict[str, object]:
        return {"fecha": self.fecha, "cierre": self.cierre}


@dataclass(frozen=True, slots=True)
class CotizacionExterna:
    """El nivel 1: lo que Yahoo publica del papel, con la hora en que se lo capturó.

    Nada de esto reemplaza nuestro precio: es el mismo instrumento visto por otra fuente, y se
    muestra rotulado como tal. Sin campo derivado ni calculado — lo que viaja es lo que vino.
    """

    simbolo: str
    bolsa: str
    bolsa_nombre: str | None
    moneda: str | None
    nombre_largo: str | None
    nombre_corto: str | None
    tipo_instrumento: str | None
    precio: float | None
    cierre_previo: float | None
    maximo_dia: float | None
    minimo_dia: float | None
    maximo_52_semanas: float | None
    minimo_52_semanas: float | None
    volumen: float | None
    historico: tuple[PuntoHistorico, ...]
    capturado_en: str

    def como_dict(self) -> dict[str, object]:
        return {
            "simbolo": self.simbolo,
            "bolsa": self.bolsa,
            "bolsa_nombre": self.bolsa_nombre,
            "moneda": self.moneda,
            "nombre_largo": self.nombre_largo,
            "nombre_corto": self.nombre_corto,
            "tipo_instrumento": self.tipo_instrumento,
            "precio": self.precio,
            "cierre_previo": self.cierre_previo,
            "maximo_dia": self.maximo_dia,
            "minimo_dia": self.minimo_dia,
            "maximo_52_semanas": self.maximo_52_semanas,
            "minimo_52_semanas": self.minimo_52_semanas,
            "volumen": self.volumen,
            "historico": [p.como_dict() for p in self.historico],
            "capturado_en": self.capturado_en,
        }


@dataclass(frozen=True, slots=True)
class PerfilExterno:
    """El nivel 2: quién es la empresa, en el vocabulario de Yahoo y sin traducir (regla 11)."""

    pais: str | None
    sector: str | None
    industria: str | None
    sitio: str | None
    empleados: int | None
    capturado_en: str

    def como_dict(self) -> dict[str, object]:
        return {
            "pais": self.pais,
            "sector": self.sector,
            "industria": self.industria,
            "sitio": self.sitio,
            "empleados": self.empleados,
            "capturado_en": self.capturado_en,
        }


@dataclass(frozen=True, slots=True)
class BloqueExterno:
    """El bloque de terceros de la ficha, disponible o declarado ausente — nunca a medias.

    `disponible` es del bloque entero (nivel 1). `perfil_motivo` es el matiz del nivel 2: hay
    cotización pero no perfil, que es exactamente lo que pasa cuando el crumb se rompe.
    """

    fuente: str
    simbolo_consultado: str
    disponible: bool
    motivo: str | None
    cotizacion: CotizacionExterna | None
    perfil: PerfilExterno | None
    perfil_motivo: str | None

    def como_dict(self) -> dict[str, object]:
        return {
            "fuente": self.fuente,
            "simbolo_consultado": self.simbolo_consultado,
            "disponible": self.disponible,
            "motivo": self.motivo,
            "cotizacion": self.cotizacion.como_dict() if self.cotizacion is not None else None,
            "perfil": self.perfil.como_dict() if self.perfil is not None else None,
            "perfil_motivo": self.perfil_motivo,
        }


def _no_disponible(simbolo: str, motivo: str) -> BloqueExterno:
    return BloqueExterno(
        fuente=FUENTE,
        simbolo_consultado=simbolo,
        disponible=False,
        motivo=motivo,
        cotizacion=None,
        perfil=None,
        perfil_motivo=None,
    )


# --- Lectura de la respuesta ----------------------------------------------------------------------


def _texto(valor: object) -> str | None:
    """Un texto de la fuente, recortado, o `None`. Nunca se traduce ni se normaliza el contenido."""
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _numero(valor: object) -> float | None:
    """Un número de la fuente, o `None`. `bool` no es número acá, y `NaN` es ausencia de dato."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        return None
    numero = float(valor)
    return None if numero != numero else numero


def _entero(valor: object) -> int | None:
    numero = _numero(valor)
    return None if numero is None else int(numero)


def _serie(resultado: dict[str, Any], desfase_horario: int) -> tuple[PuntoHistorico, ...]:
    """La serie diaria, saltando los días sin cierre publicado.

    El epoch de cada punto es la apertura de la rueda en el huso de la bolsa; se le suma el
    `gmtoffset` que la propia respuesta declara antes de sacarle la fecha, porque leerlo en UTC
    corre un día los cierres de las ruedas de la tarde.
    """
    marcas = resultado.get("timestamp")
    indicadores = resultado.get("indicators")
    if not isinstance(marcas, list) or not isinstance(indicadores, dict):
        return ()

    cotizaciones = indicadores.get("quote")
    if not isinstance(cotizaciones, list) or not cotizaciones:
        return ()
    primera = cotizaciones[0]
    cierres = primera.get("close") if isinstance(primera, dict) else None
    if not isinstance(cierres, list):
        return ()

    puntos: list[PuntoHistorico] = []
    for marca, cierre in zip(marcas, cierres, strict=False):
        epoch = _numero(marca)
        valor = _numero(cierre)
        if epoch is None or valor is None:
            continue
        fecha = datetime.fromtimestamp(epoch + desfase_horario, UTC).date()
        puntos.append(PuntoHistorico(fecha=fecha.isoformat(), cierre=valor))
    return tuple(puntos)


def leer_cotizacion(cuerpo: object, *, simbolo: str, capturado_en: str) -> CotizacionExterna | None:
    """La cotización de la respuesta del chart, o `None` si no es del instrumento que se pidió.

    Los dos guardias son la regla 11 puesta en código: la respuesta tiene que declarar la bolsa
    `BUE` y el mismo símbolo consultado. Yahoo resuelve símbolos parecidos por su cuenta, y una
    ficha que mostrara el papel de otro mercado con nuestro ticker en el título sería exactamente
    el dato inventado que el proyecto no admite.
    """
    if not isinstance(cuerpo, dict):
        return None
    chart = cuerpo.get("chart")
    resultados = chart.get("result") if isinstance(chart, dict) else None
    if not isinstance(resultados, list) or not resultados:
        return None
    resultado = resultados[0]
    if not isinstance(resultado, dict):
        return None
    meta = resultado.get("meta")
    if not isinstance(meta, dict):
        return None

    bolsa = _texto(meta.get("exchangeName"))
    devuelto = _texto(meta.get("symbol"))
    if bolsa is None or bolsa.upper() != BOLSA_ESPERADA:
        return None
    if devuelto is None or devuelto.upper() != simbolo.upper():
        return None

    desfase = _entero(meta.get("gmtoffset")) or 0
    return CotizacionExterna(
        simbolo=devuelto,
        bolsa=bolsa,
        bolsa_nombre=_texto(meta.get("fullExchangeName")),
        moneda=_texto(meta.get("currency")),
        nombre_largo=_texto(meta.get("longName")),
        nombre_corto=_texto(meta.get("shortName")),
        tipo_instrumento=_texto(meta.get("instrumentType")),
        precio=_numero(meta.get("regularMarketPrice")),
        cierre_previo=_numero(meta.get("chartPreviousClose")),
        maximo_dia=_numero(meta.get("regularMarketDayHigh")),
        minimo_dia=_numero(meta.get("regularMarketDayLow")),
        maximo_52_semanas=_numero(meta.get("fiftyTwoWeekHigh")),
        minimo_52_semanas=_numero(meta.get("fiftyTwoWeekLow")),
        volumen=_numero(meta.get("regularMarketVolume")),
        historico=_serie(resultado, desfase),
        capturado_en=capturado_en,
    )


def leer_perfil(cuerpo: object, *, capturado_en: str) -> PerfilExterno | None:
    """El perfil de `assetProfile`, campo por campo desde una lista explícita.

    Que los campos se nombren uno por uno y no se copie el objeto entero es lo que hace
    estructuralmente imposible que un campo de opinión —que Yahoo podría empezar a devolver acá
    mañana— llegue a la respuesta de nuestra API.
    """
    if not isinstance(cuerpo, dict):
        return None
    resumen = cuerpo.get("quoteSummary")
    resultados = resumen.get("result") if isinstance(resumen, dict) else None
    if not isinstance(resultados, list) or not resultados:
        return None
    primero = resultados[0]
    perfil = primero.get("assetProfile") if isinstance(primero, dict) else None
    if not isinstance(perfil, dict):
        return None

    return PerfilExterno(
        pais=_texto(perfil.get("country")),
        sector=_texto(perfil.get("sector")),
        industria=_texto(perfil.get("industry")),
        sitio=_texto(perfil.get("website")),
        empleados=_entero(perfil.get("fullTimeEmployees")),
        capturado_en=capturado_en,
    )


# --- Caché ----------------------------------------------------------------------------------------


class CacheConTTL[T]:
    """Caché en memoria con vencimiento. Sin tope de tamaño a propósito.

    Las claves son tickers del universo del día: unos pocos miles como mucho, y las entradas
    vencidas se pisan solas. Un LRU acá sería complejidad sin problema que resolver.
    """

    def __init__(self, ttl: float, reloj: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl
        self._reloj = reloj
        self._entradas: dict[str, tuple[float, T]] = {}

    def obtener(self, clave: str) -> T | None:
        entrada = self._entradas.get(clave)
        if entrada is None:
            return None
        vence_en, valor = entrada
        if self._reloj() >= vence_en:
            del self._entradas[clave]
            return None
        return valor

    def guardar(self, clave: str, valor: T) -> None:
        self._entradas[clave] = (self._reloj() + self._ttl, valor)


# --- El cliente -----------------------------------------------------------------------------------


class ClienteYahoo:
    """Los dos niveles, cada uno degradando por su cuenta y ninguno capaz de tumbar una pantalla.

    `dormir`, `reloj` y `ahora` son inyectables para que los tests no esperen de verdad ni dependan
    del reloj de pared.
    """

    def __init__(
        self,
        *,
        timeout: float = TIMEOUT_SEGUNDOS,
        politica: Reintentos | None = None,
        dormir: Callable[[float], Any] = asyncio.sleep,
        reloj: Callable[[], float] = time.monotonic,
        ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
        ttl_cotizacion: float = TTL_COTIZACION_SEGUNDOS,
        ttl_perfil: float = TTL_PERFIL_SEGUNDOS,
        ttl_fallo: float = TTL_FALLO_SEGUNDOS,
    ) -> None:
        self._timeout = timeout
        self._politica = politica or POLITICA
        self._dormir = dormir
        self._ahora = ahora
        self._cotizaciones: CacheConTTL[CotizacionExterna] = CacheConTTL(ttl_cotizacion, reloj)
        self._perfiles: CacheConTTL[PerfilExterno] = CacheConTTL(ttl_perfil, reloj)
        # El crumb vence junto con el perfil: es la credencial con la que se lo pide, y renovarla
        # más seguido que el dato que habilita sería pagar dos requests para nada.
        self._credenciales: CacheConTTL[tuple[str, httpx.Cookies]] = CacheConTTL(ttl_perfil, reloj)
        self._fallos: CacheConTTL[str] = CacheConTTL(ttl_fallo, reloj)

    def simbolo_de(self, ticker: str) -> str:
        """`GGAL` → `GGAL.BA`. El único armado que se hace, y la respuesta se verifica después."""
        return f"{ticker.strip().upper()}{SUFIJO_BUENOS_AIRES}"

    def _recordar_fallo(self, clave: str, exc: ErrorDeFuente) -> str:
        """Anota el fallo por un rato y devuelve el motivo tal como lo va a leer el asesor.

        La anotación es lo que evita que una fuente que nos está cortando el paso reciba un pedido
        por cada clic: verificado el 08/08/2026, Yahoo responde **429 a toda esta IP** —también a
        `curl`, así que no es nuestro cliente— y sin esto cada ficha abierta pagaría el timeout de
        vuelta y empujaría el límite un poco más. El minuto es corto a propósito: es la diferencia
        entre no insistir y quedarse mostrando "no disponible" después de que la fuente se recuperó.
        """
        motivo = MOTIVOS_POR_STATUS.get(exc.status or 0)
        texto = (
            f"{FUENTE} {motivo}"
            if motivo is not None
            else f"{FUENTE} no respondió la cotización: {exc.motivo}"
        )
        self._fallos.guardar(clave, texto)
        return texto

    async def bloque_externo(self, ticker: str) -> BloqueExterno:
        """El bloque de Yahoo para un ticker de BYMA. Nunca lanza: todo fallo vuelve declarado."""
        simbolo = self.simbolo_de(ticker)
        clave = simbolo.upper()

        cotizacion = self._cotizaciones.obtener(clave)
        perfil = self._perfiles.obtener(clave)
        if cotizacion is not None and perfil is not None:
            return BloqueExterno(FUENTE, simbolo, True, None, cotizacion, perfil, None)

        if cotizacion is None:
            fallo = self._fallos.obtener(clave)
            if fallo is not None:
                return _no_disponible(simbolo, fallo)

        async with self._abrir() as cliente:
            if cotizacion is None:
                try:
                    cotizacion = await self._cotizacion(cliente, simbolo)
                except ErrorDeFuente as exc:
                    logger.info("yahoo_sin_cotizacion", simbolo=simbolo, motivo=exc.motivo)
                    return _no_disponible(simbolo, self._recordar_fallo(clave, exc))
                if cotizacion is None:
                    # También se anota: que la fuente conteste por otro instrumento es estable, y
                    # volver a preguntárselo en cada clic no lo va a cambiar.
                    rechazo = (
                        f"{FUENTE} respondió con otra bolsa o con otro símbolo que el pedido: "
                        "el dato recibido no es de este instrumento y no se muestra"
                    )
                    self._fallos.guardar(clave, rechazo)
                    return _no_disponible(simbolo, rechazo)
                self._cotizaciones.guardar(clave, cotizacion)

            perfil_motivo: str | None = None
            if perfil is None:
                try:
                    perfil = await self._perfil(cliente, simbolo)
                except ErrorDeFuente as exc:
                    logger.info("yahoo_sin_perfil", simbolo=simbolo, motivo=exc.motivo)
                    perfil = None
                    perfil_motivo = f"{FUENTE} no entregó el perfil de la empresa: {exc.motivo}"
                else:
                    if perfil is None:
                        perfil_motivo = f"{FUENTE} no publica perfil para este símbolo"
                    else:
                        self._perfiles.guardar(clave, perfil)

        return BloqueExterno(FUENTE, simbolo, True, None, cotizacion, perfil, perfil_motivo)

    def _abrir(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={"User-Agent": AGENTE, "Accept": "application/json"},
        )

    async def _cotizacion(
        self, cliente: httpx.AsyncClient, simbolo: str
    ) -> CotizacionExterna | None:
        url = URL_CHART.format(simbolo=simbolo)
        parametros = f"?range={RANGO_HISTORICO}&interval={INTERVALO_HISTORICO}"

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", url + parametros, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento, descripcion=f"{FUENTE} chart", politica=self._politica, dormir=self._dormir
        )
        return leer_cotizacion(
            _json(respuesta), simbolo=simbolo, capturado_en=self._ahora().isoformat()
        )

    async def _perfil(self, cliente: httpx.AsyncClient, simbolo: str) -> PerfilExterno | None:
        crumb, cookies = await self._credencial(cliente)
        cliente.cookies.update(cookies)
        url = URL_PERFIL.format(simbolo=simbolo)
        parametros = f"?modules={MODULOS_PERFIL}&crumb={crumb}"

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", url + parametros, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento,
            descripcion=f"{FUENTE} quoteSummary",
            politica=self._politica,
            dormir=self._dormir,
        )
        return leer_perfil(_json(respuesta), capturado_en=self._ahora().isoformat())

    async def _credencial(self, cliente: httpx.AsyncClient) -> tuple[str, httpx.Cookies]:
        """La cookie y el crumb del nivel 2, cacheados. Lanza `ErrorDeFuente` si no se consiguen."""
        guardada = self._credenciales.obtener(FUENTE)
        if guardada is not None:
            return guardada

        # El status de este pedido no se mira: `fc.yahoo.com` contesta 404 y deja las cookies igual,
        # y eso es lo único que se le pide. Por eso no pasa por `pedir`, que convertiría ese 404 en
        # un error y tiraría abajo un paso que en realidad salió bien.
        try:
            await cliente.get(URL_COOKIE)
        except httpx.HTTPError as exc:
            raise ErrorDeFuente(f"no se pudo obtener la cookie ({exc.__class__.__name__})") from exc

        async def intento() -> httpx.Response:
            return await pedir(cliente, "GET", URL_CRUMB, fuente=FUENTE)

        respuesta = await con_reintentos(
            intento, descripcion=f"{FUENTE} crumb", politica=self._politica, dormir=self._dormir
        )
        crumb = respuesta.text.strip()
        if not crumb or "<" in crumb:
            # Yahoo devuelve 200 con una página de error cuando el mecanismo cambió: un crumb que
            # es HTML no es un crumb.
            raise ErrorDeFuente("el crumb vino vacío o no es un crumb")

        credencial = (crumb, cliente.cookies)
        self._credenciales.guardar(FUENTE, credencial)
        return credencial


def _json(respuesta: httpx.Response) -> object:
    """El cuerpo como JSON, o `None`. Un cuerpo ilegible es ausencia de dato, no un 500 nuestro."""
    try:
        return respuesta.json()
    except ValueError:
        return None


@lru_cache(maxsize=1)
def cliente_yahoo() -> ClienteYahoo:
    """El cliente compartido por todo el proceso: la caché de TTL sólo sirve si es una sola."""
    return ClienteYahoo()
