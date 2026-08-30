"""SQL propio para renta variable — F-052. Sólo SQL, sin decidir nada.

`segmentar()` descarta la renta variable *antes* de segmentar (`app/universo/segmentacion.py`):
una acción no tiene TIR, ni duración, ni cronograma, y `Segmentacion.renta_variable` es apenas un
contador. Por eso nunca llega a `vista_viva` ni a ningún endpoint de `/universo`, y esta lectura
existe aparte — mismo precedente que `posiciones/lectura.py`, que lee directo por la misma razón:
meter una acción en `EspecieUniverso` explota, porque `.naturaleza` hace
`NATURALEZA_TASA[self.segmento]` y una acción no tiene segmento.

`cierre_anterior` es la columna 22 de la vista `resumen` (migración F-052).
`moneda_cotizacion` no está en la vista y se trae de `instrumentos` con el mismo LEFT JOIN que usa
`universo/lectura.py`. Las puntas salen del último snapshot de `public.puntas` con el mismo LATERAL
que la vista `resumen` usa para precios — primera lectura de esa tabla en todo el backend: se
escribe para toda la rueda desde F-007 y ninguna otra lectura la expone.

**Perfil de empresa.** `public.perfil_renta_variable` se suma con un LEFT JOIN más: no toda especie
tiene fila todavía (el job de clasificación es incremental, ver `clasificacion.py`), así que es
`LEFT` y no `INNER` — sin eso una especie recién agregada al universo desaparecería del listado
hasta que corriera el job. `fuente` y `capturado_en` de esa
tabla se alias-ean como `perfil_fuente`/`perfil_capturado_en`: `fuente` ya existe en
`COLUMNAS_VISTA` (la fuente del precio, BYMA/data912) y sin el alias `dict(fila)` se quedaría con
uno solo de los dos bajo la misma clave.
"""

from typing import Any

from app.universo.segmentacion import CLASES_RENTA_VARIABLE

VISTA_UNIVERSO = "public.resumen"
TABLA_INSTRUMENTOS = "public.instrumentos"
TABLA_PUNTAS = "public.puntas"
TABLA_PERFIL = "public.perfil_renta_variable"

COLUMNAS_VISTA: tuple[str, ...] = (
    "ticker",
    "clase_activo",
    "lastPrice",
    "effectiveVolume",
    "cierre_anterior",
    # Experimento data912: de dónde salió el precio de esta fila. Ver `universo/lectura.py`.
    "fuente",
    # OHLC de BYMA (13/08/2026): siempre de BYMA aunque `fuente` diga data912 — el overlay no los
    # pisa. Ver el `COMMENT ON COLUMN` de la migración `ohlc_byma_precios`.
    "precio_apertura",
    "precio_maximo",
    "precio_minimo",
    "vwap",
)
COLUMNAS_INSTRUMENTOS: tuple[str, ...] = ("moneda_cotizacion",)
COLUMNAS_PUNTAS: tuple[str, ...] = ("px_bid", "px_ask", "operaciones")
COLUMNAS_PERFIL: tuple[str, ...] = (
    "nombre_largo",
    # La clasificación de la SEC y de la tabla de CEDEARs de BYMA (13/08/2026). `fuente` declara
    # cuál escribió la fila.
    "sic_codigo",
    "sic_titulo",
    "sic_oficina",
    "division_cadena",
    "estrategia_etf",
    # F-078: la geografía que declara el nombre del fondo. Sale del mismo nombre que
    # `estrategia_etf` y con el mismo parser (`etfs.py`), y no del país curado — son dos ejes
    # distintos que conviven sin unificarse.
    "region_etf",
    "ratio_conversion",
    "mercado_origen",
)

_SELECT = ", ".join(
    [f'u."{c}"' for c in COLUMNAS_VISTA]
    + [f'i."{c}"' for c in COLUMNAS_INSTRUMENTOS]
    + [f'pt."{c}"' for c in COLUMNAS_PUNTAS]
    + [f'pf."{c}"' for c in COLUMNAS_PERFIL]
    + ['pf."fuente" AS "perfil_fuente"', 'pf."capturado_en" AS "perfil_capturado_en"']
)

_CLASES = ", ".join(f"'{c}'" for c in CLASES_RENTA_VARIABLE)

SQL_RENTA_VARIABLE = (
    f"SELECT {_SELECT} FROM {VISTA_UNIVERSO} u "
    f"LEFT JOIN {TABLA_INSTRUMENTOS} i ON i.ticker = u.ticker "
    "LEFT JOIN LATERAL ("
    f"    SELECT px_bid, px_ask, operaciones FROM {TABLA_PUNTAS} p"
    "     WHERE p.ticker = u.ticker ORDER BY p.capturado_en DESC LIMIT 1"
    ") pt ON true "
    f"LEFT JOIN {TABLA_PERFIL} pf ON pf.ticker = u.ticker "
    f"WHERE u.clase_activo IN ({_CLASES}) "
    "ORDER BY u.ticker"
)


async def leer_renta_variable(conn: Any) -> list[dict[str, Any]]:
    """Acciones y CEDEARs del universo consolidado, con puntas y moneda de cotización."""
    filas = await conn.fetch(SQL_RENTA_VARIABLE)
    return [dict(fila) for fila in filas]
