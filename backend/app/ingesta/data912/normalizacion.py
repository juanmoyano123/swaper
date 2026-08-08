"""Dict crudo de data912 → fila canónica. Funciones puras: sin red, sin estado, sin excepciones.

data912 no declara moneda, plazo de liquidación, vencimiento ni descripción — sólo precio y libro
de una sesión. Este módulo nunca inventa ninguno de esos cuatro campos: los deja en `None`, igual
que `byma/normalizacion.py` hace con lo que BYMA no publica.

La regla que gobierna el rótulo de procedencia: `operaciones` (`q_op` en el crudo) es la cantidad
de operaciones de la sesión que trajo el payload. Si es cero o ausente, el precio (`c`) es el
último cierre conocido de una fecha que la fuente no declara — un arrastre, no un precio de hoy —
y eso se rotula distinto (regla 11 del dominio: no se afirma una frescura que no consta).
"""

from collections.abc import Mapping
from typing import Any, TypedDict

from app.ingesta.byma.normalizacion import FilaRueda


class FilaLive(TypedDict):
    """Fila canónica de los cinco tramos `live/` de especies argentinas."""

    ticker: str | None
    ultimo: float | None
    monto: float | None
    operaciones: int | None
    px_bid: float | None
    cantidad_bid: int | None
    px_ask: float | None
    cantidad_ask: int | None
    variacion_pct: float | None
    """`pct_change` del payload. Se transporta tal cual; no se deriva `cierre_anterior` de acá —
    sería un cálculo con redondeo dudoso sobre un número que la fuente no declara como cierre."""


CAMPOS_COBERTURA_LIVE = ("ticker", "ultimo", "monto")

# A qué endpoint de BYMA correspondería cada tramo, para el ticker que sólo aparece en data912:
# `armado.py` clasifica por el nombre del endpoint que trajo la fila, así que un ticker
# sólo-data912 necesita uno para poder clasificarse igual que si viniera de BYMA.
ENDPOINT_BYMA_POR_TRAMO: dict[str, str] = {
    "arg_corp": "negociable-obligations",
    "arg_bonds": "public-bonds",
    "arg_notes": "public-bonds",
    "arg_cedears": "cedears",
    "arg_stocks": "general-equity",
}


def _conservar(valor: object) -> Any:
    """Ausente, `None` o cadena vacía → `None`. Copiado de `byma/normalizacion.py` para no acoplar
    los dos módulos de fuente a un helper compartido que después uno de los dos necesite romper."""
    if valor is None:
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        return texto if texto else None
    return valor


def _numero(valor: object) -> float | None:
    """El cero se preserva: un bono con `q_op=0` sigue siendo un dato, no un hueco."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero = float(valor)
        return None if numero != numero else numero
    return None


def _entero(valor: object) -> int | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return None if valor != valor else int(valor)
    return None


def normalizar_fila_live(crudo: Mapping[str, object]) -> FilaLive:
    """Fila cruda de cualquiera de los cinco tramos `live/` — misma forma en los cinco."""
    return FilaLive(
        ticker=_conservar(crudo.get("symbol")),
        ultimo=_numero(crudo.get("c")),
        monto=_numero(crudo.get("v")),
        operaciones=_entero(crudo.get("q_op")),
        px_bid=_numero(crudo.get("px_bid")),
        cantidad_bid=_entero(crudo.get("q_bid")),
        px_ask=_numero(crudo.get("px_ask")),
        cantidad_ask=_entero(crudo.get("q_ask")),
        variacion_pct=_numero(crudo.get("pct_change")),
    )


def rotulo_de(fila: FilaLive) -> str:
    """`'data912'` si operó en la sesión del payload; `'data912-arrastre'` si no (regla 11)."""
    operaciones = fila.get("operaciones")
    return "data912" if operaciones and operaciones > 0 else "data912-arrastre"


def como_fila_rueda(fila: FilaLive, *, moneda: str | None = None) -> FilaRueda:
    """Para un ticker que sólo existe en data912: una `FilaRueda` con la metadata que la fuente no
    tiene en `None`, y sólo precio/libro/procedencia completos.

    `moneda` es la única metadata que se le puede dar sin inventarla: si el ticker ya existe en
    `instrumentos` de una corrida anterior, la moneda de cotización es un atributo estable de la
    especie (la declaró BYMA alguna vez), no un dato nuevo que data912 esté aportando. Sin ella,
    el motor de métricas nunca va a poder calcular nada para este ticker (regla 3: sin moneda no
    hay con qué descontar), así que se la pasa cuando está disponible.
    """
    return FilaRueda(
        ticker=fila["ticker"],
        descripcion=None,
        subtipo=None,
        mercado=None,
        moneda_cotizacion=moneda,
        plazo_liquidacion=None,
        precio_compra=fila["px_bid"],
        cantidad_compra=fila["cantidad_bid"],
        precio_venta=fila["px_ask"],
        cantidad_venta=fila["cantidad_ask"],
        precio_ultimo=fila["ultimo"],
        precio_cierre=None,
        precio_cierre_anterior=None,
        precio_apertura=None,
        precio_maximo=None,
        precio_minimo=None,
        vwap=None,
        volumen_nominal=None,
        monto_operado=fila["monto"],
        operaciones=fila["operaciones"],
        vencimiento=None,
        dias_al_vencimiento=None,
        origen_precio=rotulo_de(fila),
    )
