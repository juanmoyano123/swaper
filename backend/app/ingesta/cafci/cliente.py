"""Cliente HTTP de la planilla diaria de CAFCI.

`GET https://api.pub.cafci.org.ar/pb_get`, sin token. Devuelve un XLSX (`content-type`
`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`) con un `content-disposition`
del que se lee la fecha de la planilla: `attachment; filename="20260821_Planilla_Diaria_A.xlsx"`.
Es la única forma de saber de qué fecha es el snapshot — la fuente no la repite en ninguna celda.

**No hay parámetro de fecha que pedir.** Se probó `?fecha=`, `?date=`, `?f=` y `?tipo=` contra la
fuente real el 23/08/2026: las cuatro devuelven el mismo archivo del último día hábil. Por eso la
corrida matinal la pide una sola vez al día y no en cada refresh de 20 minutos — pedirla más seguido
bajaría el mismo archivo sin dato nuevo.
"""

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.ingesta.http import ErrorDeFuente, Reintentos, con_reintentos, crear_cliente, pedir

FUENTE = "CAFCI"

RE_FILENAME = re.compile(r'filename="?(\d{8})_[^"]*"?')

TIMEOUT_SEGUNDOS = 30.0
POLITICA = Reintentos(intentos=3, espera_base=3)


@dataclass(frozen=True, slots=True)
class RespuestaCafci:
    contenido: bytes
    fecha_planilla_cruda: str
    """`YYYYMMDD` tal como aparece en el nombre del archivo, sin parsear a `date` acá — eso lo hace
    quien orquesta la ingesta, para que este cliente no dependa de un formato de fecha."""


def _fecha_de(content_disposition: str | None) -> str:
    if not content_disposition:
        raise ErrorDeFuente(
            "la respuesta no trae content-disposition: no hay forma de saber de qué fecha es "
            "la planilla",
            reintentable=False,
        )
    coincidencia = RE_FILENAME.search(content_disposition)
    if not coincidencia:
        raise ErrorDeFuente(
            f"el nombre del archivo no tiene el formato esperado: {content_disposition!r}",
            reintentable=False,
        )
    return coincidencia.group(1)


def _vacio(respuesta: object) -> bool:
    return len(respuesta.content) == 0  # type: ignore[attr-defined]


async def descargar_planilla(
    url: str,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> RespuestaCafci:
    """Baja la planilla diaria y extrae la fecha declarada por la fuente. No parsea el contenido:
    eso es trabajo de `parser.py`. `dormir` es inyectable para que los tests de reintentos no
    esperen de verdad — mismo criterio que el resto de `app/ingesta/`."""

    async def intento():
        return await pedir(cliente, "GET", url, fuente=FUENTE, vacio_es_fallo=_vacio)

    async with crear_cliente(timeout=TIMEOUT_SEGUNDOS) as cliente:
        respuesta = await con_reintentos(
            intento, descripcion=f"{FUENTE} planilla diaria", politica=POLITICA, dormir=dormir
        )

    fecha_cruda = _fecha_de(respuesta.headers.get("content-disposition"))
    return RespuestaCafci(contenido=respuesta.content, fecha_planilla_cruda=fecha_cruda)
