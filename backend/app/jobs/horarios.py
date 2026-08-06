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
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import Settings


def _hora(texto: str) -> time:
    """`"09:00"` → `time(9, 0)`. Sin manejo de error: un horario mal formado en `Settings` tiene
    que reventar al arrancar, no silenciarse acá."""
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


def zona(settings: Settings) -> ZoneInfo:
    return ZoneInfo(settings.ingesta_zona_horaria)


def _combinar(dia: date, hora: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(dia, hora, tzinfo=tz)


def en_ventana_de_rueda(momento: datetime, settings: Settings) -> bool:
    """Si `momento` cae dentro de `[ingesta_rueda_desde, ingesta_rueda_hasta]`, en hora local."""
    local = momento.astimezone(zona(settings))
    hora_desde = _hora(settings.ingesta_rueda_desde)
    hora_hasta = _hora(settings.ingesta_rueda_hasta)
    return hora_desde <= local.time() <= hora_hasta


def proxima_matinal(desde: datetime, settings: Settings) -> datetime:
    """El próximo instante en que toca correr la corrida matinal completa.

    Hoy si todavía no pasó la hora configurada, o mañana si ya pasó. No hay ventana: la matinal es
    un único disparo por día, a diferencia del refresh que se repite dentro de la rueda.
    """
    tz = zona(settings)
    local = desde.astimezone(tz)
    objetivo = _combinar(local.date(), _hora(settings.ingesta_hora_matinal), tz)
    if objetivo <= local:
        objetivo += timedelta(days=1)
    return objetivo


def proximo_refresh(desde: datetime, settings: Settings) -> datetime:
    """El próximo tick de refresh intra-rueda: un múltiplo de `ingesta_refresh_minutos` desde el
    inicio de la rueda, sin pasarse del cierre.

    Fuera de la ventana de hoy —antes de que abra o después de que cierre— el próximo tick es el
    inicio de la rueda de mañana. Así el scheduler nunca dispara un refresh fuera de horario, sin
    que `_ejecutar` tenga que volver a chequear la ventana.
    """
    tz = zona(settings)
    local = desde.astimezone(tz)
    hora_desde = _hora(settings.ingesta_rueda_desde)
    hora_hasta = _hora(settings.ingesta_rueda_hasta)
    intervalo = timedelta(minutes=settings.ingesta_refresh_minutos)

    inicio_hoy = _combinar(local.date(), hora_desde, tz)
    fin_hoy = _combinar(local.date(), hora_hasta, tz)
    inicio_manana = _combinar(local.date() + timedelta(days=1), hora_desde, tz)

    if local < inicio_hoy:
        return inicio_hoy
    if local >= fin_hoy:
        return inicio_manana

    pasos_transcurridos = (local - inicio_hoy) // intervalo + 1
    candidato = inicio_hoy + pasos_transcurridos * intervalo
    return candidato if candidato <= fin_hoy else inicio_manana
