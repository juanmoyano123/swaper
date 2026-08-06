"""`app/core/seguridad.py`: la verificación del JWT que emite Supabase Auth, sin tocar la base.

El aislamiento entre asesores lo prueba `test_auth_integration.py` contra RLS. Acá se prueba la
mitad que sí puede probarse offline: que un token genuino se acepte y que uno roto, vencido, con
otra audiencia o sin `sub` se rechace con el tipo de error correcto.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.core.seguridad import (
    AUDIENCIA_ESPERADA,
    TokenExpirado,
    TokenInvalido,
    UsuarioAutenticado,
    verificar_token,
)

SECRETO = "el-secreto-de-prueba-no-es-el-real"


def _token(*, secreto: str = SECRETO, segundos_para_vencer: float = 3600, **claims_extra) -> str:
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": "asesor@example.com",
        "aud": AUDIENCIA_ESPERADA,
        "role": "authenticated",
        "iat": ahora,
        "exp": ahora + timedelta(seconds=segundos_para_vencer),
        **claims_extra,
    }
    return jwt.encode(payload, secreto, algorithm="HS256")


def test_un_token_genuino_devuelve_el_usuario() -> None:
    id_esperado = uuid4()
    token = _token(sub=str(id_esperado), email="lucia@example.com")

    usuario = verificar_token(token, SECRETO)

    assert usuario == UsuarioAutenticado(id=id_esperado, email="lucia@example.com")


def test_un_token_sin_email_igual_verifica() -> None:
    # Supabase siempre manda `email`, pero el claim no es lo que identifica al asesor -eso es
    # `sub`- y no hay motivo para que su ausencia tire abajo la verificación.
    token = _token()
    payload = jwt.decode(token, SECRETO, algorithms=["HS256"], audience=AUDIENCIA_ESPERADA)
    del payload["email"]
    token_sin_email = jwt.encode(payload, SECRETO, algorithm="HS256")

    usuario = verificar_token(token_sin_email, SECRETO)

    assert usuario.email is None


def test_un_token_vencido_es_token_expirado() -> None:
    token = _token(segundos_para_vencer=-10)

    with pytest.raises(TokenExpirado):
        verificar_token(token, SECRETO)


def test_un_token_firmado_con_otro_secreto_es_invalido() -> None:
    token = _token(secreto="otro-secreto-cualquiera")

    with pytest.raises(TokenInvalido):
        verificar_token(token, SECRETO)


def test_un_token_con_otra_audiencia_es_invalido() -> None:
    # Evita que un JWT válido para otro proyecto de Supabase que compartiera el mismo secreto se
    # acepte acá.
    token = _token(aud="otro-proyecto")

    with pytest.raises(TokenInvalido):
        verificar_token(token, SECRETO)


def test_un_token_sin_sub_es_invalido() -> None:
    ahora = datetime.now(UTC)
    payload = {
        "aud": AUDIENCIA_ESPERADA,
        "iat": ahora,
        "exp": ahora + timedelta(hours=1),
    }
    token = jwt.encode(payload, SECRETO, algorithm="HS256")

    with pytest.raises(TokenInvalido):
        verificar_token(token, SECRETO)


def test_un_texto_que_no_es_un_jwt_es_invalido() -> None:
    with pytest.raises(TokenInvalido):
        verificar_token("esto-no-es-un-token", SECRETO)
