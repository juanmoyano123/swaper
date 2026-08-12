"""La ficha de un instrumento: la especie pedida más sus hermanas de liquidación — F-039.

Función pura sobre el universo ya saneado, mismo patrón que `app/universo/segmentacion.py`: recibe
la conexión, no decide nada por su cuenta y deja la deduplicación entera a
`app/universo/emisiones.py` (`UniversoDeduplicado.vivo()` / `.hermanas()`), que ya sabe qué especies
son el mismo bono. Reimplementar ese agrupamiento acá sería tener dos criterios de "misma emisión"
que podrían divergir.
"""

from collections.abc import Collection
from typing import Any

from app.universo.segmentacion import EspecieUniverso
from app.universo.servicio import sanear_universo


async def ficha_de(conn: Any, ticker: str) -> dict[str, object] | None:
    """La especie pedida y sus hermanas de liquidación, o `None` si el ticker no está hoy.

    `None` y no una ficha vacía: un ticker que no está en el universo de hoy no tiene nada que
    mostrar, y el 404 del endpoint es lo que lo dice — inventar una ficha en blanco escondería la
    diferencia entre "no cotiza" y "no se pudo traer".
    """
    saneado = await sanear_universo(conn)
    dedup = saneado.emisiones()
    vivas = {especie.ticker: especie for especie in dedup.vivo()}
    if ticker not in vivas:
        return None

    descartados = saneado.sanidad.descartados
    return {
        "ticker": ticker,
        "especie": _con_sanidad(vivas[ticker], descartados),
        "hermanas": [_con_sanidad(h, descartados) for h in dedup.hermanas(ticker)],
    }


def _con_sanidad(especie: EspecieUniverso, descartados: Collection[str]) -> dict[str, object]:
    """La especie como viaja por el API, con el mismo criterio de `dato_sano` que `vista_viva`."""
    return {**especie.como_dict(), "dato_sano": especie.ticker not in descartados}
