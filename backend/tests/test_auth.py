"""`GET /api/v1/auth/me`: el endpoint que confirma la sesión contra el JWT de Supabase Auth.

No prueba el aislamiento por asesor -eso es `test_auth_integration.py`, contra la base real-. Acá
se prueba el contrato HTTP de la dependencia `get_usuario_actual`: qué responde con o sin token,
con un token vencido, y qué pasa si no se puede traer la clave de firma del proyecto.

Los tokens se firman con una clave EC real y se verifican contra su clave pública servida como
JWKS, igual que en `test_seguridad.py` y por el mismo motivo: firmarlos con un secreto simétrico
inventado hacía que estos tests pasaran mientras el backend rechazaba todas las sesiones reales.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI

from app.core.seguridad import AUDIENCIA_ESPERADA, cliente_jwks
from tests.conftest import FakeConnection, cliente
from tests.test_seguridad import CLAVE, CLAVE_AJENA, KID, _jwks

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
    return jwt.encode(payload, CLAVE, algorithm="ES256", headers={"kid": KID})


@pytest.fixture(autouse=True)
def con_jwks_del_proyecto(monkeypatch: pytest.MonkeyPatch):
    """El JWKS del proyecto, servido sin salir a la red. No hay ningún secreto que configurar:
    la clave con la que se verifica una firma asimétrica es pública."""
    cliente_jwks.cache_clear()
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: _jwks(CLAVE))
    yield
    cliente_jwks.cache_clear()


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
    token_ajeno = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": AUDIENCIA_ESPERADA,
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        CLAVE_AJENA,
        algorithm="ES256",
        headers={"kid": KID},
    )
    app = crear_app(FakeConnection())

    async with cliente(app) as c:
        respuesta = await c.get(RUTA, headers={"Authorization": f"Bearer {token_ajeno}"})

    assert respuesta.status_code == 401


async def test_si_no_se_puede_traer_la_clave_de_firma_responde_503(
    crear_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 y no 401: el que falló es el servicio, no la sesión. Un 401 acá mandaría al asesor a
    loguearse de nuevo para volver a chocarse con lo mismo."""
    cliente_jwks.cache_clear()

    def _explota(self):
        raise OSError("no hay red")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _explota)
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
