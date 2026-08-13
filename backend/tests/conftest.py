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


class _Transaccion:
    """Context manager que anota si la transacción cerró bien o se deshizo."""

    def __init__(self, conexion: "FakeConexionEscritura") -> None:
        self._conexion = conexion

    async def __aenter__(self) -> "_Transaccion":
        self._conexion.transacciones.append("begin")
        return self

    async def __aexit__(self, exc_type: Any, *_: Any) -> bool:
        self._conexion.transacciones.append("rollback" if exc_type else "commit")
        return False


class FakeConexionEscritura(FakeConnection):
    """Conexión falsa que además acepta escrituras y guarda qué SQL recibió con qué argumentos.

    Existe porque los tests de persistencia no prueban que PostgreSQL funcione: prueban el
    contrato de las sentencias —que el upsert de instrumentos no pise con nulos, que precios sea
    un INSERT plano, que el cronograma no se toque cuando no hay uno usable— y eso se ve en el SQL
    emitido. Que la base lo acepte es lo que verifica el test de integración.

    `fallar_en` hace que un bloque explote sin tocar a los otros, que es la propiedad que F-008
    hereda: un fallo puntual no puede convertirse en "no se guardó nada".
    """

    def __init__(
        self,
        *,
        fallar_en: str | None = None,
        metricas_previas: list[dict[str, Any]] | None = None,
        cronograma: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.fallar_en = fallar_en
        self.metricas_previas = metricas_previas or []
        self.cronograma = cronograma or []
        self.escrituras: list[tuple[str, list[Any]]] = []
        self.transacciones: list[str] = []

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        # Se rutea por tabla porque desde la baja de Docta la corrida lee el cronograma en cada
        # pasada, no sólo cuando falta uno nuevo: devolver las métricas para cualquier consulta
        # dejaría a toda la renta fija sin flujo contractual y sin clasificar.
        self._registrar(query)
        if "FROM public.cashflow" in query:
            return self.cronograma
        return self.metricas_previas

    def transaction(self) -> _Transaccion:
        return _Transaccion(self)

    async def executemany(self, query: str, args: Any) -> None:
        if self.fallar_en and self.fallar_en in query:
            raise RuntimeError(f"fallo simulado escribiendo {self.fallar_en}")
        self.escrituras.append((query, list(args)))

    async def execute(self, query: str, *args: Any) -> None:
        await self.executemany(query, [args])

    def sql_de(self, tabla: str) -> str:
        """El SQL que se emitió contra una tabla. Falla el test si no se escribió ninguno."""
        for query, _ in self.escrituras:
            if f"INTO public.{tabla}" in query:
                return query
        raise AssertionError(f"no se escribió nada en {tabla}")

    def filas_de(self, tabla: str) -> list[Any]:
        return [
            fila
            for query, args in self.escrituras
            if f"INTO public.{tabla}" in query
            for fila in args
        ]

    def escribio_en(self, tabla: str) -> bool:
        return any(f"INTO public.{tabla}" in query for query, _ in self.escrituras)


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
