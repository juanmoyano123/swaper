"""`cron_o_asesor`: la puerta de los endpoints que disparan ingestas (Tanda 3, 26/08/2026).

Hasta esa fecha `POST /api/v1/jobs/*` y `POST /api/v1/consolidar` estaban abiertos a internet en
el deploy: cualquiera con la URL podía forzar una corrida completa contra BYMA y escribir en la
base. Lo que se prueba acá es que la puerta abra para los dos consumidores legítimos —el cron
externo con su secreto, el frontend logueado con su JWT— y para nadie más.

Los tokens se firman con la clave EC de `test_seguridad.py` y se verifican contra su clave pública
servida como JWKS, por el mismo motivo que en `test_auth.py`: un token firmado con un algoritmo
inventado haría pasar estos tests mientras el backend rechaza las sesiones reales.

Los dos casos que más importan son los que no son obvios:

- **con `CRON_SECRET` sin configurar, el secreto no abre nada.** La setting es opcional y su
  ausencia cierra el camino del cron entero, en vez de dejarlo comparando contra vacío.
- **el 503 sigue siendo 503.** Si no se puede traer el JWKS, el que falló es este servicio y no la
  credencial; responder 401 mandaría a un asesor con la sesión perfectamente válida a loguearse de
  nuevo para volver a chocarse con lo mismo.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI

import app.api.v1.jobs as modulo_jobs
from app.core.config import get_settings
from app.core.seguridad import AUDIENCIA_ESPERADA, cliente_jwks
from tests.conftest import CRON_SECRET_DE_PRUEBA, FakeConnection, cliente
from tests.test_seguridad import CLAVE, KID, _jwks

RUTA_LECTURA = "/api/v1/jobs/corridas"
RUTA_MATINAL = "/api/v1/jobs/corridas/matinal"


class _FakeConexionCorridas(FakeConnection):
    """Historial vacío. Alcanza para que el endpoint devuelva 200 si la puerta lo dejó pasar."""

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self._registrar(query)
        return []


def _token_de_asesor(*, vencido: bool = False) -> str:
    ahora = datetime.now(UTC)
    delta = timedelta(seconds=-10) if vencido else timedelta(hours=1)
    return jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": AUDIENCIA_ESPERADA,
            "role": "authenticated",
            "email": "asesor@example.com",
            "iat": ahora,
            "exp": ahora + delta,
        },
        CLAVE,
        algorithm="ES256",
        headers={"kid": KID},
    )


def _bearer(credencial: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {credencial}"}


@pytest.fixture(autouse=True)
def con_jwks_del_proyecto(monkeypatch: pytest.MonkeyPatch):
    """El JWKS del proyecto servido sin salir a la red."""
    cliente_jwks.cache_clear()
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: _jwks(CLAVE))
    yield
    cliente_jwks.cache_clear()


@pytest.fixture
def sin_cron_secret(monkeypatch: pytest.MonkeyPatch):
    """El deploy al que no se le configuró `CRON_SECRET`.

    Se borra del entorno y se limpia la caché de settings *antes* de que el test arme la app: si
    se armara primero, `get_settings` ya habría quedado cacheada con el secreto puesto y el test
    estaría probando el escenario contrario al que dice probar.
    """
    monkeypatch.delenv("CRON_SECRET", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# --- Con CRON_SECRET configurado ----------------------------------------------------------------


async def test_el_token_de_cron_abre(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(CRON_SECRET_DE_PRUEBA))

    assert respuesta.status_code == 200


async def test_otro_secreto_no_abre(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer("cron-secret-equivocado"))

    assert respuesta.status_code == 401


async def test_el_jwt_de_un_asesor_tambien_abre(crear_app: Callable[..., FastAPI]) -> None:
    """El frontend logueado dispara los mismos endpoints y no tiene el secreto del cron."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(_token_de_asesor()))

    assert respuesta.status_code == 200


async def test_un_jwt_vencido_no_abre(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(_token_de_asesor(vencido=True)))

    assert respuesta.status_code == 401


