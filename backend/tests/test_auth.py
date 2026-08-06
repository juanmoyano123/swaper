"""`GET /api/v1/auth/me`: el endpoint que confirma la sesión contra el JWT de Supabase Auth.

No prueba el aislamiento por asesor -eso es `test_auth_integration.py`, contra la base real-. Acá
se prueba el contrato HTTP de la dependencia `get_usuario_actual`: qué responde con o sin token,
con un token vencido, y qué pasa si el servicio no tiene configurado el secreto todavía.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.seguridad import AUDIENCIA_ESPERADA
from tests.conftest import FakeConnection, cliente

SECRETO = "el-secreto-de-prueba-no-es-el-real"
RUTA = "/api/v1/auth/me"


def _token(id_usuario, *, email: str | None = "asesor@example.com", vencido: bool = False) -> str:
    ahora = datetime.now(UTC)
    delta = timedelta(seconds=-10) if vencido else timedelta(hours=1)
    payload = {
        "sub": str(id_usuario),
        "aud": AUDIENCIA_ESPERADA,
        "role": "authenticated",
        "iat": ahora,
        "exp": ahora + delta,
    }
    if email is not None:
        payload["email"] = email
    return jwt.encode(payload, SECRETO, algorithm="HS256")


@pytest.fixture(autouse=True)
def con_jwt_secret_configurado(monkeypatch: pytest.MonkeyPatch):
    """El secreto es opcional en `Settings` -mismo patrón que Docta- y acá sí hace falta: es la
    feature que lo consume. Cada test que necesite probar el caso "no configurado" lo saca de
    nuevo con `monkeypatch.delenv`."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRETO)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_sin_header_de_autorizacion_responde_401(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(RUTA)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "unauthorized"


async def test_con_un_header_que_no_es_bearer_responde_401(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(RUTA, headers={"Authorization": "Basic algo"})

    assert respuesta.status_code == 401


async def test_con_un_token_genuino_devuelve_el_id_y_el_email(
    crear_app: Callable[..., FastAPI],
) -> None:
    id_usuario = uuid4()
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(
            RUTA, headers={"Authorization": f"Bearer {_token(id_usuario, email='lucia@x.com')}"}
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["id"] == str(id_usuario)
    assert cuerpo["email"] == "lucia@x.com"


async def test_con_un_token_vencido_responde_401_y_pide_reloguear(
    crear_app: Callable[..., FastAPI],
) -> None:
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(
            RUTA, headers={"Authorization": f"Bearer {_token(uuid4(), vencido=True)}"}
        )

    assert respuesta.status_code == 401
    assert "expiró" in respuesta.json()["error"]["message"]


async def test_con_un_token_con_otra_firma_responde_401(
    crear_app: Callable[..., FastAPI],
) -> None:
    id_usuario = uuid4()
    token_de_otro_secreto = jwt.encode(
        {
            "sub": str(id_usuario),
            "aud": AUDIENCIA_ESPERADA,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        "un-secreto-que-no-es-el-configurado",
        algorithm="HS256",
    )
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(RUTA, headers={"Authorization": f"Bearer {token_de_otro_secreto}"})

    assert respuesta.status_code == 401


async def test_sin_supabase_jwt_secret_configurado_responde_503(
    crear_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    get_settings.cache_clear()
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(RUTA, headers={"Authorization": f"Bearer {_token(uuid4())}"})

    assert respuesta.status_code == 503


async def test_no_consulta_la_base(crear_app: Callable[..., FastAPI]) -> None:
    """Todo lo que necesita viaja en el JWT: verificar la sesión no le pide nada a PostgreSQL."""
    conexion = FakeConnection()
    app = crear_app(conexion)

    async with cliente(app) as c:
        await c.get(RUTA, headers={"Authorization": f"Bearer {_token(uuid4())}"})

    assert conexion.consultas == []
