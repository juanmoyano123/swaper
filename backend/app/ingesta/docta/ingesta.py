"""Orquesta la ingesta del feed de cashflow de Docta: arma la URL, baja el Excel, normaliza y
declara qué salió — GWT-1 (token vencido), GWT-2 (fuente caída) y GWT-3 (vacío errático).

Tres fallos, tres alertas distintas, porque la acción que piden es distinta: una credencial
vencida se arregla regenerando un link a mano, una fuente caída se arregla esperando, y un formato
inesperado necesita que alguien revise si Docta cambió el contrato. Confundirlas manda a alguien a
esperar algo que no se va a destrabar solo, o a regenerar un token que está sano.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import structlog

from app.core.config import Settings
from app.ingesta.alertas import (
    credencial_vencida,
    formato_inesperado,
    fuente_caida,
    respuesta_vacia,
)
from app.ingesta.cobertura import medir_cobertura
from app.ingesta.docta.cliente import FUENTE, bajar_cashflow
from app.ingesta.docta.normalizacion import (
    COLUMNAS_CONTRACTUALES,
    columnas_faltantes,
    normalizar_filas,
)
from app.ingesta.docta.url import url_efectiva
from app.ingesta.http import (
    INTENTOS_POR_DEFECTO,
    CredencialVencida,
    ErrorDeFuente,
    con_reintentos,
    crear_cliente,
)
from app.ingesta.snapshot import Snapshot

logger = structlog.get_logger()

TRAMO = "cash-flow"

INSTRUCCION_TOKEN_VENCIDO = (
    "Regenerar el link en Docta Terminal ('Generar Link') y actualizar las DOCTA_*_URL en .env "
    "— el token nuevo sirve para los tres links."
)


@dataclass(frozen=True, slots=True)
class ResultadoCashflow:
    """Lo que F-006 le entrega a quien persiste (F-007) — acá termina la responsabilidad de F-006.

    `filas is None` significa "esta corrida no trajo un cashflow usable" (token vencido, fuente
    caída, vacío agotado tras reintentar, o columnas contractuales rotas), y es distinguible de una
    lista de filas real. El contrato para quien consume este resultado: sólo se escribe a la base
    cuando `filas is not None`; ante `None` se conserva el último cashflow persistido y se propagan
    las alertas de `snapshot`. Cero filas "legítimas" no existen como éxito: un universo con 97 %
    de cobertura de emisiones no puede tener un cashflow vacío, así que el vacío es siempre fallo.
    """

    filas: list[dict[str, object]] | None
    snapshot: Snapshot


async def ingerir_cashflow(
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoCashflow:
    """Corre la ingesta completa. Puede lanzar `ConfiguracionFaltante` si falta una variable de
    entorno — eso corta antes de intentar nada, y lo traduce a 503 quien llama (el endpoint).

    `dormir` es inyectable, igual que en `con_reintentos`, para que los tests no esperen de
    verdad las esperas crecientes entre reintentos.
    """
    url = url_efectiva(settings.docta_cashflow_url, settings.docta_api_token)
    snapshot = Snapshot(fuente="Docta", demora_declarada_minutos=0)
    filas: list[dict[str, object]] | None = None

    async with crear_cliente() as cliente:
        try:
            df = await con_reintentos(
                lambda: bajar_cashflow(cliente, url), descripcion=FUENTE, dormir=dormir
            )
        except CredencialVencida as exc:
            logger.warning("docta_token_vencido")
            snapshot.registrar_tramo(TRAMO, 0)
            snapshot.alertar(
                credencial_vencida("Docta", INSTRUCCION_TOKEN_VENCIDO, status=exc.status)
            )
        except ErrorDeFuente as exc:
            snapshot.registrar_tramo(TRAMO, 0)
            if "cero filas" in exc.motivo:
                # Agotó los reintentos sin traer una sola fila: es la inestabilidad errática del
                # feed, no una fuente caída — la acción es distinta (ver docstring del módulo).
                snapshot.alertar(
                    respuesta_vacia(FUENTE, intentos=INTENTOS_POR_DEFECTO, motivo=exc.motivo)
                )
            else:
                snapshot.alertar(fuente_caida(FUENTE, exc.motivo, status=exc.status))
        else:
            faltantes = columnas_faltantes(df)
            if faltantes:
                snapshot.registrar_tramo(TRAMO, 0)
                snapshot.alertar(
                    formato_inesperado(FUENTE, f"faltan columnas {', '.join(faltantes)}")
                )
            else:
                filas = normalizar_filas(df)
                snapshot.registrar_tramo(TRAMO, len(filas))
                snapshot.cobertura.extend(medir_cobertura(filas, COLUMNAS_CONTRACTUALES))

    logger.info(
        "ingesta_docta_termino",
        filas=len(filas) if filas is not None else 0,
        completo=snapshot.completo,
    )
    return ResultadoCashflow(filas=filas, snapshot=snapshot)
