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
"""

from typing import Any

from app.universo.segmentacion import CLASES_RENTA_VARIABLE

VISTA_UNIVERSO = "public.resumen"
TABLA_INSTRUMENTOS = "public.instrumentos"
TABLA_PUNTAS = "public.puntas"

COLUMNAS_VISTA: tuple[str, ...] = (
    "ticker",
    "clase_activo",
    "lastPrice",
    "effectiveVolume",
    "cierre_anterior",
    # Experimento data912: de dónde salió el precio de esta fila. Ver `universo/lectura.py`.
    "fuente",
)
COLUMNAS_INSTRUMENTOS: tuple[str, ...] = ("moneda_cotizacion",)
COLUMNAS_PUNTAS: tuple[str, ...] = ("px_bid", "px_ask", "operaciones")

_SELECT = ", ".join(
    [f'u."{c}"' for c in COLUMNAS_VISTA]
    + [f'i."{c}"' for c in COLUMNAS_INSTRUMENTOS]
    + [f'pt."{c}"' for c in COLUMNAS_PUNTAS]
)

_CLASES = ", ".join(f"'{c}'" for c in CLASES_RENTA_VARIABLE)

SQL_RENTA_VARIABLE = (
    f"SELECT {_SELECT} FROM {VISTA_UNIVERSO} u "
    f"LEFT JOIN {TABLA_INSTRUMENTOS} i ON i.ticker = u.ticker "
    "LEFT JOIN LATERAL ("
    f"    SELECT px_bid, px_ask, operaciones FROM {TABLA_PUNTAS} p"
    "     WHERE p.ticker = u.ticker ORDER BY p.capturado_en DESC LIMIT 1"
    ") pt ON true "
    f"WHERE u.clase_activo IN ({_CLASES}) "
    "ORDER BY u.ticker"
)


async def leer_renta_variable(conn: Any) -> list[dict[str, Any]]:
    """Acciones y CEDEARs del universo consolidado, con puntas y moneda de cotización."""
    filas = await conn.fetch(SQL_RENTA_VARIABLE)
    return [dict(fila) for fila in filas]
