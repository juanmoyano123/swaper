"""Loop de fondo que dispara la matinal y los refrescos intra-rueda, según los horarios de
`Settings`. Se arranca y se para desde el `lifespan` de `main.py`.

`dormir` y `reloj` son inyectables, con el mismo criterio que `dormir` en `app/ingesta/http.py`:
sin eso, probar "a las 08:59 falta un minuto" obligaría a esperar un minuto de verdad. `_tick()`
hace una sola pasada —calcular el próximo evento, dormir hasta ahí, ejecutarlo— y `_loop()` es
sólo `while True: await self._tick()`; separarlos es lo que permite probar una pasada sin correr
el loop infinito.

`ingesta_habilitada=False` dejar el servicio sin loop: es el default, y es lo que mantiene a los
tests y al desarrollo local sin un job que corre solo de fondo escribiendo en la base.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import Settings
from app.jobs.corridas import corrida_matinal, refresh_intra_rueda
from app.jobs.horarios import proxima_matinal, proximo_refresh

logger = structlog.get_logger()

ACQUIRE_TIMEOUT_S = 5.0


class Scheduler:
    """Encapsula la tarea de fondo. `pool=None` (base caída al arrancar) o
    `settings.ingesta_habilitada=False` dejan `iniciar()` sin efecto."""

    def __init__(
        self,
        pool: Any | None,
        settings: Settings,
        *,
        dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
        reloj: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._pool = pool
        self._settings = settings
        self._dormir = dormir
        self._reloj = reloj
        self._tarea: asyncio.Task | None = None

    def iniciar(self) -> None:
        if not self._settings.ingesta_habilitada:
            logger.info("scheduler_deshabilitado")
            return
        if self._pool is None:
            logger.warning("scheduler_sin_pool", motivo="la base no está disponible al arrancar")
            return
        self._tarea = asyncio.create_task(self._loop())
        logger.info("scheduler_iniciado")

    async def detener(self) -> None:
        if self._tarea is None:
            return
        self._tarea.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._tarea
        self._tarea = None
        logger.info("scheduler_detenido")

    async def _loop(self) -> None:
        while True:
            await self._tick()

    async def _tick(self) -> None:
        """Una pasada: calcula el próximo evento, duerme hasta ahí y lo ejecuta."""
        ahora = self._reloj()
        objetivo_matinal = proxima_matinal(ahora, self._settings)
        objetivo_refresh = proximo_refresh(ahora, self._settings)
        proximo, tipo = min(
            (objetivo_matinal, "matinal"), (objetivo_refresh, "refresh"), key=lambda par: par[0]
        )
        espera = max((proximo - ahora).total_seconds(), 0.0)
        await self._dormir(espera)
        await self._ejecutar(tipo)

    async def _ejecutar(self, tipo: str) -> None:
        assert self._pool is not None  # iniciar() no crea la tarea sin pool
        try:
            async with self._pool.acquire(timeout=ACQUIRE_TIMEOUT_S) as conn:
                if tipo == "matinal":
                    await corrida_matinal(conn, self._settings, dormir=self._dormir)
                else:
                    await refresh_intra_rueda(conn, self._settings, dormir=self._dormir)
        except Exception as exc:
            # El loop no puede morir por una corrida que salió mal: la próxima pasada es en unos
            # minutos (refresh) o mañana (matinal), y es mejor que ese reintento natural que un
            # scheduler que dejó de correr en silencio.
            logger.error(
                "corrida_del_scheduler_fallo",
                tipo=tipo,
                error=str(exc),
                error_type=type(exc).__name__,
            )
