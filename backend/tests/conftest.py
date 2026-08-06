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
    """Conexión falsa con el esquema de mercado en el estado que pida cada test.

    Por defecto simula una base sin migrar: es el caso que hay que seguir cubriendo, porque un
    entorno nuevo arranca así hasta que corren las migraciones.
    """

    def __init__(
        self,
        tabla_existe: bool = False,
        columna_existe: bool = False,
        ultimo_snapshot: Any = None,
        error: Exception | None = None,
    ) -> None:
        self.tabla_existe = tabla_existe
        self.columna_existe = columna_existe
        self.ultimo_snapshot = ultimo_snapshot
        self.error = error
        self.consultas: list[str] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        return {"tabla_existe": self.tabla_existe, "columna_existe": self.columna_existe}

    async def fetchval(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        return self.ultimo_snapshot

    def _registrar(self, query: str) -> None:
        if self.error is not None:
            raise self.error
        self.consultas.append(query)


@pytest.fixture(autouse=True)
def env_de_prueba(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configuración válida en todos los tests, y caché de settings limpia entre ellos.

    Además desconecta el `.env` de la raíz. Sin eso, un test que borra una variable del entorno
    para probar qué pasa cuando falta la sigue encontrando en el archivo, y termina usando la
    credencial de verdad: pasó con la del feed de cashflow, que hizo una consulta real a la fuente
    desde la suite offline. Los tests marcados `integration` no dependen de esto —leen el DSN real
    con `dotenv_values`— así que siguen andando igual.
    """
    from app.core.config import Settings

    monkeypatch.setitem(Settings.model_config, "env_file", None)
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
