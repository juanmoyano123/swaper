"""Orquesta la ingesta de la planilla diaria de CAFCI: cliente → parser → almacén, en un `Snapshot`
que nunca lanza hacia afuera.

Distinto de BYMA y data912: esos dos entregan filas en memoria para que el consolidador las use.
Acá no hay consolidador — la ficha de F-057 lo dice explícito: un FCI no es una especie negociable,
no se deduplica ni entra a la sanidad de precios de renta fija. Esta función persiste directamente
(`almacen.reescribir_fci`), así que quien la llama sólo necesita el `Snapshot` para la corrida y la
barra de estado.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import UTC, date, datetime

import structlog

from app.core.config import Settings
from app.ingesta.alertas import formato_inesperado, fuente_caida
from app.ingesta.cafci.almacen import reescribir_fci
from app.ingesta.cafci.cliente import descargar_planilla
from app.ingesta.cafci.parser import PlanillaInvalida, parsear_planilla
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.http import ErrorDeFuente
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()

FUENTE = "CAFCI"

CAMPOS_COBERTURA = ("fecha_vcp", "vcp", "calificacion", "gerente", "codigo_cnv")


def _fecha_de_nombre(cruda: str) -> date | None:
    """`YYYYMMDD` del nombre del archivo, o `None` si no calza — se trata como formato inesperado,
    no como una fecha inventada."""
    try:
        return datetime.strptime(cruda, "%Y%m%d").date()
    except ValueError:
        return None


async def ingerir_cafci(
    conn: object,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Snapshot:
    """Descarga, parsea y persiste la planilla del día. Con `cafci_habilitado=False` es un no-op
    declarado: el snapshot registra el tramo en cero y el segmento FCI queda vacío a la vista.
    `dormir` es inyectable para que los tests de reintentos no esperen de verdad."""
    snapshot = Snapshot(fuente=FUENTE)

    if not settings.cafci_habilitado:
        snapshot.registrar_tramo("planilla", 0)
        return snapshot

    try:
        respuesta = await descargar_planilla(settings.cafci_url, dormir=dormir)
    except ErrorDeFuente as exc:
        snapshot.registrar_tramo("planilla", 0)
        snapshot.alertar(fuente_caida(FUENTE, exc.motivo, status=exc.status))
        return snapshot

    fecha_planilla = _fecha_de_nombre(respuesta.fecha_planilla_cruda)
    if fecha_planilla is None:
        snapshot.registrar_tramo("planilla", 0)
        snapshot.alertar(
            formato_inesperado(
                FUENTE,
                "el nombre del archivo no trae una fecha interpretable",
                nombre=respuesta.fecha_planilla_cruda,
            )
        )
        return snapshot

    try:
        resultado = parsear_planilla(respuesta.contenido)
    except PlanillaInvalida as exc:
        logger.warning("cafci_planilla_invalida", motivo=exc.motivo, detalle=exc.detalle)
        snapshot.registrar_tramo("planilla", 0)
        snapshot.alertar(
            formato_inesperado(FUENTE, exc.motivo, fecha_planilla=fecha_planilla.isoformat())
        )
        return snapshot

    capturado_en = datetime.now(UTC)
    filas_escritas = await reescribir_fci(
        conn,
        resultado.filas,
        fecha_planilla=fecha_planilla,
        fecha_cierre_anterior=resultado.fecha_cierre_anterior,
        fecha_base_mes=resultado.fecha_base_mes,
        fecha_base_anio=resultado.fecha_base_anio,
        fecha_base_12m=resultado.fecha_base_12m,
        capturado_en=capturado_en,
    )

    snapshot.registrar_tramo("planilla", filas_escritas)
    snapshot.cobertura.extend(
        medir_cobertura((asdict(f) for f in resultado.filas), CAMPOS_COBERTURA)
    )
    return snapshot
