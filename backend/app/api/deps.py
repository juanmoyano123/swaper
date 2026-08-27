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

`cron_o_asesor` (Tanda 3) es la cuarta, y es la puerta de los endpoints que disparan ingestas.
Acepta dos credenciales distintas por el mismo header: el secreto del cron externo o el JWT de un
asesor logueado. Ver su docstring para por qué no hay ambigüedad posible entre las dos.
"""

import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any

import structlog
from fastapi import Depends, Header, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings, get_settings
from app.core.seguridad import (
    ClaveDeFirmaNoDisponible,
    TokenExpirado,
    TokenInvalido,
    UsuarioAutenticado,
    verificar_token,
)

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

# Lo que ve quien manda una credencial que no abre ninguno de los dos caminos de `cron_o_asesor`.
# Es deliberadamente neutro: decir "el token de cron no coincide" o "el JWT está vencido" le
# confirmaría a quien prueba a ciegas cuál de los dos formatos está tanteando.
MENSAJE_CREDENCIAL_RECHAZADA = "La credencial no es válida."


async def _asesor_del_token(
    settings: Settings, token: str, *, detalle_401: str | None = None
) -> UsuarioAutenticado:
    """Verifica un JWT de sesión y traduce cada motivo de rechazo a su status HTTP.

    Vive separado porque lo usan las dos dependencias que aceptan sesión de asesor. Con el bloque
    duplicado, nada impediría que dentro de un tiempo un `ClaveDeFirmaNoDisponible` respondiera
    503 en una y 401 en la otra —que es justo la confusión que F-014 se tomó el trabajo de
    evitar—, y el bug viviría en la mitad que nadie mira.

    `detalle_401` reemplaza el mensaje de ambos rechazos de token. Existe porque `cron_o_asesor`
    necesita un mensaje neutro: ahí el JWT es sólo uno de los dos caminos posibles, y contar cuál
    falló es información que el que golpea la puerta no debería recibir.
    """
    try:
        # `verificar_token` bloquea la primera vez, cuando trae el JWKS del proyecto por HTTP.
        # Después queda cacheado en memoria, pero el event loop no se entera de esa distinción:
        # una sola llamada bloqueante frena todos los requests en vuelo.
        return await run_in_threadpool(verificar_token, token, settings.supabase_url)
    except TokenExpirado as exc:
        raise HTTPException(
            status_code=401, detail=detalle_401 or "La sesión expiró. Volvé a iniciar sesión."
        ) from exc
    except TokenInvalido as exc:
        raise HTTPException(
            status_code=401, detail=detalle_401 or "La sesión no es válida."
        ) from exc
    except ClaveDeFirmaNoDisponible as exc:
        # 503 y no 401: el que falló es este servicio, no la sesión del asesor. Devolver 401 lo
        # mandaría a loguearse de nuevo para volver a fallar igual.
        raise HTTPException(
            status_code=503,
            detail="El servicio no puede validar sesiones en este momento.",
        ) from exc


@dataclass(frozen=True)
class Invocante:
    """Quién disparó un job: un asesor logueado, o el cron externo.

    `usuario=None` significa cron, y no "no sabemos": los dos caminos de `cron_o_asesor` son
    excluyentes, y el único que llega sin usuario es el del token de cron. Los endpoints la usan
    hoy sólo como gate —nadie mira el contenido—, pero el dato queda disponible para el día que
    haga falta registrar en la corrida quién la pidió.
    """

    usuario: UsuarioAutenticado | None

    @property
    def es_cron(self) -> bool:
        return self.usuario is None


async def cron_o_asesor(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> Invocante:
    """La puerta de los endpoints que disparan ingestas: token de cron **o** sesión de asesor.

    Hasta el 26/08/2026 `POST /api/v1/jobs/*` y `POST /api/v1/consolidar` no pedían nada:
    cualquiera con la URL del deploy podía forzar una corrida completa contra BYMA y escribir en
    la base. Los dos consumidores legítimos son el cron externo, que no tiene sesión de nadie, y
    el frontend logueado, que sí — de ahí que se acepten dos credenciales por el mismo header.

    **El chequeo del secreto va primero, y el orden importa.** Si se probara el JWT antes, cada
    tick del cron mandaría el `CRON_SECRET` a decodificar contra el JWKS de Supabase y dejaría un
    "token inválido" en el log en cada corrida: ruido periódico e indistinguible de un intento
    real de entrar.

    **No hay ambigüedad posible entre los dos caminos.** Un `CRON_SECRET` no es un JWT —no tiene
    las tres partes separadas por punto ni una firma que verifique contra el JWKS del proyecto—,
    así que jamás pasaría por asesor; y un JWT genuino no coincide byte a byte con el secreto,
    así que jamás pasaría por cron. Con `cron_secret` sin configurar, la rama de cron ni se
    evalúa: no se compara contra vacío ni contra None, se saltea entera.
    """
    if not authorization or not authorization.startswith(PREFIJO_BEARER):
        raise HTTPException(status_code=401, detail="Falta la credencial de autorización.")

    token = authorization.removeprefix(PREFIJO_BEARER).strip()

    # `compare_digest` y no `==`: comparar dos strings con `==` corta en el primer byte distinto,
    # y ese tiempo desigual es lo que permite adivinar un secreto carácter por carácter.
    if settings.cron_secret and secrets.compare_digest(token, settings.cron_secret):
        return Invocante(usuario=None)

    return Invocante(
        usuario=await _asesor_del_token(settings, token, detalle_401=MENSAJE_CREDENCIAL_RECHAZADA)
    )


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

    token = authorization.removeprefix(PREFIJO_BEARER).strip()
    # Sin `detalle_401`: acá el único camino posible es la sesión, así que nombrar por qué falló
    # no filtra nada y le dice al asesor si tiene que reloguearse o avisar que algo anda mal.
    return await _asesor_del_token(settings, token)
