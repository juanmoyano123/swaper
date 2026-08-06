"""Verificación de la sesión que emite Supabase Auth (F-014).

El backend no arma tokens ni maneja contraseñas: el login corre en el frontend contra Supabase
Auth con la anon key, y acá sólo se verifica que el JWT que llega en el header sea genuino y no
haya expirado. La verificación es HS256 contra `supabase_jwt_secret` —el mismo secreto que firma
en el panel de Supabase— y no llama a ningún servicio externo: es la razón por la que validar la
sesión no le agrega una vuelta de red a cada request autenticado.

Esto NO es el aislamiento entre asesores. Ese lo hace Row Level Security en PostgreSQL, contra
`user_id`, y sigue valiendo aunque este módulo tuviera un bug. Lo que hay acá es sólo saber quién
está pidiendo, para poder cortar con 401 antes de tocar la base.
"""

from dataclasses import dataclass
from uuid import UUID

import jwt

# El "aud" que Supabase pone en todo JWT de sesión de usuario. Un token con otra audiencia —por
# ejemplo, uno emitido para otro proyecto de Supabase con el mismo secreto— se rechaza acá.
AUDIENCIA_ESPERADA = "authenticated"


class TokenInvalido(Exception):
    """El token no verifica: firma incorrecta, formato roto, o falta `aud`/`sub`."""


class TokenExpirado(Exception):
    """El token es genuino pero venció.

    Se distingue de `TokenInvalido` porque el mensaje que ve el asesor es distinto: uno dice
    "iniciá sesión de nuevo" —cosa esperable, pasa todos los días—; el otro no debería pasarle
    nunca y amerita revisar qué está mandando el cliente.
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


def verificar_token(token: str, secreto: str) -> UsuarioAutenticado:
    """Decodifica y valida el JWT de sesión.

    Lanza `TokenExpirado` si venció y `TokenInvalido` para cualquier otro motivo de rechazo
    (firma, formato, audiencia, o un `sub` que no es un UUID).
    """
    try:
        claims = jwt.decode(token, secreto, algorithms=["HS256"], audience=AUDIENCIA_ESPERADA)
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
