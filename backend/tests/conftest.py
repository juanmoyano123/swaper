"""Andamiaje común de los tests.

La suite corre sin base de datos: la conexión se reemplaza por una falsa vía
`dependency_overrides`. El único test que toca PostgreSQL de verdad está marcado `integration`
y queda fuera de la corrida por defecto.
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_db_optional
from app.core.config import get_settings

# Valores inventados a propósito: los tests de logging verifican que ninguno de estos aparezca
# en la salida. La contraseña del DSN es el caso testigo.
ENV_DE_PRUEBA = {
    "SUPABASE_URL": "https://proyecto-de-prueba.supabase.co",
    "SUPABASE_ANON_KEY": "anon-key-de-prueba-9f3a",
    "SUPABASE_SERVICE_ROLE_KEY": "service-role-de-prueba-7c1b",
    "DATABASE_URL": "postgresql://usuario:contrasena-secreta@localhost:5432/swaper_test",
}


class FakeConnection:
    """Conexión falsa: responde según qué fragmento aparezca en la consulta.

    Lo que no matchea ninguna clave devuelve None, que es como se ve una tabla que todavía no
    existe — el estado real del proyecto hasta que F-002 cree el esquema.
    """

    def __init__(
        self,
        respuestas: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.respuestas = respuestas or {}
        self.error = error
        self.consultas: list[str] = []

    async def fetchval(self, query: str, *args: Any) -> Any:
        if self.error is not None:
            raise self.error
        self.consultas.append(query)
        for fragmento, valor in self.respuestas.items():
            if fragmento in query:
                return valor
        return None


@pytest.fixture(autouse=True)
def env_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuración válida en todos los tests, y caché de settings limpia entre ellos."""
    for clave, valor in ENV_DE_PRUEBA.items():
        monkeypatch.setenv(clave, valor)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def crear_app() -> Callable[..., FastAPI]:
    """Fábrica de apps con la base reemplazada por una conexión falsa (o por None: base caída)."""
    from app.main import create_app

    def _crear(conn: Any | None = None) -> FastAPI:
        app = create_app()
        app.dependency_overrides[get_db_optional] = lambda: conn
        return app

    return _crear


def cliente(app: FastAPI) -> AsyncClient:
    # raise_app_exceptions=False para poder inspeccionar la respuesta 500 del handler en vez de
    # que la excepción se propague al test.
    return AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )
