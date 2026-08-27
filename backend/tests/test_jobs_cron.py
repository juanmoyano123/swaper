"""Los `GET /jobs/cron/*`: la puerta del disparador automático (Tanda 4, 26/08/2026).

Son la misma corrida que los `POST /jobs/corridas/*` con dos guardas encima, y lo que se prueba
acá son las guardas —la corrida en sí ya está probada en `test_jobs_corridas.py` sin pasar por
HTTP, así que `corrida_matinal`/`refresh_intra_rueda` se reemplazan por dobles—.

**Lo que hay que sostener es que una corrida omitida responde 200.** El contrato lo consume
`.github/workflows/ingesta.yml`, que corre con `curl --fail-with-body`: un 4xx pondría el workflow
en rojo cada feriado bursátil y cada tick que GitHub dispare tarde, y un log que está en rojo por
diseño enseña a no mirarlo. El día que la ingesta falle de verdad, esa alerta ya no alerta a nadie.

Los pedidos van con el header de cron real y no con un `dependency_overrides` sobre
`cron_o_asesor`, por el mismo motivo que en `test_jobs_endpoint.py`: con el override, el día que
alguien saque la dependencia del router toda esta suite seguiría en verde.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

import app.api.v1.jobs as modulo_jobs
from app.jobs.corridas import CLAVE_LOCK_INGESTA
from tests.conftest import AUTORIZACION_DE_CRON, FakeConnection, cliente

RUTA_MATINAL = "/api/v1/jobs/cron/matinal"
RUTA_REFRESH = "/api/v1/jobs/cron/refresh"

# Un martes dentro de la rueda y un sábado, en hora de Buenos Aires llevada a UTC (Argentina es
# UTC-3 fijo). Se congela el reloj con estos dos porque las guardas dependen de él y esperar a que
# sea martes no es una opción.
MARTES_EN_RUEDA = datetime(2026, 8, 11, 17, 0, tzinfo=UTC)  # 14:00 ART
MARTES_DE_NOCHE = datetime(2026, 8, 11, 23, 30, tzinfo=UTC)  # 20:30 ART, rueda cerrada
SABADO = datetime(2026, 8, 8, 17, 0, tzinfo=UTC)  # 14:00 ART de un sábado


class _FakeConexionConLock(FakeConnection):
    """Conexión falsa que responde el advisory lock. Con `lock_libre=False` hay otra corrida.

    Guarda las llamadas al lock para poder verificar que se suelta: un `pg_try_advisory_lock` sin su
    `pg_advisory_unlock` deja la ingesta trabada mientras la conexión siga viva en el pool, que es
    exactamente el modo de fallar que el `finally` del context manager existe para evitar.
    """

    def __init__(self, *, lock_libre: bool = True) -> None:
        super().__init__()
        self.lock_libre = lock_libre
        self.llamadas_al_lock: list[str] = []

    async def fetchval(self, query: str, *args: Any) -> Any:
        self._registrar(query)
        if "pg_try_advisory_lock" in query:
            assert args == (CLAVE_LOCK_INGESTA,)
            self.llamadas_al_lock.append("lock")
            return self.lock_libre
        if "pg_advisory_unlock" in query:
            self.llamadas_al_lock.append("unlock")
            return True
        return None


@pytest.fixture
def reloj(monkeypatch: pytest.MonkeyPatch):
    """Congela el `datetime.now(UTC)` que leen los endpoints, sin tocar el del resto del proceso."""

    def _congelar(momento: datetime) -> None:
        class _Reloj(datetime):
            @classmethod
            def now(cls, tz: Any = None) -> datetime:
                return momento if tz is None else momento.astimezone(tz)

        monkeypatch.setattr(modulo_jobs, "datetime", _Reloj)

    return _congelar


@pytest.fixture
def corridas_dobles(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Reemplaza las dos corridas por dobles que sólo cuentan cuántas veces se las llamó."""
    veces = {"matinal": 0, "refresh": 0}

    def _doble(nombre: str):
        async def _falsa(conn: Any, settings: Any) -> dict[str, object]:
            veces[nombre] += 1
            return {"tipo": nombre, "estado": "completa"}

        return _falsa

    monkeypatch.setattr(modulo_jobs, "corrida_matinal", _doble("matinal"))
    monkeypatch.setattr(modulo_jobs, "refresh_intra_rueda", _doble("refresh"))
    return veces


# --- El camino feliz -----------------------------------------------------------------------------


async def test_el_refresh_en_rueda_corre_y_devuelve_el_registro(
    crear_app, reloj, corridas_dobles
) -> None:
    reloj(MARTES_EN_RUEDA)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"tipo": "refresh", "estado": "completa"}
    assert corridas_dobles["refresh"] == 1


async def test_la_matinal_en_dia_habil_corre(crear_app, reloj, corridas_dobles) -> None:
    reloj(MARTES_EN_RUEDA)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_MATINAL, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert corridas_dobles["matinal"] == 1


async def test_el_lock_se_toma_y_se_suelta(crear_app, reloj, corridas_dobles) -> None:
    conexion = _FakeConexionConLock()
    reloj(MARTES_EN_RUEDA)
    app = crear_app(conexion)

    async with cliente(app) as http:
        await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert conexion.llamadas_al_lock == ["lock", "unlock"]


# --- La guarda de horario ------------------------------------------------------------------------


