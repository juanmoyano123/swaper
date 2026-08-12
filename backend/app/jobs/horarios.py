"""Cuándo corresponde correr la matinal y cuándo el próximo refresh intra-rueda.

Función pura, sin reloj real ni asyncio: `scheduler.py` es la única parte con reloj de verdad, y
separar el cálculo así es lo que permite probar "a las 08:59 falta un minuto para la matinal" sin
tener que esperar un minuto de verdad.

Los tres horarios (`ingesta_hora_matinal`, `ingesta_rueda_desde`, `ingesta_rueda_hasta`) y el
intervalo de refresh son configurables — `app.core.config` — precisamente para poder ejercitar
esto en un entorno de prueba sin depender de la hora real de la rueda de Buenos Aires.

Usa `zoneinfo` en vez de convertir todo a UTC a mano porque la hora de la rueda está definida en
horario de Buenos Aires y no en UTC: comparar contra UTC directamente rompería dos veces al año en
el cambio de horario de verano si Argentina lo tuviera (hoy no lo tiene, pero la fuente de la
verdad tiene que ser el nombre de la zona, no un offset fijo).

**La rueda es de lunes a viernes.** Hasta el 08/08/2026 estas funciones sólo miraban la hora, así
que un sábado a las 14:00 pasaban el chequeo igual que un martes. No era teórico: una corrida
disparada a mano un sábado escribió 466 filas sin un solo precio ni una sola TIR, y dejó el
indicador de frescura declarando el sábado sobre datos del miércoles. El scheduler habría hecho lo
mismo solo, todos los fines de semana, apenas se habilitara.

**Los feriados bursátiles no se modelan, y es a propósito.** No hay fuente programática confiable
del calendario de feriados de BYMA, y hardcodear una lista sería inventar un dato que se
desactualiza en silencio (regla 1 del dominio). Un feriado entre semana sigue produciendo una
respuesta parcial de BYMA; ese caso lo tiene que atrapar un guardia de "la respuesta vino
anormalmente chica", que todavía no existe y está anotado como pendiente. Acá se cubre lo que sí es
determinístico: el día de la semana.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import Settings

# Lunes=0 … viernes=4 en `date.weekday()`. Sábado y domingo no hay rueda.
ULTIMO_DIA_HABIL = 4


class FueraDeLaRueda(RuntimeError):
    """Se pidió una corrida contra el mercado con el mercado cerrado.

    Vive acá y no en `api/`: la condición es de dominio —hay rueda o no la hay— y el día que un job
    la necesite no va a estar pasando por HTTP. `app/core/errors.py` la traduce a 409."""


def _hora(texto: str) -> time:
    """`"09:00"` → `time(9, 0)`. Sin manejo de error: un horario mal formado en `Settings` tiene
    que reventar al arrancar, no silenciarse acá."""
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


def zona(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.ingesta_zona_horaria)


def _combinar(dia: date, hora: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(dia, hora, tzinfo=tz)


def es_dia_habil(dia: date) -> bool:
    """Lunes a viernes. No sabe de feriados — ver el docstring del módulo."""
    return dia.weekday() <= ULTIMO_DIA_HABIL


def _proximo_dia_habil(dia: date) -> date:
    """El primer día hábil estrictamente posterior a `dia`."""
    siguiente = dia + timedelta(days=1)
    while not es_dia_habil(siguiente):
        siguiente += timedelta(days=1)
    return siguiente


def en_ventana_de_rueda(momento: datetime, settings: Settings) -> bool:
    """Si `momento` cae en día hábil y dentro de `[ingesta_rueda_desde, ingesta_rueda_hasta]`, en
    hora local. Un sábado a las 14:00 da `False` aunque la hora esté en rango."""
    local = momento.astimezone(zona(settings))
    if not es_dia_habil(local.date()):
        return False
    hora_desde = _hora(settings.ingesta_rueda_desde)
    hora_hasta = _hora(settings.ingesta_rueda_hasta)
    return hora_desde <= local.time() <= hora_hasta


def proxima_matinal(desde: datetime, settings: Settings) -> datetime:
    """El próximo instante en que toca correr la corrida matinal completa.

    Hoy si todavía no pasó la hora configurada, o el próximo día hábil si ya pasó —o si hoy no es
    hábil—. No hay ventana: la matinal es un único disparo por día, a diferencia del refresh que se
    repite dentro de la rueda. Un viernes a las 10:00 devuelve el lunes, no el sábado.
    """
    tz = zona(settings)
    local = desde.astimezone(tz)
    hora = _hora(settings.ingesta_hora_matinal)
    objetivo = _combinar(local.date(), hora, tz)
    if objetivo <= local or not es_dia_habil(local.date()):
        objetivo = _combinar(_proximo_dia_habil(local.date()), hora, tz)
    return objetivo


def proximo_refresh(desde: datetime, settings: Settings) -> datetime:
    """El próximo tick de refresh intra-rueda: un múltiplo de `ingesta_refresh_minutos` desde el
    inicio de la rueda, sin pasarse del cierre.

    Fuera de la ventana de hoy —antes de que abra, después de que cierre, o en un día no hábil— el
    próximo tick es el inicio de la rueda del próximo día hábil. Así el scheduler nunca dispara un
    refresh fuera de horario ni un fin de semana, sin que `_ejecutar` tenga que volver a chequear la
    ventana.
    """
    tz = zona(settings)
    local = desde.astimezone(tz)
    hora_desde = _hora(settings.ingesta_rueda_desde)
    hora_hasta = _hora(settings.ingesta_rueda_hasta)
    intervalo = timedelta(minutes=settings.ingesta_refresh_minutos)

    inicio_hoy = _combinar(local.date(), hora_desde, tz)
    fin_hoy = _combinar(local.date(), hora_hasta, tz)
    inicio_manana = _combinar(_proximo_dia_habil(local.date()), hora_desde, tz)

    if not es_dia_habil(local.date()):
        return inicio_manana
    if local < inicio_hoy:
        return inicio_hoy
    if local >= fin_hoy:
        return inicio_manana

    pasos_transcurridos = (local - inicio_hoy) // intervalo + 1
    candidato = inicio_hoy + pasos_transcurridos * intervalo
    return candidato if candidato <= fin_hoy else inicio_manana
