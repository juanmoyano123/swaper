"""Consultas que sostienen el endpoint de salud.

El timestamp del último snapshot de mercado se lee de la tabla de precios, que recién existe a
partir de F-002. Mientras no exista, se devuelve vacío con una advertencia que la nombra: un
health que inventa una hora de snapshot es peor que uno que admite no tenerla.

La verificación de existencia va en una sola consulta —y no en tres— porque cada ida y vuelta
a la base cuesta un round-trip de red completo, y el health lo sondean la plataforma de hosting
y el contenedor cada pocos segundos.
"""

from datetime import datetime
from typing import Any

# F-002 define el esquema de mercado. Si la tabla o la columna cambian de nombre, este es el
# único lugar del backend que hay que tocar.
TABLA_PRECIOS = "public.precios"
COLUMNA_SNAPSHOT = "capturado_en"

# Verifica de un saque que la base responde, que la tabla existe y que tiene la columna.
_SQL_ESTADO = """
    SELECT
        to_regclass($1) IS NOT NULL AS tabla_existe,
        EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = split_part($1, '.', 1)
              AND table_name = split_part($1, '.', 2)
              AND column_name = $2
        ) AS columna_existe
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


async def get_last_snapshot(conn: Any) -> tuple[datetime | None, list[str]]:
    """Hora del último snapshot de mercado, o vacío con el motivo explicado.

    La consulta misma es la verificación de conectividad: si la base no responde, propaga la
    excepción y el endpoint la traduce en un 503. Mientras no exista la tabla —el estado real
    hasta F-002— resuelve en un solo viaje a la base.
    """
    estado = await conn.fetchrow(_SQL_ESTADO, TABLA_PRECIOS, COLUMNA_SNAPSHOT)

    if not estado["tabla_existe"]:
        return None, [AVISO_SIN_TABLA]
    if not estado["columna_existe"]:
        return None, [AVISO_SIN_COLUMNA]

    # Interpolación de identificadores, no de datos: ambos son constantes de este módulo.
    ultimo = await conn.fetchval(f"SELECT max({COLUMNA_SNAPSHOT}) FROM {TABLA_PRECIOS}")
    if ultimo is None:
        return None, [AVISO_SIN_DATOS]
    return ultimo, []
