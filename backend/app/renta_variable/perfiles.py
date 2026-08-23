"""Lectura y escritura de `public.perfil_renta_variable`.

Sólo SQL, sin decidir nada: qué papeles están pendientes de clasificar y cómo se persiste un
resultado. La decisión de cuándo correr, a qué ritmo y qué hacer con un 429 de la fuente vive en
`clasificacion.py`.
"""

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
    " estrategia_etf, ratio_conversion, mercado_origen, fuente, capturado_en) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
    "ON CONFLICT (ticker) DO UPDATE SET "
    # `nombre_largo` con COALESCE y no pisado: la SEC no lo publica para todo papel, y la lista de
    # CEDEARs de BYMA sí lo trae para algunos — perder el que ya había sería un retroceso.
    "nombre_largo = COALESCE(EXCLUDED.nombre_largo, public.perfil_renta_variable.nombre_largo), "
    "sic_codigo = EXCLUDED.sic_codigo, "
    "sic_titulo = EXCLUDED.sic_titulo, "
    "sic_oficina = EXCLUDED.sic_oficina, "
    "division_cadena = EXCLUDED.division_cadena, "
    "estrategia_etf = EXCLUDED.estrategia_etf, "
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
        ratio_conversion,
        mercado_origen,
        fuente,
        capturado_en,
    )
