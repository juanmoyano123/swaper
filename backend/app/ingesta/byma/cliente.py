"""Descarga cruda de los cinco endpoints de la API abierta de BYMA.

La ficha de `plan.md` confunde el tamaño de página con el total: `public-bonds` no tiene 189 filas,
tiene 1106 repartidas en 6 páginas de a 189/500. Un cliente que pida sólo la primera página se
queda con el 17 % del universo y no tiene forma de saberlo si nadie compara contra lo que la propia
fuente declaró. Por eso acá no se asume una forma fija por endpoint: se **detecta** en cada
respuesta (lista plana vs. objeto paginado) y se **verifica** el total bajado contra
`content.total_elements_count` antes de darlo por bueno.

`descargar_endpoint` nunca decide si la corrida global fracasó: eso es trabajo de `ingesta.py`, que
ve los cinco endpoints juntos. Acá sólo se declara lo que pasó con este endpoint en particular —de
ahí que un formato inesperado o una paginación incompleta vuelvan como alertas en el resultado, no
como excepciones: las filas que sí se pudieron bajar se entregan igual.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.ingesta.alertas import Alerta, Severidad, formato_inesperado
from app.ingesta.http import con_reintentos, pedir

NOMBRE_FUENTE = "BYMA"

# Los cuatro primeros llevan filas de especies (bonos, ONs, cedears, acciones); el quinto es el
# índice dólar y afines, que F-012 usa como contraste. Se listan por separado porque normalizan a
# tipos de fila distintos (decisión 6 del plan), no porque el cliente HTTP los trate distinto.
ENDPOINTS_ESPECIES: tuple[str, ...] = (
    "negociable-obligations",
    "public-bonds",
    "cedears",
    "general-equity",
)
ENDPOINT_INDICE = "index-price"

TAMANO_PAGINA = 500
CODIGO_PAGINACION_INCOMPLETA = "paginacion_incompleta"


def paginacion_incompleta(endpoint: str, esperadas: int, obtenidas: int, paginas: int) -> Alerta:
    """El total bajado no cierra contra `total_elements_count`. Las filas se entregan igual."""
    return Alerta(
        codigo=CODIGO_PAGINACION_INCOMPLETA,
        mensaje=(
            f"BYMA declaró {esperadas} filas en {endpoint} pero se obtuvieron {obtenidas} "
            f"tras {paginas} página(s)."
        ),
        severidad=Severidad.ERROR,
        accion_requerida=None,
        detalle={
            "endpoint": endpoint,
            "esperadas": esperadas,
            "obtenidas": obtenidas,
            "paginas": paginas,
        },
    )


@dataclass(frozen=True, slots=True)
class ResultadoDescarga:
    """Lo que trajo un endpoint: sus filas crudas (tal cual las publica BYMA) y lo que salió mal."""

    filas: list[dict[str, Any]] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)


def _es_vacio(respuesta: httpx.Response) -> bool:
    """Cero filas -ya sea lista plana o página con `data` vacío- es fallo reintentable.

    Es el hallazgo medido en la base común (`http.py`): la misma consulta que da cero filas trae
    datos segundos después. No es un mercado sin operaciones, es la fuente siendo inestable.
    """
    try:
        datos = respuesta.json()
    except ValueError:
        return False
    if isinstance(datos, list):
        return len(datos) == 0
    if isinstance(datos, dict):
        contenido = datos.get("data")
        return isinstance(contenido, list) and len(contenido) == 0
    return False


async def descargar_endpoint(
    cliente: httpx.AsyncClient,
    base_url: str,
    endpoint: str,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultadoDescarga:
    """Baja un endpoint entero, paginando si hace falta, y verifica el total contra lo declarado.

    El payload es siempre `{"page_size": 500, "page_number": N}`: verificado que los endpoints de
    lista plana lo ignoran, así que no hace falta ramificar el pedido por forma de respuesta, sólo
    la lectura de la respuesta.
    """
    filas: list[dict[str, Any]] = []
    alertas: list[Alerta] = []
    pagina = 1
    paginas_pedidas = 0
    total_esperado: int | None = None
    total_paginas = 1

    while pagina <= total_paginas:
        cuerpo = {"page_size": TAMANO_PAGINA, "page_number": pagina}

        async def _operacion(cuerpo: dict[str, int] = cuerpo) -> httpx.Response:
            return await pedir(
                cliente,
                "POST",
                f"{base_url}/{endpoint}",
                fuente=NOMBRE_FUENTE,
                json=cuerpo,
                vacio_es_fallo=_es_vacio,
            )

        respuesta = await con_reintentos(
            _operacion, descripcion=f"BYMA:{endpoint}:pagina{pagina}", dormir=dormir
        )
        paginas_pedidas += 1
        datos = respuesta.json()

        if isinstance(datos, list):
            # Lista plana: no hay más páginas que pedir, el conteo es la lista entera.
            filas.extend(datos)
            break

        if isinstance(datos, dict) and isinstance(datos.get("data"), list):
            filas.extend(datos["data"])
            if pagina == 1:
                # `page_count` y `total_elements_count` sólo se leen de la primera respuesta: si
                # cambiaran a mitad de corrida invalidarían el recorrido ya iniciado.
                contenido = datos.get("content") or {}
                total_esperado = contenido.get("total_elements_count")
                total_paginas = contenido.get("page_count") or 1
            pagina += 1
            continue

        # Ni lista ni objeto paginado reconocible: no se intenta "rescatar" filas de acá.
        alertas.append(
            formato_inesperado(
                NOMBRE_FUENTE,
                f"la respuesta de {endpoint} no es una lista ni un objeto con 'data'",
                endpoint=endpoint,
                tipo=type(datos).__name__,
            )
        )
        break

    if total_esperado is not None and len(filas) != total_esperado:
        alertas.append(paginacion_incompleta(endpoint, total_esperado, len(filas), paginas_pedidas))

    return ResultadoDescarga(filas=filas, alertas=alertas)
