"""Job de enriquecimiento del perfil de empresa — Etapa 4 del rediseño del armador.

Corre a mano (`POST /api/v1/jobs/perfiles-renta-variable`), ticker por ticker, con una pausa entre
cada uno para no golpear a Yahoo de una: son del orden de ~750 tickers y la fuente limita por IP
(429, ver el docstring de `app/externos/yahoo.py`). Se persiste ticker a ticker, no al final: si el
job corta en el medio, lo que ya se trajo queda guardado y la próxima corrida retoma con
`tickers_pendientes`, que no vuelve a pedir lo que ya tiene fresco — es lo que hace que sea seguro
correrlo en varias tandas chicas (`limite`) en vez de una sola que tarde diez minutos de un tirón.

**Corta al primer 429 y no insiste.** El cliente ya reintenta cada pedido individual
(`Reintentos` de `yahoo.py`); si después de eso la fuente sigue devolviendo 429, es que está
limitando la IP entera, y seguir probando ticker por ticker sólo alarga el tiempo hasta que la
fuente se recupere sin traer nada más.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import structlog

from app.externos.yahoo import ClienteYahoo
from app.renta_variable.perfiles import guardar_perfil, tickers_pendientes

logger = structlog.get_logger()

PAUSA_ENTRE_TICKERS_SEGUNDOS = 1.0

# Una corrida no procesa el universo entero de un tirón: acota cuánto puede tardar un solo POST y
# deja el resto para la próxima invocación (los pendientes no procesados siguen pendientes).
LIMITE_POR_CORRIDA = 50


@dataclass(frozen=True, slots=True)
class ResumenEnriquecimiento:
    """Lo que el endpoint devuelve — cuántos había, cuántos se tocaron y por qué se paró."""

    pendientes: int
    procesados: int
    guardados: int
    cortado_por_limite_de_fuente: bool
    motivo_corte: str | None

    def como_dict(self) -> dict[str, object]:
        return {
            "pendientes": self.pendientes,
            "procesados": self.procesados,
            "guardados": self.guardados,
            "cortado_por_limite_de_fuente": self.cortado_por_limite_de_fuente,
            "motivo_corte": self.motivo_corte,
        }


async def enriquecer_perfiles(
    conn: Any,
    cliente: ClienteYahoo,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    limite: int = LIMITE_POR_CORRIDA,
) -> ResumenEnriquecimiento:
    """Enriquece hasta `limite` tickers pendientes, uno por uno, con pausa entre cada uno.

    El resto de los pendientes (si los hay) queda para la próxima corrida — no es una falla, es el
    diseño: `limite` existe para que un solo POST no bloquee diez minutos.
    """
    pendientes = await tickers_pendientes(conn)
    a_procesar = pendientes[:limite]

    guardados = 0
    for indice, ticker in enumerate(a_procesar):
        resultado = await cliente.perfil_de_empresa(ticker)

        if resultado.status == 429:
            logger.info(
                "enriquecimiento_renta_variable_cortado_por_429",
                ticker=ticker,
                procesados=indice,
            )
            return ResumenEnriquecimiento(
                pendientes=len(pendientes),
                procesados=indice,
                guardados=guardados,
                cortado_por_limite_de_fuente=True,
                motivo_corte=resultado.motivo,
            )

        if resultado.disponible:
            await guardar_perfil(
                conn,
                ticker,
                nombre_corto=resultado.nombre_corto,
                nombre_largo=resultado.nombre_largo,
                sector=resultado.sector,
                industria=resultado.industria,
                pais=resultado.pais,
                fuente="Yahoo Finance",
                capturado_en=resultado.capturado_en,
            )
            guardados += 1
        else:
            logger.info(
                "enriquecimiento_renta_variable_sin_dato", ticker=ticker, motivo=resultado.motivo
            )

        if indice < len(a_procesar) - 1:
            await dormir(PAUSA_ENTRE_TICKERS_SEGUNDOS)

    return ResumenEnriquecimiento(
        pendientes=len(pendientes),
        procesados=len(a_procesar),
        guardados=guardados,
        cortado_por_limite_de_fuente=False,
        motivo_corte=None,
    )
