"""La barra de estado del dato como una sola llamada — F-013.

Junta las dos mitades y las presenta juntas: la barata, que se lee de la base en cada request, y la
cara, que sale del caché de `analisis.py` mientras la corrida no cambie.

## Qué es "la hora del dato" y qué no

El GWT-2 de la spec es la regla 1 del proyecto aplicada al tiempo: un snapshot de las 11:00 mostrado
a las 11:15 declara **la hora del snapshot y la demora de la fuente**, nunca la hora actual como si
fuera el dato. Por eso la respuesta lleva tres horas distintas con tres nombres distintos y ninguna
puede ocupar el lugar de otra:

- `capturado_en` — cuándo se capturó el precio más nuevo que hay en la base.
- `dato_valido_hasta` — `capturado_en` menos la demora declarada por la fuente. **Es el número que
  contesta la pregunta real**: hasta qué momento del mercado refleja lo que se está viendo. La API
  abierta de BYMA publica con 20 minutos de retraso, así que un precio capturado 11:15 es el mercado
  de las 10:55.
- `consultado_en` — cuándo se armó esta respuesta. Es la hora del reloj y **no es la hora de nada de
  lo que se muestra**; viaja para poder distinguir una pantalla vieja de un dato viejo.

`antiguedad_minutos` se informa cruda, sin veredicto. Ver el docstring de `estado/alertas.py`: no
hay alerta de "dato viejo" porque fijar el umbral sería decidir cuánta desactualización es aceptable
para operar, y eso no lo decide el backend.

## Por qué las alertas de posiciones (F-029) no están acá

`app/posiciones/resolucion.py` emite cinco alertas —posiciones no resueltas, sin monto, sin base
para el porcentaje, sin plazo de liquidación y con dato no sano— y ninguna aparece en esta barra.
No es un olvido: **hablan de una cartera que alguien acaba de pegar**, no del dato de mercado. La
barra es global y transversal a las seis pantallas, y una alerta sobre la cartera de un asesor no
tiene sentido mostrarla mientras otro mira el monitor. Esas alertas viven donde vive su cartera, en
la respuesta de `POST /api/v1/posiciones/resolucion`, que es donde F-029 ya las muestra.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.core.config import Settings
from app.db.health import get_last_snapshot
from app.estado.alertas import corrida_atrasada, sin_corrida_registrada, sin_dato_de_mercado
from app.estado.analisis import Analisis, CacheDelAnalisis, analizar
from app.estado.fuentes import diagnosticar
from app.ingesta.alertas import Alerta, Severidad
from app.jobs.horarios import es_dia_habil, zona
from app.jobs.registro import ultima_corrida

# La fuente cuya demora se declara. Experimento data912 (rama `experimento/data912`): el precio de
# cada especie puede salir de data912 (que no declara demora — regla 11, no se le inventa una) o
# de BYMA de respaldo (que sí la declara, 20 minutos). El número que se muestra sigue siendo el
# peor caso conocido: la demora de BYMA, porque es la única que la fuente publica y porque un
# precio de respaldo puede ser tan viejo como eso. Antes de este experimento la única fuente era
# BYMA y el texto lo daba por sentado; ahora tiene que decir por qué sigue siendo ese número.
FUENTE_DE_LA_DEMORA = "BYMA (respaldo, la fuente con demora declarada)"
POR_QUE_LA_DEMORA = (
    "Los precios salen de data912 cuando la especie está ahí, con BYMA de respaldo para lo que "
    "falte. data912 no declara demora respecto del mercado, así que se muestra la de BYMA: es el "
    "peor caso conocido, y un precio de respaldo puede ser de hasta ese momento anterior. Un "
    "precio rotulado 'arrastre' es el último cierre conocido de una especie que no operó en la "
    "sesión: refleja una fecha anterior que la fuente no declara, no necesariamente la de la "
    "demora de BYMA."
)

# `Severidad` es un `StrEnum`: comparar dos valores con `<` compara los strings, y alfabéticamente
# "advertencia" < "error" < "info", que es casi el orden inverso al que interesa. El orden se
# declara acá, explícito, en vez de confiar en un operador que devuelve una respuesta plausible y
# equivocada.
ORDEN_SEVERIDAD: dict[str, int] = {
    Severidad.ERROR.value: 0,
    Severidad.ADVERTENCIA.value: 1,
    Severidad.INFO.value: 2,
}

ORIGEN_INGESTA = "ingesta"
"""Alertas que quedaron guardadas cuando corrió el job: lo que falló al **traer** el dato."""

ORIGEN_ESTADO = "estado"
"""Alertas calculadas ahora sobre lo que hay en la base: lo que falta en el dato **ya traído**."""


@dataclass(frozen=True, slots=True)
class EstadoDelDato:
    """Todo lo que la barra global muestra, en una sola estructura."""

    dato: dict[str, object]
    corrida: dict[str, object] | None
    fuentes: dict[str, object]
    analisis: Analisis
    alertas: list[dict[str, object]]
    desde_cache: bool
    consultado_en: datetime

    @property
    def peor_severidad(self) -> str | None:
        """La severidad más alta presente, o `None` si no hay ninguna alerta.

        `None` y `"info"` son estados distintos y la barra los muestra distinto: uno es "no hay nada
        que decir" y el otro es "hay cosas que decir y ninguna urge".
        """
        if not self.alertas:
            return None
        return min((str(a["severidad"]) for a in self.alertas), key=_rango)

    def como_dict(self) -> dict[str, object]:
        por_severidad = {
            severidad: sum(1 for a in self.alertas if a["severidad"] == severidad)
            for severidad in ORDEN_SEVERIDAD
        }
        return {
            "consultado_en": self.consultado_en.isoformat(),
            "dato": self.dato,
            "corrida": self.corrida,
            "fuentes": self.fuentes,
            **self.analisis.como_dict(),
            "alertas": self.alertas,
            "resumen": {
                "alertas": len(self.alertas),
                "por_severidad": por_severidad,
                "peor_severidad": self.peor_severidad,
                "requiere_intervencion": self.fuentes["requiere_intervencion"],
            },
            "costo": {
                "desde_cache": self.desde_cache,
                "analisis_calculado_en": self.analisis.calculado_en.isoformat(),
                "analisis_duracion_ms": self.analisis.duracion_ms,
            },
        }


def _rango(severidad: str) -> int:
    """Dónde va una severidad en el orden de urgencia. Lo desconocido va último y no primero.

    Una severidad que este backend no conoce no puede escalar sola al tope de la lista: si algún día
    entra un valor nuevo, que se lo vea al final y no que empuje un error real hacia abajo.
    """
    return ORDEN_SEVERIDAD.get(severidad, len(ORDEN_SEVERIDAD))


def ordenar(alertas: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    """Las alertas de la más urgente a la menos, y dentro de cada nivel las accionables primero.

    El segundo criterio no es decorativo y es el que ordena la barra de verdad: entre dos errores,
    "la credencial de una fuente venció" y "BYMA no responde" duelen igual, pero sólo el primero
    espera que alguien haga algo. Es la distinción que `Alerta` separa en `accion_requerida`, y
    perderla en el orden la escondería debajo de la que se arregla sola.

    El orden es estable, así que dentro de cada grupo se conserva el de origen: primero las de la
    corrida y después las del estado de la base, que es como se produjeron.
    """
    return sorted(
        alertas,
        key=lambda a: (_rango(str(a["severidad"])), 0 if a.get("accion_requerida") else 1),
    )


async def estado_del_dato(
    conn: Any,
    settings: Settings,
    *,
    cache: CacheDelAnalisis,
    hoy: date | None = None,
    ahora: datetime | None = None,
) -> EstadoDelDato:
    """Arma la respuesta de la barra: dos consultas baratas más el análisis cacheado.

    El caché llega por parámetro y no de un singleton de módulo para que cada aplicación tenga el
    suyo —vive en `app.state`— y para que un test pueda darle uno vacío sin tener que acordarse de
    limpiar estado global entre casos.
    """
    ahora = ahora or datetime.now(UTC)

    corrida = await ultima_corrida(conn)
    capturado_en, avisos = await get_last_snapshot(conn)

    alertas_de_ingesta = _alertas_de(corrida)
    analisis, desde_cache = await cache.resolver(
        _clave_de_cache(corrida, capturado_en), lambda: analizar(conn, hoy=hoy)
    )

    del_estado = [*_alertas_del_estado(corrida, avisos, settings, ahora), *analisis.alertas]
    alertas = ordenar(
        [
            *(_serializada(a, ORIGEN_INGESTA) for a in alertas_de_ingesta),
            *(_serializada(a.como_dict(), ORIGEN_ESTADO) for a in del_estado),
        ]
    )

    return EstadoDelDato(
        dato=_dato(capturado_en, settings, ahora),
        corrida=_corrida_sin_alertas(corrida),
        fuentes=diagnosticar(alertas),
        analisis=analisis,
        alertas=alertas,
        desde_cache=desde_cache,
        consultado_en=ahora,
    )


def _clave_de_cache(
    corrida: dict[str, object] | None, capturado_en: datetime | None
) -> tuple[object, ...]:
    """Qué identifica al contenido de la base. Ver el docstring de `analisis.py`.

    Con `corridas_ingesta` vacía —el caso de la base real hoy— la clave se reduce a la hora del
    snapshot, que es lo que de verdad se mueve cuando alguien escribe precios. Sigue funcionando:
    lo que la clave tiene que garantizar es que cambie cuando cambia el dato, no que tenga dos
    componentes.
    """
    return (corrida["id"] if corrida else None, capturado_en)


def _alertas_de(corrida: dict[str, object] | None) -> list[dict[str, object]]:
    """Las alertas que la corrida guardó, tal como quedaron en `jsonb`.

    Se filtran las que no tienen la forma de una alerta en vez de confiar en el contenido de la
    columna: es JSON libre desde el punto de vista de PostgreSQL, y una respuesta de la barra que
    revienta con un `KeyError` dejaría las seis pantallas sin barra por una fila mal escrita.
    """
    if corrida is None:
        return []
    guardadas = corrida.get("alertas") or []
    if not isinstance(guardadas, list):
        return []
    return [a for a in guardadas if isinstance(a, dict) and "codigo" in a and "severidad" in a]


# Cuántas ruedas puede pasar la ingesta sin correr antes de que valga la pena gritar. Una es
# tolerancia sana: un cron que se saltea un disparo y engancha el siguiente no es una falla, y el
# refresh siguiente trae lo mismo. Dos ruedas seguidas ya no es un tick perdido, es algo roto.
RUEDAS_PERDIDAS_TOLERADAS = 1


def _ruedas_habiles_entre(desde: date, hasta: date) -> int:
    """Días hábiles estrictamente posteriores a `desde` y hasta `hasta` inclusive.

    Se cuentan ruedas y no horas para que un fin de semana o un fin de semana largo no disparen la
    alerta: el lunes a la mañana pasaron 60 horas desde el viernes y no se perdió ni una rueda.
    No sabe de feriados, igual que `es_dia_habil` — un feriado suma un falso positivo de una rueda,
    que la tolerancia absorbe.
    """
    dias = (hasta - desde).days
    if dias <= 0:
        return 0
    return sum(1 for n in range(1, dias + 1) if es_dia_habil(desde + timedelta(days=n)))


def _alertas_del_estado(
    corrida: dict[str, object] | None,
    avisos: Sequence[str],
    settings: Settings,
    ahora: datetime,
) -> list[Alerta]:
    """Los huecos que sólo esta feature ve: sin corrida, corrida atrasada y sin dato de mercado."""
    alertas: list[Alerta] = []
    if corrida is None:
        alertas.append(sin_corrida_registrada())
    else:
        alertas.extend(_atraso_de(corrida, settings, ahora))
    alertas.extend(sin_dato_de_mercado(aviso) for aviso in avisos)
    return alertas


def _atraso_de(corrida: dict[str, object], settings: Settings, ahora: datetime) -> list[Alerta]:
    """Alerta si desde la última corrida pasaron más ruedas de las toleradas.

    La fecha viene de la corrida registrada, no del último precio: un precio puede ser viejo porque
    la especie no operó, que es normal; una corrida vieja significa que nadie fue a preguntar.
    """
    inicio = corrida.get("iniciado_en")
    if not isinstance(inicio, datetime):
        return []
    tz = zona(settings)
    perdidas = _ruedas_habiles_entre(inicio.astimezone(tz).date(), ahora.astimezone(tz).date())
    if perdidas <= RUEDAS_PERDIDAS_TOLERADAS:
        return []
    return [corrida_atrasada(inicio.astimezone(tz), perdidas)]


def _serializada(alerta: dict[str, object], origen: str) -> dict[str, object]:
    """Una alerta lista para viajar, con el origen y con los campos opcionales siempre presentes.

    `accion_requerida` y `detalle` se completan si faltan porque una alerta guardada hace meses pudo
    haberse escrito con otra forma, y el consumidor no tiene por qué tener dos caminos según de qué
    corrida salió.
    """
    return {
        "codigo": alerta.get("codigo"),
        "mensaje": alerta.get("mensaje", ""),
        "severidad": alerta.get("severidad", Severidad.ADVERTENCIA.value),
        "accion_requerida": alerta.get("accion_requerida"),
        "detalle": alerta.get("detalle") or {},
        "origen": origen,
    }


def _corrida_sin_alertas(corrida: dict[str, object] | None) -> dict[str, object] | None:
    """La corrida sin su lista de alertas: ésas ya viajan una vez, en la lista general.

    Duplicarlas haría que la misma alerta se pueda contar dos veces y, peor, que alguien la vea en
    un lugar y no en el otro según qué parte del payload esté mirando.
    """
    if corrida is None:
        return None
    return {clave: valor for clave, valor in corrida.items() if clave != "alertas"}


def _dato(capturado_en: datetime | None, settings: Settings, ahora: datetime) -> dict[str, object]:
    """Las tres horas y la demora, cada una con su nombre. Ver el docstring del módulo.

    Cuando no hay snapshot, `capturado_en`, `dato_valido_hasta` y `antiguedad_minutos` quedan en
    `null` y **no en cero**: no saber hace cuánto se capturó el dato no es haberlo capturado recién.
    La demora declarada sí sale igual, porque es un atributo de la fuente y no de la corrida.
    """
    demora = settings.byma_demora_minutos
    return {
        "capturado_en": capturado_en.isoformat() if capturado_en else None,
        "dato_valido_hasta": (capturado_en - timedelta(minutes=demora)).isoformat()
        if capturado_en
        else None,
        "antiguedad_minutos": round((ahora - capturado_en).total_seconds() / 60)
        if capturado_en
        else None,
        "demora": {
            "minutos": demora,
            "fuente": FUENTE_DE_LA_DEMORA,
            "por_que": POR_QUE_LA_DEMORA,
        },
    }
