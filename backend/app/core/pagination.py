"""Paginación por cursor, obligatoria en toda colección del API.

Ninguna colección devuelve el conjunto completo: el universo son ~1.700 especies y las
colecciones de cashflow son mucho más grandes. El cursor es opaco a propósito —el cliente lo
devuelve tal cual y no depende de su forma, así que la clave de orden puede cambiar sin romper
a nadie.

Patrón de uso desde un endpoint:

    filas = await conn.fetch(consulta, params.limit + 1)     # una de más, para saber si hay página
    return build_page(filas, params.limit, lambda f: {"k": f["fecha"], "id": f["id"]})

Se pide `limit + 1` filas y se devuelven `limit`: la fila sobrante no se muestra, sólo delata
que existe una página siguiente.
"""

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


class InvalidCursorError(ValueError):
    """El cursor recibido no es uno emitido por este servicio."""


@dataclass
class CursorParams:
    """Parámetros de paginación de cualquier colección. Se inyecta con `Depends(CursorParams)`."""

    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT
    cursor: Annotated[str | None, Query()] = None

    def decoded_cursor(self) -> dict[str, Any] | None:
        return decode_cursor(self.cursor) if self.cursor else None


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(payload: dict[str, Any]) -> str:
    crudo = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(crudo).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        relleno = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + relleno))
    except Exception as exc:
        raise InvalidCursorError("El cursor no es válido o fue alterado.") from exc
    if not isinstance(payload, dict):
        raise InvalidCursorError("El cursor no es válido o fue alterado.")
    return payload


def build_page[T](
    rows: list[T],
    limit: int,
    cursor_from: Callable[[T], dict[str, Any]],
) -> Page[T]:
    """Arma la página a partir de las `limit + 1` filas pedidas.

    `cursor_from` recibe la última fila devuelta y produce el payload del cursor: la clave de
    orden más un desempate estable, para que dos filas con la misma clave no se pisen.
    """
    hay_pagina_siguiente = len(rows) > limit
    items = rows[:limit]
    next_cursor = encode_cursor(cursor_from(items[-1])) if hay_pagina_siguiente and items else None
    return Page(items=items, next_cursor=next_cursor)
