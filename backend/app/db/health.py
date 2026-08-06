"""Consultas que sostienen el endpoint de salud.

El timestamp del último snapshot de mercado se lee de la tabla de precios, que recién existe a
partir de F-002. Mientras no exista, se devuelve vacío con una advertencia que la nombra: un
health que inventa una hora de snapshot es peor que uno que admite no tenerla.
"""

from datetime import datetime
from typing import Any

# F-002 define el esquema de mercado. Si la tabla o la columna cambian de nombre, este es el
# único lugar del backend que hay que tocar.
TABLA_PRECIOS = "public.precios"
COLUMNA_SNAPSHOT = "capturado_en"

_SQL_PING = "SELECT 1"
_SQL_TABLA_EXISTE = "SELECT to_regclass($1)"
_SQL_COLUMNA_EXISTE = """
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = split_part($1, '.', 1)
      AND table_name = split_part($1, '.', 2)
      AND column_name = $2
"""

AVISO_SIN_TABLA = (
    f"La tabla {TABLA_PRECIOS} todavía no existe (la crea F-002): "
    "no hay hora de último snapshot de mercado para informar."
)
AVISO_SIN_COLUMNA = (
    f"La tabla {TABLA_PRECIOS} existe pero no tiene la columna {COLUMNA_SNAPSHOT}: "
    "no hay hora de último snapshot de mercado para informar."
)
AVISO_SIN_DATOS = (
    f"La tabla {TABLA_PRECIOS} está vacía: todavía no corrió ninguna ingesta de mercado."
)


async def check_database(conn: Any) -> None:
    """Verifica que la conexión responda. Propaga la excepción si no."""
    await conn.fetchval(_SQL_PING)


async def get_last_snapshot(conn: Any) -> tuple[datetime | None, list[str]]:
    """Hora del último snapshot de mercado, o vacío con el motivo explicado."""
    if await conn.fetchval(_SQL_TABLA_EXISTE, TABLA_PRECIOS) is None:
        return None, [AVISO_SIN_TABLA]

    if await conn.fetchval(_SQL_COLUMNA_EXISTE, TABLA_PRECIOS, COLUMNA_SNAPSHOT) is None:
        return None, [AVISO_SIN_COLUMNA]

    # Interpolación de identificadores, no de datos: ambos son constantes de este módulo.
    ultimo = await conn.fetchval(f"SELECT max({COLUMNA_SNAPSHOT}) FROM {TABLA_PRECIOS}")
    if ultimo is None:
        return None, [AVISO_SIN_DATOS]
    return ultimo, []
