"""Orquesta los cinco endpoints de BYMA en un único snapshot de rueda.

BYMA no tiene credencial que renovar: la API abierta no lleva token. Por eso un endpoint que
responde 401 no se trata distinto de uno que da timeout o 500 persistente -las dos situaciones se
resuelven de la misma forma (esperar y reintentar en la próxima corrida), así que las dos se
declaran igual, como `fuente_caida`- y sobre todo, ninguna de las dos corta a los otros cuatro
endpoints. Cada uno se ingiere en su propio `try/except`, y los cinco tramos quedan siempre
registrados en el snapshot -con 0 filas el que falló- porque eso es lo que permite ver a simple
vista cuál faltó, sin tener que ir a buscar en los logs.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from app.core.config import Settings, get_settings
from app.ingesta.alertas import CODIGO_FUENTE_CAIDA, fuente_caida, respuesta_vacia
from app.ingesta.byma.cliente import (
    ENDPOINT_INDICE,
    ENDPOINTS_ESPECIES,
    descargar_endpoint,
)
from app.ingesta.byma.normalizacion import (
    CAMPOS_COBERTURA_ESPECIES,
    CAMPOS_COBERTURA_INDICES,
    FilaIndice,
    FilaRueda,
    normalizar_fila_indice,
    normalizar_fila_rueda,
)
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.http import INTENTOS_POR_DEFECTO, ErrorDeFuente, RespuestaVacia, crear_cliente
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class ResultadoRueda:
    """Lo que entrega una corrida de ingesta de BYMA, en memoria: F-004 no persiste nada.

    F-007 importa `ingerir_rueda` directamente (`from app.ingesta.byma import ingerir_rueda`) y es
    quien decide qué persistir y con qué precedencia; el endpoint HTTP es sólo la forma de
    dispararla a mano.
    """

    especies: list[FilaRueda]
    indices: list[FilaIndice]
    snapshot: Snapshot


async def ingerir_rueda(
    *,
    settings: Settings | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoRueda:
    """Recorre los cinco endpoints, normaliza lo que trajeron y arma el snapshot de la corrida."""
    settings = settings or get_settings()
    snapshot = Snapshot(fuente="BYMA", demora_declarada_minutos=settings.byma_demora_minutos)

    especies: list[FilaRueda] = []
    indices: list[FilaIndice] = []

    async with crear_cliente() as cliente:
        for endpoint in (*ENDPOINTS_ESPECIES, ENDPOINT_INDICE):
            try:
                descarga = await descargar_endpoint(
                    cliente, settings.byma_base_url, endpoint, dormir=dormir
                )
            except RespuestaVacia:
                # Agotó los reintentos sin traer una fila: es la inestabilidad medida del
                # endpoint, no una caída del servicio.
                snapshot.registrar_tramo(endpoint, 0)
                snapshot.alertar(respuesta_vacia("BYMA", INTENTOS_POR_DEFECTO, endpoint=endpoint))
                continue
            except ErrorDeFuente as exc:
                snapshot.registrar_tramo(endpoint, 0)
                snapshot.alertar(
                    fuente_caida("BYMA", exc.motivo, endpoint=endpoint, status=exc.status)
                )
                continue

            snapshot.registrar_tramo(endpoint, len(descarga.filas))
            for alerta in descarga.alertas:
                snapshot.alertar(alerta)

            if endpoint == ENDPOINT_INDICE:
                indices.extend(normalizar_fila_indice(fila) for fila in descarga.filas)
            else:
                especies.extend(normalizar_fila_rueda(fila) for fila in descarga.filas)

    snapshot.cobertura = medir_cobertura(especies, CAMPOS_COBERTURA_ESPECIES) + medir_cobertura(
        indices, CAMPOS_COBERTURA_INDICES
    )

    endpoints_caidos = [
        alerta.detalle.get("endpoint")
        for alerta in snapshot.alertas
        if alerta.codigo == CODIGO_FUENTE_CAIDA
    ]
    logger.info(
        "ingesta_byma_termino",
        total_filas=snapshot.total_filas,
        endpoints_caidos=endpoints_caidos,
        completo=snapshot.completo,
    )

    return ResultadoRueda(especies=especies, indices=indices, snapshot=snapshot)
