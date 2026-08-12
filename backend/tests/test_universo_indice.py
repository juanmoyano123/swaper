"""De dónde sale el índice de contraste, y qué pasa cuando no sale — F-012.

Lo único que se prueba acá es la garantía que sostiene toda la feature: **BYMA no puede tumbar el
cálculo del implícito**. El contraste es un control opcional sobre un número que ya está hecho, así
que cualquier cosa que salga mal tiene que terminar en una lista vacía y en el log, nunca en una
excepción que suba.
"""

from typing import ClassVar

import httpx
import pytest
from structlog.testing import capture_logs

from app.universo import indice
from app.universo.indice import leer_indices


class ClienteFalso:
    """Se hace pasar por el `AsyncClient` de `crear_cliente`, sin abrir un socket."""

    async def __aenter__(self) -> "ClienteFalso":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(indice, "crear_cliente", ClienteFalso)


class DescargaFalsa:
    """Lo que devuelve `descargar_endpoint`: filas crudas tal como las publica BYMA."""

    filas: ClassVar[list[dict[str, object]]] = [
        {"symbol": "M", "price": 3_100_731.81},
        {"symbol": "SPMERVDT", "price": 2_040.67},
    ]


async def test_devuelve_las_filas_normalizadas_del_endpoint(monkeypatch) -> None:
    _sin_red(monkeypatch)

    async def _descarga(*_: object, **__: object) -> DescargaFalsa:
        return DescargaFalsa()

    monkeypatch.setattr(indice, "descargar_endpoint", _descarga)

    filas = await leer_indices()

    assert [f["indice"] for f in filas] == ["M", "SPMERVDT"]
    assert filas[0]["valor"] == 3_100_731.81


@pytest.mark.parametrize(
    "error",
    [
        httpx.ConnectError("sin red"),
        httpx.ReadTimeout("tardó"),
        ValueError("respuesta que no es JSON"),
    ],
    ids=["conexion", "timeout", "formato"],
)
async def test_ningun_fallo_de_byma_se_propaga(monkeypatch, error: Exception) -> None:
    """La garantía de la feature: el implícito sale del universo y no necesita a BYMA para existir.

    Se prueban tres familias distintas a propósito. El `except Exception` del módulo es ancho por
    decisión, y un test que sólo cubriera una de ellas dejaría creer que las otras se propagan.
    """
    _sin_red(monkeypatch)

    async def _falla(*_: object, **__: object):
        raise error

    monkeypatch.setattr(indice, "descargar_endpoint", _falla)

    assert await leer_indices() == []


async def test_el_fallo_queda_en_el_log_y_sin_la_url(monkeypatch) -> None:
    """Que no se propague no puede significar que no se sepa: el fallo se nombra por su tipo.

    Y se nombra **sin la URL**, que es la regla de siempre. Acá la de BYMA no lleva token, pero una
    regla que se aplica a veces es una regla que alguien va a olvidar en la fuente que sí lo lleva.
    """
    _sin_red(monkeypatch)

    async def _falla(*_: object, **__: object):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(indice, "descargar_endpoint", _falla)

    with capture_logs() as registros:
        await leer_indices()

    (registro,) = registros
    assert registro["event"] == "indice_de_contraste_no_disponible"
    assert registro["endpoint"] == "index-price"
    assert registro["error"] == "ConnectError"
    assert not any("http" in str(valor) for valor in registro.values())
