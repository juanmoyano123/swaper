"""Una corrida completa: pedirle a las tres fuentes, armar el universo y escribirlo.

Las tres fuentes se comportan distinto y esa asimetría se resuelve acá, no en `armado.py`:

- **BYMA y Docta son asíncronas y no lanzan.** Declaran sus fallos en el snapshot, así que se
  piden juntas con `gather` y lo que salga mal viaja como alerta.
- **IAMC es síncrona y llega por subida manual.** No se le puede pedir el informe del día: se
  vuelve a parsear el último aceptado del almacén, que es determinístico. Y sí lanza —
  `InformeInvalido` cuando el PDF dejó de tener la forma esperada— así que se envuelve.

Ninguna fuente caída aborta la corrida. Lo que se pudo traer se escribe y lo que no se declara,
que es la única forma de que un universo incompleto se note.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog
from starlette.concurrency import run_in_threadpool

from app.core.config import Settings
from app.ingesta.alertas import CODIGO_FUENTE_CAIDA, Alerta, Severidad, fuente_caida
from app.ingesta.byma import ingerir_rueda
from app.ingesta.consolidacion.armado import Consolidacion, armar_consolidacion
from app.ingesta.consolidacion.persistencia import (
    Escritura,
    leer_cronograma,
    leer_metricas_previas,
    persistir,
)
from app.ingesta.docta import ConfiguracionFaltante, ingerir_cashflow
from app.ingesta.iamc import InformeInvalido, parsear_informe
from app.ingesta.iamc.almacen import ultimo_informe
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()

ACCION_SUBIR_INFORME = (
    "Bajar el informe diario de deuda corporativa de IAMC y subirlo por "
    "POST /api/v1/iamc/informe; hasta entonces el universo queda sin ley, moneda de pago, "
    "estructura de cupón, TIR, duración ni paridad."
)


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


async def _cashflow_de_docta(settings, dormir):
    try:
        return await ingerir_cashflow(settings, dormir=dormir)
    except ConfiguracionFaltante as exc:
        logger.warning("docta_sin_configurar", error=str(exc))
        return exc


@dataclass(frozen=True, slots=True)
class Informe:
    """Lo que quedó del último informe de IAMC guardado, haya salido bien o no."""

    archivo: str | None = None
    filas: list | None = None
    fecha: date | None = None
    alerta: Alerta | None = None


def _leer_informe() -> Informe:
    """Vuelve a parsear el último informe aceptado del almacén."""
    guardado = ultimo_informe()
    if guardado is None:
        # Es la única fuente cuya caída tiene una acción humana concreta: subir el archivo.
        # Esperar no la arregla, así que no alcanza con `fuente_caida`.
        return Informe(
            alerta=Alerta(
                codigo=CODIGO_FUENTE_CAIDA,
                mensaje="IAMC no está disponible: no hay ningún informe aceptado en el almacén.",
                severidad=Severidad.ERROR,
                accion_requerida=ACCION_SUBIR_INFORME,
                detalle={"fuente": "IAMC"},
            )
        )

    ruta, contenido = guardado
    try:
        resultado = parsear_informe(contenido)
    except InformeInvalido as exc:
        return Informe(
            archivo=ruta.name,
            alerta=fuente_caida(
                "IAMC",
                f"el informe guardado ya no se puede parsear ({exc})",
                archivo=ruta.name,
                **exc.detalle,
            ),
        )
    return Informe(archivo=ruta.name, filas=resultado.filas, fecha=resultado.fecha_informe)


async def consolidar(
    conn,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoConsolidacion:
    """Corre las tres fuentes, arma el universo y lo escribe con un único instante de captura.

    `conn` llega por parámetro y no de `app.state` para que F-008 pueda invocar esto desde un job,
    fuera del ciclo HTTP.
    """
    rueda, cashflow = await asyncio.gather(
        _rueda_de_byma(settings, dormir), _cashflow_de_docta(settings, dormir)
    )
    # El parseo del PDF es CPU-bound y síncrono: en el event loop bloquearía al resto del servicio.
    informe = await run_in_threadpool(_leer_informe)
    # Lo que ya se sabía de IAMC, para que una corrida sin informe no publique un universo sin TIR.
    metricas_previas = await leer_metricas_previas(conn)

    snapshots: dict[str, Snapshot] = {}
    if rueda is not None:
        snapshots["byma"] = rueda.snapshot

    snapshot_iamc = Snapshot(fuente="IAMC")
    snapshot_iamc.registrar_tramo("informe", len(informe.filas or []))
    if informe.alerta is not None:
        snapshot_iamc.alertar(informe.alerta)
    snapshots["iamc"] = snapshot_iamc

    filas_cashflow = None
    if isinstance(cashflow, ConfiguracionFaltante):
        sin_configurar = Snapshot(fuente="Docta")
        sin_configurar.registrar_tramo("cash-flow", 0)
        sin_configurar.alertar(
            fuente_caida("Docta", f"falta configuración: {cashflow}", configurada=False)
        )
        snapshots["docta"] = sin_configurar
    elif cashflow is not None:
        snapshots["docta"] = cashflow.snapshot
        filas_cashflow = cashflow.filas

    # Sin cronograma nuevo se usa el persistido: es contractual y no envejece, así que reusarlo no
    # es presentar un dato viejo como nuevo. Sin esto, una corrida sin Docta perdería la
    # clasificación por submarket y todas las métricas calculadas de F-051.
    cronograma_persistido = None if filas_cashflow is not None else await leer_cronograma(conn)

    # El sello de la corrida se toma antes de armar porque el armado lo necesita: es la fecha
    # contra la que se devengan los corridos y se miden los plazos al descuento.
    capturado_en = datetime.now(UTC)
    consolidacion = armar_consolidacion(
        especies_por_endpoint=rueda.especies_por_endpoint if rueda else {},
        filas_iamc=informe.filas,
        filas_cashflow=filas_cashflow,
        cronograma_persistido=cronograma_persistido,
        archivo_iamc=informe.archivo,
        fecha_informe=informe.fecha,
        metricas_previas=metricas_previas,
        hoy=capturado_en.date(),
    )

    escritura = await persistir(conn, consolidacion, capturado_en)

    logger.info(
        "consolidacion_termino",
        capturado_en=capturado_en.isoformat(),
        instrumentos=escritura.filas_por_tabla.get("instrumentos", 0),
        alertas=len(consolidacion.alertas) + len(escritura.alertas),
        informe_iamc=informe.archivo,
    )
    return ResultadoConsolidacion(
        capturado_en=capturado_en,
        snapshots=snapshots,
        escritura=escritura,
        consolidacion=consolidacion,
    )
