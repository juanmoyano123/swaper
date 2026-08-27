"""Última punta bid/ask por ticker, para el costo real de rotar — F-035.

Mismo molde que `app/renta_variable/lectura.py`: `LEFT JOIN LATERAL` contra `public.puntas`,
quedándose con la fila más reciente por ticker (`capturado_en DESC LIMIT 1`). La diferencia es el
punto de partida: acá no hay una vista de universo de la que colgar el LATERAL, así que arranca de
la lista de tickers que aparecen en las candidatas ya detectadas (origen ∪ destino) — nunca hace
falta traer más que eso.

Una fila con `fuente` terminada en `-arrastre` (F-007: la fecha del libro consolidado es incierta)
se trata como sin punta viva: una punta de fecha desconocida no es una punta viva.

**Las puntas se convierten a `float` acá, en el borde.** `public.puntas` las guarda como `numeric`,
que asyncpg entrega como `Decimal`, y `calcular_costo` las mezcla con constantes que son `float`
(el arancel) — sumar los dos tipos revienta con `TypeError` en runtime. La firma de este módulo
siempre declaró `float | None`: convertir donde el tipo se promete es lo que evita que el resto del
paquete tenga que saber de qué tipo las trajo el driver.
"""

from collections.abc import Sequence
from typing import Any

TABLA_PUNTAS = "public.puntas"

SQL_PUNTAS = (
    "SELECT tk.ticker, p.px_bid, p.px_ask, p.fuente "
    "FROM unnest($1::text[]) AS tk(ticker) "
    "LEFT JOIN LATERAL ("
    f"    SELECT px_bid, px_ask, fuente FROM {TABLA_PUNTAS} pt"
    "     WHERE pt.ticker = tk.ticker ORDER BY pt.capturado_en DESC LIMIT 1"
    ") p ON true"
)

SUFIJO_ARRASTRE = "-arrastre"


def _como_float(valor: Any) -> float | None:
    """`numeric` de Postgres llega como `Decimal`; el resto del paquete trabaja en `float`."""
    return None if valor is None else float(valor)


async def leer_puntas(
    conn: Any, tickers: Sequence[str]
) -> dict[str, tuple[float | None, float | None]]:
    """`{ticker: (px_bid, px_ask)}` con la última punta de cada ticker pedido.

    Un ticker sin fila en `puntas`, o cuya última fila viene de arrastre, sale con `(None, None)`
    — nunca se asume una punta por defecto.
    """
    if not tickers:
        return {}
    filas = await conn.fetch(SQL_PUNTAS, list(dict.fromkeys(tickers)))
    resultado: dict[str, tuple[float | None, float | None]] = {}
    for fila in filas:
        ticker = fila["ticker"]
        fuente = fila["fuente"]
        if fuente is not None and str(fuente).endswith(SUFIJO_ARRASTRE):
            resultado[ticker] = (None, None)
        else:
            resultado[ticker] = (_como_float(fila["px_bid"]), _como_float(fila["px_ask"]))
    return resultado
