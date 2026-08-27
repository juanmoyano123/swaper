"""Una corrida completa: pedirle a las fuentes, armar el universo y escribirlo.

Las fuentes se comportan distinto y esa asimetría se resuelve acá, no en `armado.py`:

- **BYMA y data912 son asíncronas y no lanzan.** Declaran sus fallos en el snapshot, así que se
  piden juntas con `gather` y lo que salga mal viaja como alerta.
- **El cronograma no se le pide a nadie.** Docta era la única fuente que lo publicaba y se dio de
  baja el 12/08/2026 por costo; el flujo contractual sale del que quedó persistido en `cashflow`.

Ninguna fuente caída aborta la corrida. Lo que se pudo traer se escribe y lo que no se declara,
que es la única forma de que un universo incompleto se note.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from app.core.config import Settings
from app.ingesta.byma import ingerir_rueda
from app.ingesta.consolidacion.armado import Consolidacion, armar_consolidacion
from app.ingesta.consolidacion.overlay import aplicar_overlay
from app.ingesta.consolidacion.persistencia import (
    Escritura,
    leer_cronograma,
    leer_monedas,
    persistir,
)
from app.ingesta.data912 import ingerir_live
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class ResultadoConsolidacion:
    """Lo que la corrida deja para reportar. No lleva filas: son miles y ya están en la base."""

    capturado_en: datetime
    snapshots: dict[str, Snapshot]
    escritura: Escritura
    consolidacion: Consolidacion

    def como_dict(self) -> dict[str, object]:
        alertas = [
            *(a for s in self.snapshots.values() for a in s.alertas),
            *self.consolidacion.alertas,
            *self.escritura.alertas,
        ]
        return {
            "capturado_en": self.capturado_en.isoformat(),
            "snapshots": {n: s.como_dict() for n, s in self.snapshots.items()},
            "escrito": self.escritura.filas_por_tabla,
            "cobertura": [c.como_dict() for c in self.consolidacion.cobertura],
            "alertas": [a.como_dict() for a in alertas],
        }


async def _rueda_de_byma(settings, dormir):
    try:
        return await ingerir_rueda(settings=settings, dormir=dormir)
    except Exception as exc:  # la fuente no debería lanzar, pero una corrida no se pierde por eso
        logger.warning("byma_lanzo", error=str(exc))
        return None


async def _live_de_data912(settings, dormir):
    """Experimento de fuente primaria: si data912 falla, la corrida sigue sólo con BYMA — es
    exactamente el estado de hoy, sin overlay. `aplicar_overlay` recibe `{}` y no cambia nada."""
    try:
        return await ingerir_live(settings=settings, dormir=dormir)
    except Exception as exc:  # la fuente no debería lanzar, pero una corrida no se pierde por eso
        logger.warning("data912_lanzo", error=str(exc))
        return None


async def consolidar(
    conn,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoConsolidacion:
    """Corre las fuentes, arma el universo y lo escribe con un único instante de captura.

    `conn` llega por parámetro y no de `app.state` para que F-008 pueda invocar esto desde un job,
    fuera del ciclo HTTP.
    """
    rueda, live = await asyncio.gather(
        _rueda_de_byma(settings, dormir),
        _live_de_data912(settings, dormir),
    )
    # La moneda que BYMA ya declaró para cada ticker, para los que en esta corrida sólo trae
    # data912 (que no la declara). Ver `overlay.py` — no es un dato nuevo, es atributo estable.
    monedas_previas = await leer_monedas(conn)

    snapshots: dict[str, Snapshot] = {}
    if rueda is not None:
        snapshots["byma"] = rueda.snapshot
    if live is not None:
        snapshots["data912"] = live.snapshot

    overlay = aplicar_overlay(
        rueda.especies_por_endpoint if rueda else {},
        live.filas_por_tramo if live else {},
        monedas_previas=monedas_previas,
    )
    if live is not None:
        for alerta in overlay.alertas:
            snapshots["data912"].alertar(alerta)
    logger.info("overlay_data912", **overlay.conteos)

    # Ninguna fuente publica cronogramas desde que se dio de baja Docta, así que el flujo
    # contractual sale siempre del que ya está persistido. No es dato viejo presentado como nuevo:
    # un cronograma es contractual y no envejece — lo que no cambia más es qué especies lo tienen.
    # `filas_cashflow=None` en el armado le dice a `persistir()` que no toque la tabla `cashflow`.
    cronograma_persistido = await leer_cronograma(conn)

    # El sello de la corrida se toma antes de armar porque el armado lo necesita: es la fecha
    # contra la que se devengan los corridos y se miden los plazos al descuento.
    capturado_en = datetime.now(UTC)
    consolidacion = armar_consolidacion(
        especies_por_endpoint=overlay.especies_por_endpoint,
        filas_cashflow=None,
        cronograma_persistido=cronograma_persistido,
        hoy=capturado_en.date(),
    )

    escritura = await persistir(
        conn, consolidacion, capturado_en, serie_historica=settings.serie_historica_habilitada
    )

    logger.info(
        "consolidacion_termino",
        capturado_en=capturado_en.isoformat(),
        instrumentos=escritura.filas_por_tabla.get("instrumentos", 0),
        alertas=len(consolidacion.alertas) + len(escritura.alertas),
    )
    return ResultadoConsolidacion(
        capturado_en=capturado_en,
        snapshots=snapshots,
        escritura=escritura,
        consolidacion=consolidacion,
    )
