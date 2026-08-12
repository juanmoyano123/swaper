"""Descarga cruda de los tramos en vivo de data912.com — experimento de fuente primaria.

Espejo de `byma/cliente.py`, con dos diferencias que vienen de cómo es la fuente:

**No pagina.** Cada tramo de `live/` es una lista plana; no hay `total_elements_count` que
verificar ni segunda página que pedir.

**Un ticker inexistente responde `{"Error": "..."}` con HTTP 200**, verificado contra
`historical/bonds/{ticker}`. Los tramos `live/` no lo hicieron en las pruebas manuales, pero la
forma de la respuesta no es parte de ningún contrato firmado con data912 — es una API pública sin
documentación de compromiso —, así que se la trata igual que BYMA trata un objeto no reconocible:
alerta y cero filas, sin excepción. Un tramo con formato inesperado no corta a los otros cuatro.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.ingesta.alertas import Alerta, formato_inesperado
from app.ingesta.http import con_reintentos, pedir

NOMBRE_FUENTE = "data912"

# Sólo los tramos de especies de renta fija y renta variable local. `live/mep` y `live/ccl`
# quedan afuera a propósito: el tipo de cambio se deriva del propio universo (regla 3), nunca de
# una fuente externa.
TRAMOS_LIVE: tuple[str, ...] = (
    "arg_bonds",
    "arg_corp",
    "arg_notes",
    "arg_cedears",
    "arg_stocks",
)


@dataclass(frozen=True, slots=True)
class ResultadoDescarga:
    """Lo que trajo un tramo: sus filas crudas (tal cual las publica data912) y lo que salió mal."""

    filas: list[dict[str, Any]] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)


def _es_vacio(respuesta: httpx.Response) -> bool:
    """Cero filas es fallo reintentable: un tramo de `live/` nunca es una lista vacía legítima —
    data912 arrastra el último cierre conocido de cada especie, así que hasta un sábado con el
    mercado cerrado devuelve el universo entero. Mismo criterio medido que en BYMA
    (`byma/cliente.py`).
    """
    try:
        datos = respuesta.json()
    except ValueError:
        return False
    return isinstance(datos, list) and len(datos) == 0


async def descargar_tramo(
    cliente: httpx.AsyncClient,
    base_url: str,
    tramo: str,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoDescarga:
    """Baja un tramo `live/` entero. Sin paginación: cada respuesta es la lista completa."""

    async def _operacion() -> httpx.Response:
        return await pedir(
            cliente,
            "GET",
            f"{base_url}/live/{tramo}",
            fuente=NOMBRE_FUENTE,
            vacio_es_fallo=_es_vacio,
        )

    respuesta = await con_reintentos(_operacion, descripcion=f"data912:{tramo}", dormir=dormir)
    datos = respuesta.json()

    if isinstance(datos, list):
        return ResultadoDescarga(filas=datos)

    # Ni lista: un objeto (típicamente `{"Error": "..."}`) o cualquier otra forma. No se intenta
    # "rescatar" filas de acá — mismo criterio que la rama equivalente de `byma/cliente.py`.
    alerta = formato_inesperado(
        NOMBRE_FUENTE,
        f"la respuesta de live/{tramo} no es una lista",
        tramo=tramo,
        tipo=type(datos).__name__,
        cuerpo=datos if isinstance(datos, dict) else None,
    )
    return ResultadoDescarga(alertas=[alerta])
