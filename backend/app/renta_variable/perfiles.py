"""Lectura y escritura de `public.perfil_renta_variable`.

Sólo SQL, sin decidir nada: qué papeles están pendientes de clasificar y cómo se persiste un
resultado. La decisión de cuándo correr, a qué ritmo y qué hacer con un 429 de la fuente vive en
`clasificacion.py`.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from app.universo.segmentacion import CLASES_RENTA_VARIABLE

# El perfil de una empresa (nombre, actividad, rubro) cambia lento: una fila de hace un mes sigue
# sirviendo. Ni tan corto que reprocese todo el universo cada corrida, ni tan largo que un cambio
# real (una fusión, una escisión) tarde meses en reflejarse.
DIAS_VENCIMIENTO = 30

_CLASES = ", ".join(f"'{c}'" for c in CLASES_RENTA_VARIABLE)

SQL_UPSERT_SEC = (
    "INSERT INTO public.perfil_renta_variable "
    "(ticker, nombre_largo, sic_codigo, sic_titulo, sic_oficina, division_cadena, "
    " estrategia_etf, region_etf, ratio_conversion, mercado_origen, fuente, capturado_en) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12) "
    "ON CONFLICT (ticker) DO UPDATE SET "
    # `nombre_largo` con COALESCE y no pisado: la SEC no lo publica para todo papel, y la lista de
    # CEDEARs de BYMA sí lo trae para algunos — perder el que ya había sería un retroceso.
    "nombre_largo = COALESCE(EXCLUDED.nombre_largo, public.perfil_renta_variable.nombre_largo), "
    "sic_codigo = EXCLUDED.sic_codigo, "
    "sic_titulo = EXCLUDED.sic_titulo, "
    "sic_oficina = EXCLUDED.sic_oficina, "
    "division_cadena = EXCLUDED.division_cadena, "
    "estrategia_etf = EXCLUDED.estrategia_etf, "
    # Sin COALESCE, igual que `estrategia_etf`: las dos salen del mismo nombre y con el mismo
    # parser, así que un valor nuevo nunca es "menos" que el guardado — o el nombre cambió, o el
    # vocabulario de `etfs.py` cambió, y en los dos casos gana lo recién derivado. Protegerlas
    # dejaría una geografía vieja pegada a un nombre que ya no la declara.
    "region_etf = EXCLUDED.region_etf, "
    "ratio_conversion = EXCLUDED.ratio_conversion, "
    "mercado_origen = EXCLUDED.mercado_origen, "
    "fuente = EXCLUDED.fuente, "
    "capturado_en = EXCLUDED.capturado_en"
)

# Pendiente = sin fila, con una fila que escribió otra fuente, o con una vencida.
#
# **No se mira si `sic_codigo` quedó nulo.** La primera versión lo hacía —"si no tiene SIC, falta
# clasificarlo"— y el job no avanzaba nunca: los ~1.500 papeles que la SEC no lista volvían a la
# cola en cada corrida, y nueve tandas de 100 bajaron los pendientes de 1.539 a 1.536 (medido el
# 13/08/2026). Una fila vacía escrita por la SEC significa "se preguntó y no está", que es un
# resultado, no una tarea pendiente. `capturado_en` decide cuándo se vuelve a preguntar.
SQL_PAPELES_PENDIENTES_SEC = (
    "SELECT i.ticker FROM public.instrumentos i "
    "LEFT JOIN public.perfil_renta_variable p ON p.ticker = i.ticker "
    f"WHERE i.clase_activo IN ({_CLASES}) "
    "AND (p.ticker IS NULL "
    "     OR p.fuente IS DISTINCT FROM $2 "
    "     OR p.capturado_en < now() - make_interval(days => $1::int)) "
    "ORDER BY i.ticker"
)


async def papeles_pendientes_sec(
    conn: Any, *, fuente: str, dias_vencimiento: int = DIAS_VENCIMIENTO
) -> list[str]:
    """Tickers de renta variable sin clasificar por `fuente`, o con una clasificación vencida."""
    filas = await conn.fetch(SQL_PAPELES_PENDIENTES_SEC, dias_vencimiento, fuente)
    return [fila["ticker"] for fila in filas]


async def guardar_clasificacion(
    conn: Any,
    ticker: str,
    *,
    nombre_largo: str | None,
    sic_codigo: str | None,
    sic_titulo: str | None,
    sic_oficina: str | None,
    division_cadena: str | None,
    estrategia_etf: str | None,
    region_etf: str | None,
    ratio_conversion: str | None,
    mercado_origen: str | None,
    fuente: str,
    capturado_en: datetime,
) -> None:
    """Upsert de la clasificación de un papel. Se persiste ticker a ticker y no al final de la
    corrida: un corte a mitad de camino conserva lo que ya se trajo."""
    await conn.execute(
        SQL_UPSERT_SEC,
        ticker,
        nombre_largo,
        sic_codigo,
        sic_titulo,
        sic_oficina,
        division_cadena,
        estrategia_etf,
        region_etf,
        ratio_conversion,
        mercado_origen,
        fuente,
        capturado_en,
    )


# --- Reclasificación de fondos desde el nombre ya persistido -------------------------------------
#
# `estrategia_etf` y `region_etf` no son dato de la SEC: salen de parsear `nombre_largo`, que ya
# está en esta tabla. Cuando el vocabulario de `etfs.py` cambia —como el 28/08/2026, que estrenó
# `region_etf`— hay que reescribirlas sobre las 1.641 filas, y hacerlo por el camino normal
# significaría volver a barrer la SEC de a 100 papeles por corrida para no cambiar nada de lo que la
# SEC aporta. Estas dos consultas existen para no hacer eso.

SQL_NOMBRES_PERSISTIDOS = (
    "SELECT ticker, nombre_largo FROM public.perfil_renta_variable "
    "WHERE nombre_largo IS NOT NULL ORDER BY ticker"
)

# **No toca `capturado_en` ni `fuente`.** Los dos declaran cuándo y de dónde se trajo la fila, y
# esto no trae nada: re-deriva lo que ya estaba escrito. Moverlos haría parecer fresca una consulta
# a la SEC que no ocurrió, y sacaría a la fila de la cola de vencidos sin haberla consultado.
SQL_RECLASIFICAR_FONDO = (
    "UPDATE public.perfil_renta_variable SET estrategia_etf = $2, region_etf = $3 WHERE ticker = $1"
)


async def nombres_persistidos(conn: Any) -> list[tuple[str, str]]:
    """`(ticker, nombre_largo)` de toda fila que tenga nombre. Sin nombre no hay nada que re-derivar
    —ni estrategia ni geografía—, así que esas filas no se leen ni se escriben."""
    filas = await conn.fetch(SQL_NOMBRES_PERSISTIDOS)
    return [(fila["ticker"], fila["nombre_largo"]) for fila in filas]


async def guardar_reclasificacion(
    conn: Any, filas: Sequence[tuple[str, str | None, str | None]]
) -> None:
    """Escribe `(ticker, estrategia_etf, region_etf)` de a lotes, en una sola transacción.

    Va en bloque y no fila por fila —al revés que `guardar_clasificacion`— porque acá no hay fuente
    externa que pueda cortar a mitad de camino: es un parser sobre datos que ya están en la base y
    tarda lo que tarda un UPDATE. Un corte parcial dejaría media tabla con el vocabulario nuevo y
    media con el viejo, sin nada que lo declarara.
    """
    if not filas:
        return
    async with conn.transaction():
        await conn.executemany(SQL_RECLASIFICAR_FONDO, list(filas))
