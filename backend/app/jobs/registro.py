"""Registro auditable de cada corrida del job de ingesta: hora de inicio, duración, filas por
fuente y alertas emitidas. Vive en `public.corridas_ingesta` — ver la migración de F-008— y es lo
que F-013 va a leer para la barra de estado del dato.

`filas_por_fuente` y `alertas` son `jsonb`: asyncpg no serializa dicts a JSON solo, así que acá se
hace a mano con `json.dumps`/`json.loads` en vez de depender de un codec global que afectaría a
cualquier otra consulta del pool.
"""

import json
from datetime import datetime
from enum import StrEnum
from typing import Any


class TipoCorrida(StrEnum):
    MATINAL = "matinal"
    REFRESH = "refresh"
    FCI = "fci"
    """F-057: la corrida manual de la planilla de CAFCI (`POST /jobs/fci`). Distinta de `matinal`
    porque no toca BYMA/data912/IAMC ni la consolidación — sólo la tabla `fci`."""


class EstadoCorrida(StrEnum):
    COMPLETA = "completa"
    """Todas las fuentes que la corrida usa respondieron sin error."""

    PARCIAL = "parcial"
    """Al menos una fuente aportó algo, pero no todas: lo que llegó se persistió igual."""

    FALLIDA = "fallida"
    """Ninguna fuente aportó una fila. La corrida corrió pero no dejó nada nuevo."""


SQL_INSERTAR = """
INSERT INTO public.corridas_ingesta
    (tipo, iniciado_en, finalizado_en, duracion_ms, filas_por_fuente, alertas, estado)
VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7)
RETURNING id, tipo, iniciado_en, finalizado_en, duracion_ms, filas_por_fuente, alertas, estado
"""

SQL_LISTAR = """
SELECT id, tipo, iniciado_en, finalizado_en, duracion_ms, filas_por_fuente, alertas, estado
  FROM public.corridas_ingesta
 ORDER BY iniciado_en DESC
 LIMIT $1
"""

SQL_ULTIMA = """
SELECT id, tipo, iniciado_en, finalizado_en, duracion_ms, filas_por_fuente, alertas, estado
  FROM public.corridas_ingesta
 ORDER BY iniciado_en DESC
 LIMIT 1
"""


def _como_dict(fila: Any) -> dict[str, object]:
    datos = dict(fila)
    datos["filas_por_fuente"] = json.loads(datos["filas_por_fuente"])
    datos["alertas"] = json.loads(datos["alertas"])
    datos["iniciado_en"] = datos["iniciado_en"].isoformat()
    datos["finalizado_en"] = datos["finalizado_en"].isoformat()
    return datos


async def registrar_corrida(
    conn: Any,
    *,
    tipo: str,
    iniciado_en: datetime,
    finalizado_en: datetime,
    filas_por_fuente: dict[str, int],
    alertas: list[dict[str, object]],
    estado: str,
) -> dict[str, object]:
    """Escribe una fila en `corridas_ingesta` y devuelve lo que quedó, ya como dict serializable.

    `duracion_ms` se calcula acá, de las dos fechas, en vez de que cada llamador lo derive por su
    cuenta y arriesgue redondear distinto.
    """
    duracion_ms = round((finalizado_en - iniciado_en).total_seconds() * 1000)
    fila = await conn.fetchrow(
        SQL_INSERTAR,
        tipo,
        iniciado_en,
        finalizado_en,
        duracion_ms,
        json.dumps(filas_por_fuente),
        json.dumps(alertas),
        estado,
    )
    return _como_dict(fila)


async def listar_corridas(conn: Any, *, limite: int = 20) -> list[dict[str, object]]:
    filas = await conn.fetch(SQL_LISTAR, limite)
    return [_como_dict(fila) for fila in filas]


async def ultima_corrida(conn: Any) -> dict[str, object] | None:
    fila = await conn.fetchrow(SQL_ULTIMA)
    return _como_dict(fila) if fila else None
