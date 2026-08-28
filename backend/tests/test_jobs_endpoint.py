"""Los endpoints de F-008: historial de corridas y disparo manual de la matinal y del refresh.

La orquestación de cada corrida ya está probada en `test_jobs_corridas.py` sin pasar por HTTP; acá
sólo se prueba el router -que responda 503 sin base, que el límite del historial tenga tope, y que
delegue en las funciones correctas- así que `corrida_matinal`/`refresh_intra_rueda` se reemplazan
por dobles.

Todos los pedidos van con credencial: desde la Tanda 3 el router entero está detrás de
`cron_o_asesor`. Los tests mandan el header de cron real en vez de neutralizar la dependencia, así
que cada uno de estos casos vuelve a ejercitar la auth. Los caminos de la puerta en sí -y el 401
sin header- están en `test_cron_auth.py`.
"""

from datetime import UTC, datetime

import app.api.v1.jobs as modulo_jobs
from app.core.config import get_settings
from app.instrumentos.emisores import ResumenBarrido
from tests.conftest import AUTORIZACION_DE_CRON, FakeConnection, cliente


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
        respuesta = await http.get("/api/v1/jobs/corridas", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert len(cuerpo) == 1
    assert cuerpo[0]["estado"] == "completa"
    assert cuerpo[0]["filas_por_fuente"] == {"byma": 100}


async def test_corridas_sin_base_responde_503(crear_app) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.get("/api/v1/jobs/corridas", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 503


async def test_corridas_limita_el_maximo_pedido(crear_app) -> None:
    conn = _FakeConexionCorridas([])
    app = crear_app(conn)

    async with cliente(app) as http:
        respuesta = await http.get(
            "/api/v1/jobs/corridas?limite=9999", headers=AUTORIZACION_DE_CRON
        )

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
        respuesta = await http.post("/api/v1/jobs/corridas/matinal", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tipo": "matinal", "estado": "completa"}
    assert "conn" in llamado


async def test_disparar_refresh_delega_en_refresh_intra_rueda(crear_app, monkeypatch) -> None:
    async def _falsa(conn, settings):
        return {"tipo": "refresh", "estado": "parcial"}

    monkeypatch.setattr(modulo_jobs, "refresh_intra_rueda", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/refresh", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tipo": "refresh", "estado": "parcial"}


async def test_disparar_matinal_sin_base_responde_503(crear_app) -> None:
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/matinal", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 503


async def test_completar_emisores_exige_credencial(crear_app) -> None:
    """Nace cerrado porque la dependencia vive en el router, no en el decorador. El test lo fija:
    si alguien moviera `cron_o_asesor` a cada endpoint, éste quedaría abierto y nadie lo notaría.
    """
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/completar-emisores")

    assert respuesta.status_code == 401


async def test_completar_emisores_topea_el_limite_pedido(crear_app, monkeypatch) -> None:
    """Son ~4.000 pendientes y un POST por especie: sin tope, una sola llamada duraría más de lo
    que cualquier proxy tolera."""
    pedido = {}

    async def _falsa(conn, *, limite):
        pedido["limite"] = limite
        return ResumenBarrido(0, 0, 0, 0, 0, 0, 0, 0)

    monkeypatch.setattr(modulo_jobs, "completar_emisores", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post(
            "/api/v1/jobs/completar-emisores?limite=99999", headers=AUTORIZACION_DE_CRON
        )

    assert respuesta.status_code == 200
    assert pedido["limite"] == modulo_jobs.LIMITE_EMISORES
