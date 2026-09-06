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
from typing import Any

import app.api.v1.jobs as modulo_jobs
from app.core.config import get_settings
from app.instrumentos.emisores import ResumenBarrido
from app.jobs.corridas import CLAVE_LOCK_INGESTA
from app.renta_variable.clasificacion import ResumenReclasificacion
from tests.conftest import AUTORIZACION_DE_CRON, FakeConnection, cliente


class _FakeConexionCorridas(FakeConnection):
    """`lock_libre=True` por defecto: la mayoría de estos tests no le interesa el lock, sólo que
    el endpoint delegue en la corrida correcta, y con el lock tomado eso no pasaría —el mismo
    problema que resuelve `_FakeConexionConLock` en `test_jobs_cron.py`, replicado acá porque
    `disparar_matinal`/`disparar_refresh` ahora también pasan por `lock_de_ingesta`."""

    def __init__(self, filas: list[dict] | None = None, *, lock_libre: bool = True) -> None:
        super().__init__()
        self.filas = filas or []
        self.limite_pedido: int | None = None
        self.lock_libre = lock_libre
        self.llamadas_al_lock: list[str] = []

    async def fetch(self, query: str, *args):
        self._registrar(query)
        self.limite_pedido = args[0] if args else None
        return self.filas

    async def fetchval(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        if "pg_try_advisory_lock" in query:
            assert args == (CLAVE_LOCK_INGESTA,)
            self.llamadas_al_lock.append("lock")
            return self.lock_libre
        if "pg_advisory_unlock" in query:
            self.llamadas_al_lock.append("unlock")
            return True
        return await super().fetchval(query, *args)


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


async def test_disparar_matinal_con_lock_tomado_se_omite_y_no_corre(
    crear_app, monkeypatch
) -> None:
    """El botón manual apretado mientras el cron (u otro click) ya está corriendo: no se suman
    corridas en paralelo, se declara por qué no corrió — mismo contrato que `GET /jobs/cron/*`."""
    llamado = {"veces": 0}

    async def _falsa(conn, settings):
        llamado["veces"] += 1
        return {"tipo": "matinal", "estado": "completa"}

    monkeypatch.setattr(modulo_jobs, "corrida_matinal", _falsa)
    conexion = _FakeConexionCorridas(lock_libre=False)
    app = crear_app(conexion)

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/matinal", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"omitida": True, "motivo": modulo_jobs.MOTIVO_LOCK_TOMADO}
    assert llamado["veces"] == 0
    assert conexion.llamadas_al_lock == ["lock"]


async def test_disparar_refresh_con_lock_tomado_se_omite_y_no_corre(
    crear_app, monkeypatch
) -> None:
    async def _falsa(conn, settings):
        raise AssertionError("no debería correr con el lock tomado")

    monkeypatch.setattr(modulo_jobs, "refresh_intra_rueda", _falsa)
    app = crear_app(_FakeConexionCorridas(lock_libre=False))

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/corridas/refresh", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"omitida": True, "motivo": modulo_jobs.MOTIVO_LOCK_TOMADO}


async def test_disparar_matinal_toma_y_suelta_el_lock(crear_app, monkeypatch) -> None:
    async def _falsa(conn, settings):
        return {"tipo": "matinal", "estado": "completa"}

    monkeypatch.setattr(modulo_jobs, "corrida_matinal", _falsa)
    conexion = _FakeConexionCorridas()
    app = crear_app(conexion)

    async with cliente(app) as http:
        await http.post("/api/v1/jobs/corridas/matinal", headers=AUTORIZACION_DE_CRON)

    assert conexion.llamadas_al_lock == ["lock", "unlock"]


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


# --- F-078: reclasificar ETFs y sembrar el curado de países --------------------------------------


async def test_reclasificar_etfs_devuelve_los_tres_conteos(crear_app, monkeypatch) -> None:
    async def _falsa(conn):
        return ResumenReclasificacion(procesados=1074, con_estrategia=126, con_region=30)

    monkeypatch.setattr(modulo_jobs, "reclasificar_etfs", _falsa)
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/reclasificar-etfs", headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"procesados": 1074, "con_estrategia": 126, "con_region": 30}


async def test_reclasificar_etfs_exige_credencial(crear_app) -> None:
    """Nace cerrado porque la dependencia vive en el router: es la propiedad que hace que un job
    nuevo llegue protegido sin que su autor tenga que enterarse de que la puerta existe."""
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/reclasificar-etfs")

    assert respuesta.status_code == 401


async def test_sembrar_paises_sin_artefacto_devuelve_cero_y_la_alerta(crear_app, tmp_path) -> None:
    """El estado normal hasta que el curado se valide: cero cargados, con la alerta arriba. No es
    un fallo — es el país de cada CEDEAR declarado faltante, que es el contrato del sistema."""
    ajustes = get_settings().model_copy(
        update={"paises_cedears_csv": str(tmp_path / "no-existe.csv")}
    )
    app = crear_app(_FakeConexionCorridas())
    app.dependency_overrides[get_settings] = lambda: ajustes

    async with cliente(app) as http:
        respuesta = await http.post(
            "/api/v1/jobs/sembrar-paises-cedears", headers=AUTORIZACION_DE_CRON
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["cargados"] == 0
    assert [a["codigo"] for a in cuerpo["alertas"]] == ["paises_cedears_no_encontrado"]


async def test_sembrar_paises_exige_credencial(crear_app) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/sembrar-paises-cedears")

    assert respuesta.status_code == 401


# --- F-079 D3: sembrar la geografía curada de ETFs -----------------------------------------------


async def test_sembrar_geografia_etfs_sin_artefacto_devuelve_cero(crear_app, tmp_path) -> None:
    """El estado normal hasta que el curado se valide: cero cargados, sin explotar — cada ETF
    geográfico sigue mostrándose con el token crudo de su nombre hasta entonces."""
    ajustes = get_settings().model_copy(
        update={"etfs_geografia_csv": str(tmp_path / "no-existe.csv")}
    )
    app = crear_app(_FakeConexionCorridas())
    app.dependency_overrides[get_settings] = lambda: ajustes

    async with cliente(app) as http:
        respuesta = await http.post(
            "/api/v1/jobs/sembrar-geografia-etfs", headers=AUTORIZACION_DE_CRON
        )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"cargados": 0}


async def test_sembrar_geografia_etfs_exige_credencial(crear_app) -> None:
    app = crear_app(_FakeConexionCorridas())

    async with cliente(app) as http:
        respuesta = await http.post("/api/v1/jobs/sembrar-geografia-etfs")

    assert respuesta.status_code == 401
