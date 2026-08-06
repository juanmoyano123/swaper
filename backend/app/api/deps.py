"""Dependencias compartidas por los endpoints.

Hay dos formas de pedir la base y la diferencia es deliberada:

- `get_db` es la que usan las features: si la base no está, el request muere con 503 y contrato
  de error uniforme, sin que cada endpoint tenga que acordarse de chequearlo.
- `get_db_optional` devuelve None en vez de fallar, y existe para `/health`, que tiene que poder
  *informar* que la base está caída en lugar de fallar por eso.

`get_usuario_actual` (F-014) es la tercera: quién hace el request, verificado contra el JWT de
Supabase Auth. Ojo con lo que NO es: no es el aislamiento entre asesores. Ese lo aplica Row Level
Security en PostgreSQL contra `user_id`, adentro de la base, y sigue valiendo aunque esta
dependencia tuviera un bug. Lo que aporta acá es simplemente poder cortar con 401 antes de tocar
la base cuando no hay sesión válida.
"""

from collections.abc import AsyncIterator
from typing import Annotated, Any

import structlog
from fastapi import Depends, Header, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.seguridad import TokenExpirado, TokenInvalido, UsuarioAutenticado, verificar_token

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


PREFIJO_BEARER = "Bearer "


async def get_usuario_actual(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> UsuarioAutenticado:
    """El asesor de la sesión actual, o 401 si no hay una sesión válida.

    No consulta la base: todo lo que necesita viaja en el JWT. Un endpoint que además necesite
    filtrar por `user_id` no lo hace con el `id` que devuelve esto —eso sería el filtro de cliente
    que la spec de F-014 prohíbe explícitamente— sino dejando que la conexión pase por RLS con el
    `user_id` de la fila. Esta dependencia es para lo que sí es legítimo resolver acá: cortar
    temprano si no hay sesión, y para lo que el propio backend necesite saber de quién es el
    request (logging, por ejemplo).
    """
    if not authorization or not authorization.startswith(PREFIJO_BEARER):
        raise HTTPException(status_code=401, detail="Falta el token de sesión.")

    if not settings.supabase_jwt_secret:
        # Mismo patrón que Docta en `app/ingesta/docta/url.py`: la variable es opcional en
        # `Settings` y se exige recién acá, en la feature que la consume.
        raise HTTPException(
            status_code=503,
            detail="El servicio no puede validar sesiones: falta configurar SUPABASE_JWT_SECRET.",
        )

    token = authorization.removeprefix(PREFIJO_BEARER).strip()
    try:
        return verificar_token(token, settings.supabase_jwt_secret)
    except TokenExpirado as exc:
        raise HTTPException(
            status_code=401, detail="La sesión expiró. Volvé a iniciar sesión."
        ) from exc
    except TokenInvalido as exc:
        raise HTTPException(status_code=401, detail="La sesión no es válida.") from exc
