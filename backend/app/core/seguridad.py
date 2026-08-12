"""Verificación de la sesión que emite Supabase Auth (F-014).

El backend no arma tokens ni maneja contraseñas: el login corre en el frontend contra Supabase
Auth con la anon key, y acá sólo se verifica que el JWT que llega en el header sea genuino y no
haya expirado.

**La verificación es asimétrica, contra el JWKS público del proyecto.** Supabase migró a JWT
Signing Keys: los tokens de sesión se firman con una clave EC (ES256) y lo que se publica en
`/auth/v1/.well-known/jwks.json` es la clave *pública* con la que se verifican. No hay ningún
secreto que guardar. Esto reemplaza a la verificación HS256 contra `SUPABASE_JWT_SECRET` que esta
feature usaba al construirse: ese secreto es el esquema anterior y hoy sólo firma las API keys
`anon` y `service_role`, no los tokens de usuario, así que verificar con él rechazaba todas las
sesiones genuinas. Se descubrió leyendo el JWKS real del proyecto, no con un test: los tests
firmaban sus propios tokens con el mismo algoritmo equivocado, así que pasaban siempre.

**`HS256` no está entre los algoritmos aceptados, y es deliberado.** Aceptar a la vez un algoritmo
simétrico y uno asimétrico es el ataque de confusión de algoritmo: quien conozca la clave pública
—que es pública— podría firmar un token con ella como si fuera un secreto HMAC, y la librería lo
validaría. La lista se fija acá y nunca sale del header del token.

Rotar la clave de firma en Supabase no requiere tocar nada: el JWKS publica la nueva y el `kid` de
cada token dice cuál lo firmó.

Esto NO es el aislamiento entre asesores. Ese lo hace Row Level Security en PostgreSQL, contra
`user_id`, y sigue valiendo aunque este módulo tuviera un bug. Lo que hay acá es sólo saber quién
está pidiendo, para poder cortar con 401 antes de tocar la base.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from jwt import PyJWKClient

# El "aud" que Supabase pone en todo JWT de sesión de usuario. Un token con otra audiencia —por
# ejemplo, uno emitido para otro proyecto de Supabase— se rechaza acá.
AUDIENCIA_ESPERADA = "authenticated"

# Sólo asimétricos. Ver el porqué en el docstring del módulo: mezclar HS256 con una clave pública
# es una vulnerabilidad, no una comodidad. ES256 es lo que firma Supabase hoy; RS256 queda
# aceptado porque es la otra opción que ofrece el panel y cambiarla no debería romper el backend.
ALGORITMOS_ACEPTADOS = ("ES256", "RS256")

RUTA_JWKS = "/auth/v1/.well-known/jwks.json"


class TokenInvalido(Exception):
    """El token no verifica: firma incorrecta, formato roto, o falta `aud`/`sub`."""


class TokenExpirado(Exception):
    """El token es genuino pero venció.

    Se distingue de `TokenInvalido` porque el mensaje que ve el asesor es distinto: uno dice
    "iniciá sesión de nuevo" —cosa esperable, pasa todos los días—; el otro no debería pasarle
    nunca y amerita revisar qué está mandando el cliente.
    """


class ClaveDeFirmaNoDisponible(Exception):
    """No se pudo traer el JWKS del proyecto: sin él no se puede verificar ninguna sesión.

    Es distinto de un token inválido y por eso es su propia excepción: acá el que falla es
    nuestro servicio o la red, no el cliente, y responder 401 haría que un asesor con la sesión
    perfectamente válida crea que tiene que volver a loguearse.
    """


@dataclass(frozen=True)
class UsuarioAutenticado:
    """El contexto de usuario que un endpoint necesita: quién es, nada más.

    No carga nada de `auth.users`: los claims del JWT ya traen lo que hace falta, y pedirle una
    consulta a la base a cada request autenticado sería pagar una vuelta que no aporta nada — el
    aislamiento por asesor lo hace RLS adentro de la base, no este objeto.
    """

    id: UUID
    email: str | None


@lru_cache
def cliente_jwks(url_supabase: str) -> PyJWKClient:
    """El cliente de JWKS del proyecto, uno solo por URL y para toda la vida del proceso.

    `cache_keys=True` es obligatorio y no una optimización: por defecto `PyJWKClient` **no**
    cachea, y sin eso cada request autenticado saldría a la red antes de validar el token. Lo
    detectó un test que cuenta las llamadas, porque el síntoma no es un error sino latencia.

    El `lru_cache` es por URL y no un global para que un test pueda apuntar a otro proyecto sin
    ensuciar al siguiente.
    """
    return PyJWKClient(url_supabase.rstrip("/") + RUTA_JWKS, cache_keys=True)


def verificar_token(token: str, url_supabase: str) -> UsuarioAutenticado:
    """Decodifica y valida el JWT de sesión contra la clave pública del proyecto.

    Lanza `TokenExpirado` si venció, `TokenInvalido` para cualquier otro motivo de rechazo
    (firma, formato, audiencia, o un `sub` que no es un UUID) y `ClaveDeFirmaNoDisponible` si no
    se pudo obtener el JWKS.

    **Bloquea**: la primera llamada trae el JWKS por HTTP. Quien la use desde código async tiene
    que sacarla del event loop.
    """
    try:
        clave = cliente_jwks(url_supabase).get_signing_key_from_jwt(token)
    except jwt.InvalidTokenError as exc:
        # Un token que ni siquiera se puede parsear muere acá, antes de llegar a la firma. Va
        # primero porque `DecodeError` es de la librería y no del cliente HTTP: si lo agarrara el
        # `except Exception` de abajo, un texto cualquiera mandado como token haría que el
        # servicio se declarara caído con 503 en vez de rechazar el request con 401.
        raise TokenInvalido(f"El token no es válido: {exc}") from exc
    except jwt.exceptions.PyJWKClientError as exc:
        # Un `kid` que no está en el JWKS entra por acá y tampoco es un problema nuestro: es un
        # token que no firmó este proyecto.
        if "Unable to find" in str(exc):
            raise TokenInvalido(f"El token no fue firmado por este proyecto: {exc}") from exc
        raise ClaveDeFirmaNoDisponible(f"No se pudo obtener la clave de firma: {exc}") from exc
    except Exception as exc:  # la red, el DNS, un 500 del proveedor
        raise ClaveDeFirmaNoDisponible(f"No se pudo obtener la clave de firma: {exc}") from exc

    try:
        claims = jwt.decode(
            token,
            clave.key,
            algorithms=list(ALGORITMOS_ACEPTADOS),
            audience=AUDIENCIA_ESPERADA,
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpirado("El token expiró.") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalido(f"El token no es válido: {exc}") from exc

    sub = claims.get("sub")
    if not sub:
        raise TokenInvalido("El token no trae el identificador del usuario (claim 'sub').")

    try:
        id_usuario = UUID(sub)
    except ValueError as exc:
        raise TokenInvalido("El claim 'sub' no es un UUID válido.") from exc

    return UsuarioAutenticado(id=id_usuario, email=claims.get("email"))
