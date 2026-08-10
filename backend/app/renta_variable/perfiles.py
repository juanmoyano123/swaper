"""Lectura y escritura de `public.perfil_renta_variable` — Etapa 4 del rediseño del armador.

Sólo SQL, sin decidir nada: qué tickers están pendientes de enriquecer y cómo se persiste un
resultado. La decisión de cuándo correr, a qué ritmo y qué hacer con un 429 de la fuente vive en
`enriquecimiento.py`; este módulo no sabe que existe Yahoo.
"""

from datetime import datetime
from typing import Any

from app.universo.segmentacion import CLASES_RENTA_VARIABLE

# El perfil de una empresa (nombre, sector, país) cambia lento: una fila de hace un mes sigue
# sirviendo. Ni tan corto que reprocese todo el universo cada corrida, ni tan largo que un cambio
# real (una fusión, una escisión) tarde meses en reflejarse.
DIAS_VENCIMIENTO = 30

_CLASES = ", ".join(f"'{c}'" for c in CLASES_RENTA_VARIABLE)

# Pendiente = sin fila todavía, o con una fila más vieja que `DIAS_VENCIMIENTO`. `$1` es la cantidad
# de días: se pasa como parámetro y no se interpola, para que un test pueda variarlo sin tocar SQL.
SQL_TICKERS_PENDIENTES = (
    "SELECT i.ticker FROM public.instrumentos i "
    "LEFT JOIN public.perfil_renta_variable p ON p.ticker = i.ticker "
    f"WHERE i.clase_activo IN ({_CLASES}) "
    "AND (p.ticker IS NULL OR p.capturado_en < now() - make_interval(days => $1::int)) "
    "ORDER BY i.ticker"
)

SQL_UPSERT = (
    "INSERT INTO public.perfil_renta_variable "
    "(ticker, nombre_corto, nombre_largo, sector, industria, pais, fuente, capturado_en) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8) "
    "ON CONFLICT (ticker) DO UPDATE SET "
    "nombre_corto = EXCLUDED.nombre_corto, "
    "nombre_largo = EXCLUDED.nombre_largo, "
    "sector = EXCLUDED.sector, "
    "industria = EXCLUDED.industria, "
    "pais = EXCLUDED.pais, "
    "fuente = EXCLUDED.fuente, "
    "capturado_en = EXCLUDED.capturado_en"
)


async def tickers_pendientes(conn: Any, *, dias_vencimiento: int = DIAS_VENCIMIENTO) -> list[str]:
    """Tickers de renta variable sin perfil, o con uno de hace más de `dias_vencimiento` días."""
    filas = await conn.fetch(SQL_TICKERS_PENDIENTES, dias_vencimiento)
    return [fila["ticker"] for fila in filas]


async def guardar_perfil(
    conn: Any,
    ticker: str,
    *,
    nombre_corto: str | None,
    nombre_largo: str | None,
    sector: str | None,
    industria: str | None,
    pais: str | None,
    fuente: str,
    capturado_en: datetime,
) -> None:
    """Upsert de una fila. El job persiste ticker a ticker (no al final de la corrida) para que un
    corte a mitad de camino no pierda lo que ya se trajo — ver `enriquecimiento.py`."""
    await conn.execute(
        SQL_UPSERT,
        ticker,
        nombre_corto,
        nombre_largo,
        sector,
        industria,
        pais,
        fuente,
        capturado_en,
    )