async def test_un_refresh_fuera_de_la_ventana_se_omite_con_200(
    crear_app, reloj, corridas_dobles
) -> None:
    """El tick de las 17:00 que GitHub dispara a las 17:06, con la rueda ya cerrada."""
    reloj(MARTES_DE_NOCHE)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json()["omitida"] is True
    assert "ventana de rueda" in respuesta.json()["motivo"]
    assert corridas_dobles["refresh"] == 0


async def test_un_refresh_de_sabado_se_omite(crear_app, reloj, corridas_dobles) -> None:
    """La hora está en rango pero no hay rueda. El antecedente de correr igual: 466 filas sin un
    solo precio (ver el docstring de `app.jobs.horarios`)."""
    reloj(SABADO)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.json()["omitida"] is True
    assert corridas_dobles["refresh"] == 0


async def test_la_matinal_de_sabado_se_omite(crear_app, reloj, corridas_dobles) -> None:
    reloj(SABADO)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_MATINAL, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json()["omitida"] is True
    assert "día hábil" in respuesta.json()["motivo"]
    assert corridas_dobles["matinal"] == 0


async def test_la_matinal_atrasada_hasta_despues_del_cierre_corre_igual(
    crear_app, reloj, corridas_dobles
) -> None:
    """La diferencia deliberada entre las dos guardas. La matinal es un disparo único por día: si
    el cron llega tarde, traer el universo de hoy con los precios de cierre sigue siendo mejor que
    dejar la jornada entera con los de ayer. El refresh en ese mismo instante no aporta nada que la
    matinal no tenga, y por eso sí se omite."""
    reloj(MARTES_DE_NOCHE)
    app = crear_app(_FakeConexionConLock())

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_MATINAL, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert "omitida" not in respuesta.json()
    assert corridas_dobles["matinal"] == 1


async def test_fuera_de_horario_no_se_toca_el_lock(crear_app, reloj, corridas_dobles) -> None:
    """La guarda de horario va primero justamente para esto: un sábado entero de ticks no tiene
    por qué tomar y soltar un lock cada veinte minutos."""
    conexion = _FakeConexionConLock()
    reloj(SABADO)
    app = crear_app(conexion)

    async with cliente(app) as http:
        await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert conexion.llamadas_al_lock == []


# --- La guarda de solapamiento -------------------------------------------------------------------


async def test_con_otra_corrida_en_curso_se_omite_con_200(
    crear_app, reloj, corridas_dobles
) -> None:
    """Dos corridas simultáneas no corrompen nada, pero intercalan sus `capturado_en` y dejan dos
    filas en `corridas_ingesta` para un solo evento: el indicador de frescura termina publicando el
    timestamp de la que terminó última, que no es la que trajo el precio más nuevo."""
    reloj(MARTES_EN_RUEDA)
    app = crear_app(_FakeConexionConLock(lock_libre=False))

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"omitida": True, "motivo": modulo_jobs.MOTIVO_LOCK_TOMADO}
    assert corridas_dobles["refresh"] == 0


async def test_el_lock_que_no_se_consiguio_no_se_suelta(
    crear_app, reloj, corridas_dobles
) -> None:
    """`pg_advisory_unlock` sobre un lock que tiene otra sesión no hace nada, pero deja un warning
    en el log de Postgres en cada tick. El `finally` sólo suelta lo que efectivamente tomó."""
    conexion = _FakeConexionConLock(lock_libre=False)
    reloj(MARTES_EN_RUEDA)
    app = crear_app(conexion)

    async with cliente(app) as http:
        await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert conexion.llamadas_al_lock == ["lock"]


async def test_el_lock_se_suelta_aunque_la_corrida_explote(
    crear_app, reloj, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El caso que importa del `finally`: si una corrida revienta y el lock queda tomado, la
    conexión vuelve al pool con el lock puesto y la ingesta queda trabada sin que nadie lo note."""

    async def _explota(conn: Any, settings: Any) -> dict[str, object]:
        raise RuntimeError("BYMA devolvió algo que el parser no esperaba")

    monkeypatch.setattr(modulo_jobs, "refresh_intra_rueda", _explota)
    conexion = _FakeConexionConLock()
    reloj(MARTES_EN_RUEDA)
    app = crear_app(conexion)

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 500
    assert conexion.llamadas_al_lock == ["lock", "unlock"]


# --- La puerta ------------------------------------------------------------------------------------


async def test_sin_credencial_no_corre_nada(crear_app, reloj, corridas_dobles) -> None:
    """El router entero está detrás de `cron_o_asesor`, así que un endpoint nuevo nace protegido.
    Esto es lo que verifica que efectivamente haya nacido así."""
    conexion = _FakeConexionConLock()
    reloj(MARTES_EN_RUEDA)
    app = crear_app(conexion)

    async with cliente(app) as http:
        matinal = await http.get(RUTA_MATINAL)
        refresh = await http.get(RUTA_REFRESH)

    assert (matinal.status_code, refresh.status_code) == (401, 401)
    assert corridas_dobles == {"matinal": 0, "refresh": 0}
    assert conexion.consultas == []


async def test_sin_base_responde_503(crear_app, reloj, corridas_dobles) -> None:
    reloj(MARTES_EN_RUEDA)
    app = crear_app(None)

    async with cliente(app) as http:
        respuesta = await http.get(RUTA_REFRESH, headers=AUTORIZACION_DE_CRON)

    assert respuesta.status_code == 503
