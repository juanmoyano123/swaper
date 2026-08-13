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


# --- Clasificación de la SEC (13/08/2026) ---------------------------------------------------------
#
# Columnas aparte de las de Yahoo y con su propio upsert, no porque el dato sea de otra naturaleza
# —es el mismo perfil de la misma empresa— sino porque **las dos fuentes se pisarían**: un upsert
# que escribiera las once columnas de una vez borraría lo que la otra trajo cada vez que corre.
# Cada job escribe lo suyo y deja intacto lo ajeno.

SQL_UPSERT_SEC = (
    "INSERT INTO public.perfil_renta_variable "
    "(ticker, nombre_largo, sic_codigo, sic_titulo, sic_oficina, division_cadena, "
    " estrategia_etf, ratio_conversion, mercado_origen, fuente, capturado_en) "
    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11) "
    "ON CONFLICT (ticker) DO UPDATE SET "
    # `nombre_largo` con COALESCE y no pisado: si Yahoo alguna vez lo trajo y la SEC no lo tiene
    # para este papel, perder el que había sería un retroceso. El resto sí se pisa: son columnas
    # que sólo escribe esta fuente.
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

# Los papeles a clasificar, no las especies: `AAPL` una vez, y `AAPLC`/`AAPLD` heredan de su
# emisión. Se cuentan pendientes los que no tienen `sic_codigo` **ni** `estrategia_etf`: un ETF
# nunca va a tener SIC útil, y sin esta condición volvería a pedirse en cada corrida para siempre.
SQL_PAPELES_PENDIENTES_SEC = (
    "SELECT i.ticker FROM public.instrumentos i "
    "LEFT JOIN public.perfil_renta_variable p ON p.ticker = i.ticker "
    f"WHERE i.clase_activo IN ({_CLASES}) "
    "AND (p.ticker IS NULL "
    "     OR (p.sic_codigo IS NULL AND p.estrategia_etf IS NULL) "
    "     OR p.capturado_en < now() - make_interval(days => $1::int)) "
    "ORDER BY i.ticker"
)


async def papeles_pendientes_sec(
    conn: Any, *, dias_vencimiento: int = DIAS_VENCIMIENTO
) -> list[str]:
    """Tickers de renta variable sin clasificar por la SEC, o con una clasificación vencida."""
    filas = await conn.fetch(SQL_PAPELES_PENDIENTES_SEC, dias_vencimiento)
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
    """Upsert de la clasificación de un papel. Ticker a ticker, igual que `guardar_perfil`: un
    corte a mitad de corrida conserva lo que ya se trajo."""
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
