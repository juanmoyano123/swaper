"""Dict crudo de BYMA → fila canónica. Funciones puras: sin red, sin estado, sin excepciones.

Acá viven las reglas del dominio que le tocan a esta fuente. La que más pesa: la moneda de
cotización sale de `denominationCcy`, el campo que la fuente declara, y de ningún otro lado. En
particular nunca del sufijo del ticker — no existe en este módulo ninguna función que reciba un
`symbol` y devuelva una moneda, y así tiene que seguir.

La otra regla que gobierna todo el archivo: ausente, `None` o cadena vacía se normaliza a `None`, y
`None` es lo que hace que un campo cuente como faltante en `medir_cobertura`. Un `0` numérico no es
lo mismo que un hueco -un bono que no operó tiene volumen cero, y esconderlo como faltante taparía
justo el instrumento que hay que poder ver-, así que los campos numéricos preservan el cero.
"""

from collections.abc import Mapping
from typing import Any, NotRequired, TypedDict


class FilaRueda(TypedDict):
    """Fila canónica de los cuatro endpoints de especies (ONs, bonos, cedears, acciones)."""

    ticker: str | None
    descripcion: str | None
    subtipo: str | None
    mercado: str | None
    moneda_cotizacion: str | None
    plazo_liquidacion: str | None
    precio_compra: float | None
    cantidad_compra: int | None
    precio_venta: float | None
    cantidad_venta: int | None
    precio_ultimo: float | None
    precio_cierre: float | None
    precio_cierre_anterior: float | None
    precio_apertura: float | None
    precio_maximo: float | None
    precio_minimo: float | None
    vwap: float | None
    volumen_nominal: float | None
    monto_operado: float | None
    operaciones: int | None
    vencimiento: str | None
    dias_al_vencimiento: int | None

    origen_precio: NotRequired[str]
    """Experimento data912: 'data912' | 'data912-arrastre' cuando `consolidacion/overlay.py` pisó
    el precio de esta fila; ausente cuando el precio sigue siendo el de BYMA.
    `normalizar_fila_rueda` nunca lo setea — es el overlay, río abajo, el único que lo escribe."""


class FilaIndice(TypedDict):
    """Fila canónica de `index-price`: el índice dólar y afines que F-012 usa de contraste."""

    indice: str | None
    descripcion: str | None
    valor: float | None
    cierre_anterior: float | None
    variacion: float | None
    maximo: float | None
    minimo: float | None
    fecha: str | None
    es_tasa: bool | None


# Sobre qué campos se mide la cobertura (decisión 9 del plan). Moneda y plazo habilitan la regla
# de dominio "nada se compara entre monedas sin normalizar"; puntas y cierre son el corazón del
# output; vencimiento delata cuándo BYMA no publica lo que F-007 esperaría heredar.
CAMPOS_COBERTURA_ESPECIES = (
    "ticker",
    "moneda_cotizacion",
    "plazo_liquidacion",
    "precio_cierre",
    "precio_compra",
    "precio_venta",
    "monto_operado",
    "vencimiento",
)
CAMPOS_COBERTURA_INDICES = ("indice", "valor")


def _conservar(valor: object) -> Any:
    """Ausente, `None` o cadena vacía → `None`. Cualquier otra cosa viaja tal cual, sin traducir.

    Es la función que sostiene `plazo_liquidacion` (`settlementType`, "1"/"2" sin mapear) y
    `moneda_cotizacion` (`denominationCcy`, "ARS"/"USD"/"EXT" sin interpretar): traducir acá sería
    tomar una decisión que no corresponde a esta feature.
    """
    if valor is None:
        return None
    if isinstance(valor, str):
        texto = valor.strip()
        return texto if texto else None
    return valor


def _numero(valor: object) -> float | None:
    """Lo que llega como número se tipa `float`. Cualquier otra cosa → `None`: no se adivina."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        numero = float(valor)
        return None if numero != numero else numero  # NaN es distinto de sí mismo
    return None


def _entero(valor: object) -> int | None:
    """Igual que `_numero` pero para cantidades: cupos, operaciones, días. Nunca se estima."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return None if valor != valor else int(valor)
    return None


def normalizar_fila_rueda(crudo: Mapping[str, object]) -> FilaRueda:
    """Fila cruda de `negociable-obligations` / `public-bonds` / `cedears` / `general-equity`."""
    return FilaRueda(
        ticker=_conservar(crudo.get("symbol")),
        descripcion=_conservar(crudo.get("securityDesc")),
        subtipo=_conservar(crudo.get("securitySubType")),
        mercado=_conservar(crudo.get("market")),
        moneda_cotizacion=_conservar(crudo.get("denominationCcy")),
        plazo_liquidacion=_conservar(crudo.get("settlementType")),
        precio_compra=_numero(crudo.get("bidPrice")),
        cantidad_compra=_entero(crudo.get("quantityBid")),
        precio_venta=_numero(crudo.get("offerPrice")),
        cantidad_venta=_entero(crudo.get("quantityOffer")),
        precio_ultimo=_numero(crudo.get("trade")),
        precio_cierre=_numero(crudo.get("closingPrice")),
        precio_cierre_anterior=_numero(crudo.get("previousClosingPrice")),
        precio_apertura=_numero(crudo.get("openingPrice")),
        precio_maximo=_numero(crudo.get("tradingHighPrice")),
        precio_minimo=_numero(crudo.get("tradingLowPrice")),
        vwap=_numero(crudo.get("vwap")),
        volumen_nominal=_numero(crudo.get("tradeVolume")),
        monto_operado=_numero(crudo.get("volumeAmount")),
        operaciones=_entero(crudo.get("numberOfOrders")),
        vencimiento=_conservar(crudo.get("maturityDate")),
        dias_al_vencimiento=_entero(crudo.get("daysToMaturity")),
    )


def normalizar_fila_indice(crudo: Mapping[str, object]) -> FilaIndice:
    """Fila cruda de `index-price`."""
    return FilaIndice(
        indice=_conservar(crudo.get("symbol")),
        descripcion=_conservar(crudo.get("description")),
        valor=_numero(crudo.get("price")),
        cierre_anterior=_numero(crudo.get("previousClosingPrice")),
        variacion=_numero(crudo.get("variation")),
        maximo=_numero(crudo.get("highValue")),
        minimo=_numero(crudo.get("minValue")),
        fecha=_conservar(crudo.get("date")),
        es_tasa=_conservar(crudo.get("isRate")),
    )
