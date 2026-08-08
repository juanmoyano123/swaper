"""Orquesta los cinco tramos `live/` de data912 en un único snapshot.

Espejo de `byma/ingesta.py`. data912 tampoco tiene credencial que renovar, así que un tramo que
responde con formato inesperado no se trata distinto de uno que da timeout: las dos se resuelven
reintentando en la próxima corrida, y ninguna corta a los otros cuatro tramos. Cada uno se ingiere
en su propio `try/except`, y los cinco quedan siempre registrados en el snapshot —con 0 filas el
que falló— para que se vea a simple vista cuál faltó.

Sin demora declarada: a diferencia de BYMA, data912 no publica cuánto atrasa respecto del mercado,
y la regla 11 prohíbe inventarle una.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from app.core.config import Settings, get_settings
from app.ingesta.alertas import CODIGO_FUENTE_CAIDA, fuente_caida, respuesta_vacia
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.data912.cliente import NOMBRE_FUENTE, TRAMOS_LIVE, descargar_tramo
from app.ingesta.data912.normalizacion import (
    CAMPOS_COBERTURA_LIVE,
    FilaLive,
    normalizar_fila_live,
)
from app.ingesta.http import INTENTOS_POR_DEFECTO, ErrorDeFuente, RespuestaVacia, crear_cliente
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class ResultadoLive:
    """Lo que entrega una corrida de ingesta de data912, en memoria.

    `filas_por_tramo` conserva la separación por tramo porque el overlay necesita saber a qué
    endpoint de BYMA mapea cada uno (`ENDPOINT_BYMA_POR_TRAMO`) para los tickers sólo-data912.
    """

    filas_por_tramo: dict[str, list[FilaLive]]
    snapshot: Snapshot


async def ingerir_live(
    *,
    settings: Settings | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoLive:
    """Recorre los cinco tramos, normaliza lo que trajeron y arma el snapshot de la corrida."""
    settings = settings or get_settings()
    snapshot = Snapshot(fuente=NOMBRE_FUENTE)

    filas_por_tramo: dict[str, list[FilaLive]] = {}

    async with crear_cliente() as cliente:
        for tramo in TRAMOS_LIVE:
            try:
                descarga = await descargar_tramo(
                    cliente, settings.data912_base_url, tramo, dormir=dormir
                )
            except RespuestaVacia:
                snapshot.registrar_tramo(tramo, 0)
                snapshot.alertar(respuesta_vacia(NOMBRE_FUENTE, INTENTOS_POR_DEFECTO, tramo=tramo))
                continue
            except ErrorDeFuente as exc:
                snapshot.registrar_tramo(tramo, 0)
                snapshot.alertar(
                    fuente_caida(NOMBRE_FUENTE, exc.motivo, tramo=tramo, status=exc.status)
                )
                continue

            snapshot.registrar_tramo(tramo, len(descarga.filas))
            for alerta in descarga.alertas:
                snapshot.alertar(alerta)

            filas_por_tramo[tramo] = [normalizar_fila_live(fila) for fila in descarga.filas]

    todas_las_filas = [fila for filas in filas_por_tramo.values() for fila in filas]
    snapshot.cobertura = medir_cobertura(todas_las_filas, CAMPOS_COBERTURA_LIVE)

    tramos_caidos = [
        alerta.detalle.get("tramo")
        for alerta in snapshot.alertas
        if alerta.codigo == CODIGO_FUENTE_CAIDA
    ]
    logger.info(
        "ingesta_data912_termino",
        total_filas=snapshot.total_filas,
        tramos_caidos=tramos_caidos,
        completo=snapshot.completo,
    )

    return ResultadoLive(filas_por_tramo=filas_por_tramo, snapshot=snapshot)
