"""Dependencias compartidas por los endpoints.

Hay dos formas de pedir la base y la diferencia es deliberada:

- `get_db` es la que usan las features: si la base no está, el request muere con 503 y contrato
  de error uniforme, sin que cada endpoint tenga que acordarse de chequearlo.
- `get_db_optional` devuelve None en vez de fallar, y existe para `/health`, que tiene que poder
  *informar* que la base está caída en lugar de fallar por eso.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

import structlog
from fastapi import Depends, HTTPException, Request

logger = structlog.get_logger()

ACQUIRE_TIMEOUT_S = 5.0


async def get_db_optional(request: Request) -> AsyncIterator[Any | None]:
    pool = getattr(request.app.state, "pool", None)
    if pool is None:
        yield None
        return

    try:
        conn = await pool.acquire(timeout=ACQUIRE_TIMEOUT_S)
    except Exception as exc:
        logger.warning("db_conexion_fallida", error=str(exc), error_type=type(exc).__name__)
        yield None
        return

    try:
        yield conn
    finally:
        await pool.release(conn)


async def get_db(conn: Annotated[Any | None, Depends(get_db_optional)]) -> Any:
    if conn is None:
        raise HTTPException(status_code=503, detail="La base de datos no está disponible.")
    return conn
