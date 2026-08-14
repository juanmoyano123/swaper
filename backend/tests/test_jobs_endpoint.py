"""Los endpoints de F-008: historial de corridas y disparo manual de la matinal y del refresh.

La orquestación de cada corrida ya está probada en `test_jobs_corridas.py` sin pasar por HTTP; acá
sólo se prueba el router -que responda 503 sin base, que el límite del historial tenga tope, y que
delegue en las funciones correctas- así que `corrida_matinal`/`refresh_intra_rueda` se reemplazan
por dobles.
"""

from datetime import UTC, datetime

import app.api.v1.jobs as modulo_jobs
from app.core.config import get_settings
from tests.conftest import FakeConnection, cliente


class _FakeConexionCorridas(FakeConnection):
    def __init__(self, filas: list[dict] | None = None) -> None:
        super().__init__()
        self.filas = filas or []
        self.limite_pedido: int | None = None

    async def fetch(self, query: str, *args):
        self._registrar(query)
        self.limite_pedido = args[0] if args else None
        return self.filas


def _fila_cruda() -> dict:
    return {
        "id": 1,
        "tipo": "refresh",
        "iniciado_en": datetime(2026, 8, 6, 11, 0, tzinfo=UTC),
        "finalizado_en": datetime(2026, 8, 6, 11, 0, 30, tzinfo=UTC),
        "duracion_ms": 30000,
        "filas_por_fuente": '{"byma": 100}',
        "alertas": "[]",
        "estado": "completa",
    }


async def test_corridas_devuelve_el_historial(crear_app) -> None:
    app = crear_app(_FakeConexionCorridas([_fila_cruda()]))

    async with cliente(app) as http:
        respuesta = await http.get("/api/v1/jobs/corridas")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["estado"] == "completa"
    assert cuerpo[0]["filas_por_fuente"] == {"byma": 100}


async def test_corridas_sin_base_responde_503(crear_app) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.get("/api/v1/jobs/corridas")

    assert respuesta.status_code == 503


async def test_corridas_limita_el_maximo_pedido(crear_app) -> None:
    conn = _FakeConexionCorridas([])
    app = crear_app(conn)

    async with cliente(app) as http:
        respuesta = await http.get("/api/v1/jobs/corridas?limite=9999")

    assert respuesta.status_code == 200
    assert conn.limite_pedido == modulo_jobs.LIMITE_MAXIMO


async def test_disparar_matinal_delega_en_corrida_matinal(crear_app, monkeypatch) -> None:
    llamado = {}

    async def _falsa(conn, settings):
        llamado["conn"] = conn
        llamado["settings"] = settings
        return {"tipo": "matinal", "estado": "completa"}

    monkeypatch.setattr(modulo_jobs, "corrida_matinal", _falsa)
    app = crear_app(_FakeConexionCorridas())
    app.dependency_overrides[get_settings] = lambda: get_settings()

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/matinal")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tipo": "matinal", "estado": "completa"}
    assert "conn" in llamado


async def test_disparar_refresh_delega_en_refresh_intra_rueda(crear_app, monkeypatch) -> None:
    async def _falsa(conn, settings):
        return {"tipo": "refresh", "estado": "parcial"}

    monkeypatch.setattr(modulo_jobs, "refresh_intra_rueda", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/refresh")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tipo": "refresh", "estado": "parcial"}


async def test_disparar_matinal_sin_base_responde_503(crear_app) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/matinal")

    assert respuesta.status_code == 503


# --- Enriquecimiento de renta variable: Etapa 4 del rediseño del armador -------------------------


async def test_disparar_enriquecimiento_renta_variable_delega_y_devuelve_el_resumen(
    crear_app, monkeypatch
) -> None:
    llamado = {}

    async def _falsa(conn, cliente_yahoo, *, limite):
        llamado["conn"] = conn
        llamado["cliente_yahoo"] = cliente_yahoo
        llamado["limite"] = limite
        return _ResumenFalso()

    monkeypatch.setattr(modulo_jobs, "enriquecer_perfiles", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/perfiles-renta-variable")

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "pendientes": 3,
        "procesados": 3,
        "guardados": 2,
        "cortado_por_limite_de_fuente": False,
        "motivo_corte": None,
    }
    assert "conn" in llamado
    assert llamado["limite"] == modulo_jobs.LIMITE_POR_CORRIDA


async def test_disparar_enriquecimiento_renta_variable_respeta_el_limite_pedido(
    crear_app, monkeypatch
) -> None:
    limites_recibidos = []

    async def _falsa(conn, cliente_yahoo, *, limite):
        limites_recibidos.append(limite)
        return _ResumenFalso()

    monkeypatch.setattr(modulo_jobs, "enriquecer_perfiles", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        await http.post("/api/v1/jobs/perfiles-renta-variable?limite=5")

    assert limites_recibidos == [5]


async def test_disparar_enriquecimiento_renta_variable_sin_base_responde_503(crear_app) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/perfiles-renta-variable")

    assert respuesta.status_code == 503


async def test_con_yahoo_pausado_el_enriquecimiento_no_corre(crear_app, monkeypatch) -> None:
    """Con la pausa activa el endpoint corta antes de leer la base: ni un ticker se le pide a
    Yahoo, y `enriquecer_perfiles` -que sí tocaría la conexión falsa- no se llama."""
    monkeypatch.setenv("YAHOO_HABILITADO", "false")
    get_settings.cache_clear()

    llamado = False

    async def _no_deberia_llamarse(conn, cliente_yahoo, *, limite):
        nonlocal llamado
        llamado = True
        return _ResumenFalso()

    monkeypatch.setattr(modulo_jobs, "enriquecer_perfiles", _no_deberia_llamarse)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/perfiles-renta-variable")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["pausado"] is True
    assert "pausado" in cuerpo["motivo"]
    assert llamado is False


class _ResumenFalso:
    def como_dict(self) -> dict:
        return {
            "pendientes": 3,
            "procesados": 3,
            "guardados": 2,
            "cortado_por_limite_de_fuente": False,
            "motivo_corte": None,
        }
