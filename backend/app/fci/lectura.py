"""SQL propio para los fondos comunes de inversión — F-057. Sólo SQL, sin decidir nada.

`public.fci` no pasa por `segmentar()` ni por ninguna lectura del universo: no es una especie
negociable, no tiene puntas ni volumen, y agruparla con renta fija o renta variable violaría la
regla 2 (naturaleza de rendimiento distinta). Mismo precedente que `renta_variable/lectura.py` y
`posiciones/lectura.py`: lectura aparte para un universo que nunca comparte tabla con el resto.
"""

from collections.abc import Sequence
from typing import Any

TABLA_FCI = "public.fci"
TABLA_PLANILLA = "public.fci_planilla"

SQL_SEGMENTOS = f"""
SELECT tipo_renta,
       COUNT(*) AS cantidad,
       ARRAY_AGG(DISTINCT moneda ORDER BY moneda) AS monedas
  FROM {TABLA_FCI}
 GROUP BY tipo_renta
 ORDER BY tipo_renta
"""

SQL_PLANILLA = f"""
SELECT fecha_planilla, fecha_cierre_anterior, fecha_base_mes, fecha_base_anio, fecha_base_12m,
       total_filas, capturado_en
  FROM {TABLA_PLANILLA}
 WHERE id = true
"""

SQL_FONDO = f"SELECT * FROM {TABLA_FCI} WHERE codigo_cafci = $1"


def _sql_fondos(tipo_renta: str | None, moneda: str | None) -> tuple[str, list[Any]]:
    condiciones: list[str] = []
    parametros: list[Any] = []
    if tipo_renta is not None:
        parametros.append(tipo_renta)
        condiciones.append(f"tipo_renta = ${len(parametros)}")
    if moneda is not None:
        parametros.append(moneda)
        condiciones.append(f"moneda = ${len(parametros)}")

    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    sql = f"SELECT * FROM {TABLA_FCI}{where} ORDER BY codigo_cafci"
    return sql, parametros


async def leer_segmentos(conn: Any) -> list[dict[str, Any]]:
    """Tipos de renta presentes hoy, con cuántos fondos tiene cada uno y en qué monedas cotizan."""
    filas = await conn.fetch(SQL_SEGMENTOS)
    return [dict(fila) for fila in filas]


async def leer_planilla(conn: Any) -> dict[str, Any] | None:
    """El singleton de la última planilla ingerida, o `None` si la ingesta nunca corrió."""
    fila = await conn.fetchrow(SQL_PLANILLA)
    return dict(fila) if fila else None


async def leer_fondos(
    conn: Any, *, tipo_renta: str | None = None, moneda: str | None = None
) -> list[dict[str, Any]]:
    sql, parametros = _sql_fondos(tipo_renta, moneda)
    filas = await conn.fetch(sql, *parametros)
    return [dict(fila) for fila in filas]


async def leer_fondo(conn: Any, codigo_cafci: str) -> dict[str, Any] | None:
    fila = await conn.fetchrow(SQL_FONDO, codigo_cafci)
    return dict(fila) if fila else None


SQL_FONDOS_POR_CODIGOS = f"SELECT * FROM {TABLA_FCI} WHERE codigo_cafci = ANY($1)"


async def leer_fondos_por_codigos(conn: Any, codigos: Sequence[str]) -> list[dict[str, Any]]:
    """El lookup exacto de F-046: sólo los fondos cuyo `codigo_cafci` está en `codigos`, tal cual.

    Se usa para resolver una cartera cargada contra `public.fci` sin traer las 4.251 filas del
    universo entero — la cartera de un cliente tiene, como mucho, unas pocas decenas de posiciones.
    """
    if not codigos:
        return []
    filas = await conn.fetch(SQL_FONDOS_POR_CODIGOS, list(codigos))
    return [dict(fila) for fila in filas]