async def test_sin_header_no_abre(crear_app: Callable[..., FastAPI]) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA)

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "unauthorized"


async def test_el_rechazo_no_dice_cual_de_los_dos_caminos_fallo(
    crear_app: Callable[..., FastAPI],
) -> None:
    """El mismo header transporta dos credenciales distintas. Contestar "la sesión expiró" a quien
    mandó un JWT le confirmaría que ese es un formato que el servicio reconoce, y que lo que le
    falta es uno vigente. El mensaje es el mismo para las dos ramas."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        con_jwt = await http.get(RUTA_LECTURA, headers=_bearer(_token_de_asesor(vencido=True)))
        con_secreto = await http.get(RUTA_LECTURA, headers=_bearer("cron-secret-equivocado"))

    assert con_jwt.json()["error"]["message"] == con_secreto.json()["error"]["message"]
    assert "expir" not in con_jwt.json()["error"]["message"]


# --- Sin CRON_SECRET configurado ----------------------------------------------------------------


async def test_sin_cron_secret_el_secreto_no_abre(
    crear_app: Callable[..., FastAPI], sin_cron_secret: None
) -> None:
    """La rama del cron queda deshabilitada, no comparando contra vacío."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(CRON_SECRET_DE_PRUEBA))

    assert respuesta.status_code == 401


async def test_sin_cron_secret_una_cadena_vacia_tampoco_abre(
    crear_app: Callable[..., FastAPI], sin_cron_secret: None
) -> None:
    """El caso que un `token == settings.cron_secret` mal escrito dejaría pasar."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers={"Authorization": "Bearer "})

    assert respuesta.status_code == 401


async def test_sin_cron_secret_el_asesor_sigue_entrando(
    crear_app: Callable[..., FastAPI], sin_cron_secret: None
) -> None:
    """Un deploy sin la variable queda cerrado para el cron, no roto para el frontend."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(_token_de_asesor()))

    assert respuesta.status_code == 200


# --- Cuando el que falla es este servicio -------------------------------------------------------


async def test_sin_jwks_una_credencial_que_no_es_el_secreto_responde_503(
    crear_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    cliente_jwks.cache_clear()

    def _explota(self):
        raise OSError("no hay red")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _explota)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(_token_de_asesor()))

    assert respuesta.status_code == 503


async def test_sin_jwks_el_cron_sigue_disparando(
    crear_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    """El chequeo del secreto va primero y no depende de Supabase: que el JWKS no esté no puede
    dejar sin corridas a la ingesta programada."""
    cliente_jwks.cache_clear()

    def _explota(self):
        raise OSError("no hay red")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", _explota)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_LECTURA, headers=_bearer(CRON_SECRET_DE_PRUEBA))

    assert respuesta.status_code == 200


# --- Que el corte pase antes de tocar nada ------------------------------------------------------


async def test_un_disparo_sin_credencial_no_llega_a_la_corrida_ni_a_la_base(
    crear_app: Callable[..., FastAPI], monkeypatch: pytest.MonkeyPatch
) -> None:
    """El punto de todo esto: el 401 corta antes de que se toque BYMA o se escriba una fila."""
    corrio = False

    async def _falsa(conn, settings):
        nonlocal corrio
        corrio = True
        return {}

    monkeypatch.setattr(modulo_jobs, "corrida_matinal", _falsa)
    conexion = _FakeConexionCorridas()
    app = crear_app(conexion)

    async with cliente(app) as http:
        respuesta = await http.post(RUTA_MATINAL)

    assert respuesta.status_code == 401
    assert not corrio
    assert conexion.consultas == []


async def test_consolidar_tambien_esta_cerrado(crear_app: Callable[..., FastAPI]) -> None:
    """`forzar=true` se saltea el guardia de rueda cerrada, así que la puerta tiene que estar
    antes que él: si no, un pedido anónimo con `forzar` escribiría un universo parcial."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/consolidar?forzar=true")

    assert respuesta.status_code == 401
