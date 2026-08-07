"""La mitad cara de la barra, calculada una vez por corrida — F-013.

# El problema que este módulo existe para resolver

La barra de estado del dato está en las seis pantallas y se pide en cada carga. Todo lo que haga
este código lo paga **cada pantalla del producto**, para siempre. Es la misma clase de problema que
F-012 ya tuvo cuando el contraste contra BYMA vivo colgaba siete endpoints que no lo usaban (ver el
docstring de `sanear_universo`), sólo que peor: aquéllos eran siete endpoints y esto es todo.

Medido contra la base real del 07/08/2026, lo que la barra necesita cuesta:

| pieza                                   | filas | tiempo  |
|-----------------------------------------|-------|---------|
| última corrida + hora del snapshot      |     1 | ~0,11 s |
| universo saneado (F-010 + F-011 + F-012)| 2.894 | ~0,33 s |
| cronograma y paridades (F-015)          | 6.150 | ~0,12 s |

O sea ~0,45 s de trabajo repetido por cada carga de pantalla, seis veces por vuelta, para producir
**exactamente el mismo resultado** hasta que entre una corrida nueva.

# La decisión: cachear por identidad de la corrida, no por reloj

El análisis caro es una **función pura del contenido de la base**: sobre las mismas filas de
`resumen`, `cashflow` e `instrumentos` da siempre lo mismo, porque nada de esto sale a la red y nada
depende del reloj salvo la fecha de corte del calendario. Y esas tablas sólo cambian cuando una
ingesta escribe.

Así que la clave del caché es **qué corrida produjo el dato que está en la base**: el `id` de la
última fila de `corridas_ingesta` y la hora del último snapshot de `precios`, que son los dos
números que la mitad barata ya lee de todas formas. Mientras la clave no cambie, el resultado
cacheado no es una aproximación aceptable: es el mismo resultado.

Es mejor que un TTL a secas en las dos direcciones. Un TTL de cinco minutos serviría dato viejo
durante cinco minutos después de una corrida —justo cuando más importa que la barra diga la
verdad— y recalcularía cada cinco minutos un domingo, cuando no cambió nada desde el viernes.

El TTL igual está, como red de seguridad y no como política: hay caminos que escriben `instrumentos`
sin tocar `precios` —la semilla curada de F-009 es uno— y ésos moverían el resultado sin mover la
clave. Cinco minutos es el techo de cuánto puede durar esa discrepancia.

# Lo que este módulo **no** hace

- **No sale a la red.** `sanear_universo` se invoca sin contraste, que es lo único de aquel servicio
  que sale a Internet. Un BYMA colgado reintenta cinco veces con 90 s de timeout: en el camino de la
  barra eso sería el producto entero clavado ocho minutos por un control que ni siquiera es fuente.
  El precio de esa decisión es explícito y la barra lo declara: la alerta de contraste del tipo de
  cambio que pide la ficha de F-013 **no aparece acá**, y en su lugar aparece
  `tipo_de_cambio_sin_contraste`, que es la que dice que no se evaluó. Quien quiera el contraste lo
  tiene en `GET /api/v1/universo/tipo-de-cambio`, que es una pantalla que alguien abre a propósito.
- **No arma la grilla de doce meses.** De todo F-015 la barra necesita una sola cosa —qué proporción
  del universo llegó al calendario— y `armar_calendario` construye doce meses con su detalle por
  instrumento para tirarlos. Se componen las piezas públicas de F-015 (`leer_cashflow`,
  `flujos_por_peso`, `cobertura_del_calendario`) en vez de llamar a `calendario_del_universo`, que
  además volvería a leer y sanear el universo entero por su cuenta: +0,33 s, un 70 % más, para
  llegar al mismo número.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import structlog

from app.calendario.alertas import cobertura_del_calendario
from app.calendario.cupones import flujos_por_peso, indexar_cronograma, indexar_paridades
from app.calendario.lectura import leer_cashflow, leer_paridades
from app.estado.campos import alertas_de_cobertura, medir_campos_criticos
from app.estado.campos import como_dict as cobertura_como_dict
from app.ingesta.alertas import Alerta
from app.universo.emisiones import UniversoDeduplicado
from app.universo.lectura import leer_universo
from app.universo.segmentacion import segmentar
from app.universo.servicio import UniversoSaneado, sanear

logger = structlog.get_logger()

# Cuántos descartes viajan en la respuesta de la barra. El GWT-3 de la spec pide poder desplegar los
# 14 descartes de una corrida con su motivo y su valor, así que el tope tiene que quedar cómodamente
# por encima de eso; pero la barra está en las seis pantallas y una colección sin techo no puede
# viajar en un recurso que se pide en cada carga. Cuando se corta, la respuesta lo dice y el listado
# completo, paginado por cursor, sigue estando en GET /api/v1/universo/sanidad/descartes.
MAX_DESCARTES = 50

# Techo de cuánto puede vivir un análisis cacheado aunque la corrida no haya cambiado. Ver el
# docstring del módulo: es red de seguridad contra escrituras que no mueven la clave, no la
# política.
TTL_SEGUNDOS = 300.0

# El contraste del tipo de cambio contra los índices de BYMA no se evalúa en el camino de la barra:
# es la única pieza de todo esto que sale a la red. Se declara con estas palabras y no se deja en
# `null` a secas, porque `null` y la alerta que lo acompaña se leen como "se intentó y no se pudo".
CONTRASTE_EVALUADO: dict[str, object] = {
    "evaluado": False,
    "por_que": (
        "El contraste contra los índices de BYMA es lo único de este cálculo que sale a Internet, "
        "y la barra se pide en cada carga de cada pantalla: una fuente colgada dejaría el producto "
        "entero esperando. El implícito se deriva del propio universo y no lo necesita."
    ),
    "donde_verlo": "GET /api/v1/universo/tipo-de-cambio",
}


@dataclass(frozen=True, slots=True)
class Analisis:
    """Lo que se calcula sobre el contenido de la base, listo para viajar y para cachearse."""

    universo: dict[str, object]
    descartes: list[dict[str, object]]
    descartes_totales: int
    cobertura: list[dict[str, object]]
    tipo_de_cambio: dict[str, object]
    calendario: dict[str, object]
    alertas: list[Alerta]
    calculado_en: datetime
    duracion_ms: int

    def como_dict(self) -> dict[str, object]:
        return {
            "universo": self.universo,
            "descartes": {
                "total": self.descartes_totales,
                "items": self.descartes,
                "truncado": self.descartes_totales > len(self.descartes),
            },
            "cobertura": self.cobertura,
            "tipo_de_cambio": self.tipo_de_cambio,
            "calendario": self.calendario,
        }


@dataclass
class CacheDelAnalisis:
    """Guarda un solo análisis: el de la corrida vigente.

    Es uno y no un diccionario por clave porque **no hay varias respuestas correctas a la vez**: el
    estado del dato es del universo de mercado, que es único y compartido por todos los asesores
    (la base de mercado es común; lo que se aísla por asesor son las carteras). Un diccionario sólo
    serviría para acumular análisis de corridas que ya nadie va a pedir.

    El lock evita la estampida: seis pantallas que cargan a la vez con el caché frío dispararían
    seis lecturas del universo entero para escribir seis veces el mismo resultado. Con el lock, una
    calcula y las otras cinco esperan y leen.
    """

    ttl_segundos: float = TTL_SEGUNDOS
    _clave: tuple[object, ...] | None = None
    _analisis: Analisis | None = None
    _vence_en: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def resolver(
        self, clave: tuple[object, ...], calcular: Callable[[], Awaitable[Analisis]]
    ) -> tuple[Analisis, bool]:
        """El análisis de esta clave, del caché o recién calculado. El bool dice de dónde salió.

        El chequeo se hace dos veces, antes y después de tomar el lock, y no es redundante: la
        segunda es la que hace que de seis pantallas simultáneas calcule una sola. La primera es la
        que hace que el caso normal —caché caliente— no se serialice detrás de un lock.
        """
        vigente = self._vigente(clave)
        if vigente is not None:
            return vigente, True

        async with self._lock:
            vigente = self._vigente(clave)
            if vigente is not None:
                return vigente, True

            analisis = await calcular()
            self._clave = clave
            self._analisis = analisis
            self._vence_en = time.monotonic() + self.ttl_segundos
            return analisis, False

    def _vigente(self, clave: tuple[object, ...]) -> Analisis | None:
        if self._analisis is None or self._clave != clave:
            return None
        if time.monotonic() >= self._vence_en:
            return None
        return self._analisis

    def limpiar(self) -> None:
        """Descarta lo guardado: para los tests y para quien necesite forzar el recálculo."""
        self._clave = None
        self._analisis = None
        self._vence_en = 0.0


async def analizar(conn: Any, *, hoy: date | None = None) -> Analisis:
    """Lee el universo una sola vez y deriva todo lo que la barra muestra de él.

    Las tres lecturas van en serie y no en paralelo a propósito: comparten una conexión de asyncpg,
    que no multiplexa consultas. Un `gather` sobre la misma conexión no las apuraría —las
    serializaría igual, con un error posible de por medio si dos entran a la vez.
    """
    hoy = hoy or date.today()
    empezado = time.perf_counter()

    # Se compone `leer_universo` + `segmentar` + `sanear` en vez de llamar a `sanear_universo`, que
    # hace exactamente esto, por una razón concreta: la cobertura de campos se mide sobre las filas
    # **crudas** de la vista, y `sanear_universo` sólo devuelve las especies ya segmentadas. Medir
    # `tipo_tasa` sobre ésas daría 100 % siempre: tener segmento es haber tenido tipo de tasa.
    filas = await leer_universo(conn)
    saneado = sanear(segmentar(filas), leidos=len(filas))
    dedup = saneado.emisiones()

    cronograma = indexar_cronograma(await leer_cashflow(conn))
    filas_paridad = await leer_paridades(conn)
    flujos = flujos_por_peso(dedup.colapsado(), cronograma, indexar_paridades(filas_paridad), hoy)

    coberturas = medir_campos_criticos(filas, filas_paridad)
    descartes = [d.como_dict() for d in saneado.descartes]

    # Los mismos cinco números alimentan el bloque `calendario` de la respuesta y la alerta que lo
    # declara. Se arman una vez: si divergieran, la barra mostraría un número y la alerta otro.
    calendario = {
        "emisiones": flujos.evaluados,
        "con_calendario": len(flujos.tickers),
        "sin_paridad": len(flujos.sin_paridad),
        "sin_cronograma": len(flujos.sin_cronograma),
        "vencidos": len(flujos.vencidos),
    }

    alertas = [
        *saneado.alertas,
        *dedup.alertas,
        *alertas_de_cobertura(coberturas),
        *flujos.alertas,
        cobertura_del_calendario(**calendario),
    ]

    duracion_ms = round((time.perf_counter() - empezado) * 1000)
    logger.info(
        "estado_del_dato_analizado",
        leidos=saneado.leidos,
        evaluados=len(saneado.especies),
        descartados=len(descartes),
        emisiones=flujos.evaluados,
        con_calendario=len(flujos.tickers),
        alertas=len(alertas),
        duracion_ms=duracion_ms,
    )

    return Analisis(
        universo=_resumen_del_universo(saneado, dedup),
        descartes=descartes[:MAX_DESCARTES],
        descartes_totales=len(descartes),
        cobertura=[cobertura_como_dict(c) for c in coberturas],
        # `contraste` sale en `null` y la alerta que lo acompaña dice "no se pudo contrastar". En
        # esta barra el motivo es otro y hay que declararlo: **no se pidió**. La diferencia importa
        # por lo mismo que la de credencial vencida contra API caída — "no se pudo" manda a alguien
        # a revisar si BYMA está andando, y acá BYMA no tiene nada que ver.
        tipo_de_cambio=saneado.cambio.como_dict() | {"contraste_evaluado": CONTRASTE_EVALUADO},
        calendario=dict(calendario),
        alertas=alertas,
        calculado_en=datetime.now(UTC),
        duracion_ms=duracion_ms,
    )


def _resumen_del_universo(
    saneado: UniversoSaneado, dedup: UniversoDeduplicado
) -> dict[str, object]:
    """Los conteos que dicen de qué tamaño es el universo del que se está hablando.

    `sin_segmento` va acá arriba y no escondido en el detalle porque es el número que explica por
    qué la sanidad puede descartar cero sin que eso signifique que el dato está sano: una especie
    sin tipo de tasa no tiene segmento, y sin segmento no hay techo contra el cual compararla, así
    que las dos capas de F-010 ni la miran. Medido el 07/08/2026 son 535 de 1.477 filas de renta
    fija, y los dos únicos rendimientos imposibles del universo —VE32P al 614 % y CAC4O al 315 %—
    caen justamente ahí.
    """
    return {
        "leidos": saneado.leidos,
        "renta_variable": saneado.renta_variable,
        "sin_segmento": len(saneado.sin_segmento),
        "evaluados": len(saneado.especies),
        "con_rendimiento": sum(1 for e in saneado.especies if e.rendimiento is not None),
        "descartados": len(saneado.descartes),
        "operables": len(saneado.operables()),
        "emisiones": dedup.resumen()["emisiones"],
    }
