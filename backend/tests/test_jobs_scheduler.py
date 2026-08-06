"""El loop de fondo del job de ingesta: cuándo arranca, cuándo no, y que una corrida que sale mal
no lo tumbe.

`_tick()` es una sola pasada (calcular el próximo evento, dormir hasta ahí, ejecutarlo) y es lo que
se prueba acá en vez de `_loop()`, que es `while True: await self._tick()` y correrlo de verdad en
un test lo dejaría colgado.
"""

from datetime import UTC, datetime

import pytest

import app.jobs.scheduler as modulo_scheduler
from app.core.config import get_settings
from app.jobs.scheduler import Scheduler

_CONEXION_DE_PRUEBA = object()


class _CtxAdquisicion:
    def __init__(self, conn) -> None:
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_a) -> bool:
        return False


class _FakePool:
    def __init__(self, conn: object = _CONEXION_DE_PRUEBA) -> None:
        self.conn = conn

    def acquire(self, timeout=None):
        return _CtxAdquisicion(self.conn)


class _Dormidas:
    """Registra cuánto se le pidió dormir, sin dormir de verdad."""

    def __init__(self) -> None:
        self.llamadas: list[float] = []

    async def __call__(self, segundos: float) -> None:
        self.llamadas.append(segundos)


def _settings(**overrides):
    return get_settings().model_copy(
        update={
            "ingesta_habilitada": True,
            "ingesta_zona_horaria": "America/Argentina/Buenos_Aires",
            "ingesta_hora_matinal": "09:00",
            "ingesta_refresh_minutos": 15,
            "ingesta_rueda_desde": "11:00",
            "ingesta_rueda_hasta": "17:00",
            **overrides,
        }
    )


# --- iniciar / detener ------------------------------------------------------------------------


async def test_no_arranca_si_ingesta_esta_deshabilitada() -> None:
    scheduler = Scheduler(_FakePool(), _settings(ingesta_habilitada=False))
    scheduler.iniciar()
    assert scheduler._tarea is None
    await scheduler.detener()  # no revienta aunque nunca arrancó


async def test_no_arranca_sin_pool() -> None:
    scheduler = Scheduler(None, _settings())
    scheduler.iniciar()
    assert scheduler._tarea is None


async def test_iniciar_crea_la_tarea_y_detener_la_cancela_limpio() -> None:
    async def dormir_para_siempre(_: float) -> None:
        # Simula estar esperando el próximo evento: `detener()` tiene que poder cortar esto.
        import asyncio

        await asyncio.Event().wait()

    scheduler = Scheduler(_FakePool(), _settings(), dormir=dormir_para_siempre)
    scheduler.iniciar()
    assert scheduler._tarea is not None
    assert not scheduler._tarea.done()

    await scheduler.detener()

    assert scheduler._tarea is None


# --- _tick --------------------------------------------------------------------------------------


async def test_tick_ejecuta_la_matinal_cuando_es_el_evento_mas_cercano(monkeypatch) -> None:
    llamadas: list[str] = []

    async def _matinal_falsa(conn, settings, *, dormir):
        llamadas.append("matinal")

    async def _refresh_falso(conn, settings, *, dormir):
        llamadas.append("refresh")

    monkeypatch.setattr(modulo_scheduler, "corrida_matinal", _matinal_falsa)
    monkeypatch.setattr(modulo_scheduler, "refresh_intra_rueda", _refresh_falso)

    dormir = _Dormidas()

    def reloj() -> datetime:
        # 08:59 en Buenos Aires: la matinal es en 1 minuto, el próximo refresh es a las 11:00 ->
        # gana la matinal.
        return datetime(2026, 8, 6, 11, 59, tzinfo=UTC)  # 08:59 ART

    scheduler = Scheduler(_FakePool(), _settings(), dormir=dormir, reloj=reloj)

    await scheduler._tick()

    assert llamadas == ["matinal"]
    assert dormir.llamadas == [pytest.approx(60.0, abs=1.0)]


async def test_tick_ejecuta_el_refresh_cuando_es_el_evento_mas_cercano(monkeypatch) -> None:
    llamadas: list[str] = []

    async def _matinal_falsa(conn, settings, *, dormir):
        llamadas.append("matinal")

    async def _refresh_falso(conn, settings, *, dormir):
        llamadas.append("refresh")

    monkeypatch.setattr(modulo_scheduler, "corrida_matinal", _matinal_falsa)
    monkeypatch.setattr(modulo_scheduler, "refresh_intra_rueda", _refresh_falso)

    dormir = _Dormidas()

    def reloj() -> datetime:
        # 10:55 ART: la matinal ya pasó hoy (recién mañana a las 09:00), el próximo refresh es en
        # 5 minutos (11:00, la apertura de la rueda) -> gana el refresh.
        return datetime(2026, 8, 6, 13, 55, tzinfo=UTC)  # 10:55 ART

    scheduler = Scheduler(_FakePool(), _settings(), dormir=dormir, reloj=reloj)

    await scheduler._tick()

    assert llamadas == ["refresh"]
    assert dormir.llamadas == [pytest.approx(300.0, abs=1.0)]


async def test_ejecutar_no_relanza_si_la_corrida_explota(monkeypatch) -> None:
    async def _explota(conn, settings, *, dormir):
        raise RuntimeError("la fuente se cayó de verdad")

    monkeypatch.setattr(modulo_scheduler, "corrida_matinal", _explota)

    scheduler = Scheduler(_FakePool(), _settings())
    await scheduler._ejecutar("matinal")  # no debe propagar
