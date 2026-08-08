"""Cruza BYMA con data912 por ticker, antes de `armar_consolidacion` — experimento de fuente
primaria de precios.

**Qué se pisa y qué no.** data912 sólo trae precio, volumen y libro de una sesión — no declara
moneda, plazo de liquidación, vencimiento ni descripción. Por eso el overlay pisa exactamente esos
siete campos (`CAMPOS_PISADOS`) sobre la `FilaRueda` que BYMA ya trajo, y deja la metadata intacta:
no hay forma de que data912 la aporte sin inventarla, y BYMA sigue siendo la única fuente de
`moneda_cotizacion` (regla 1 del dominio).

**Por qué se pisan todas las filas del ticker y no una sola.** Un ticker puede llegar de BYMA en
más de un plazo de liquidación (`_elegir_por_plazo` en `armado.py` decide cuál de las dos entra al
universo). Pisando las dos con el mismo precio, la elección de plazo sigue funcionando exactamente
igual río abajo — el overlay no tiene que reimplementarla.

**El rótulo de procedencia** (`origen_precio`, ver `byma/normalizacion.py`) es lo que sostiene la
regla 11 acá: un precio que data912 arrastra de una sesión sin operaciones no es un precio de hoy,
y se lo distingue con `'data912-arrastre'` en vez de `'data912'`. La fila sigue mostrándose y
calculándose — es el mismo comportamiento que cualquier monitor de mercado con el mercado
cerrado —, pero rotulada.

**Un ticker que sólo trae data912** (no está en el universo que bajó BYMA esta corrida) entra al
universo igual, en el endpoint de BYMA que le correspondería (`ENDPOINT_BYMA_POR_TRAMO`). Sin
moneda no hay con qué calcular — se le pasa la última moneda conocida de `instrumentos` si existe,
nunca una inventada — y sin cronograma la renta fija queda sin clase, como ya pasa hoy con
cualquier ticker sin cronograma.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.byma.normalizacion import FilaRueda
from app.ingesta.data912.normalizacion import (
    ENDPOINT_BYMA_POR_TRAMO,
    FilaLive,
    como_fila_rueda,
    rotulo_de,
)

# 5 % relativo: el mismo orden de magnitud que `TOLERANCIA_PARIDAD` en `consolidacion/metricas.py`,
# holgado a propósito para no gritar todos los días por diferencias de captura entre dos fuentes
# que no cierran al mismo segundo.
TOLERANCIA_CONTRASTE = 0.05

CODIGO_CONTRASTE_FUENTES = "contraste_fuentes_precio"
MUESTRA_ALERTA = 20

CAMPOS_PISADOS = (
    "precio_ultimo",
    "monto_operado",
    "operaciones",
    "precio_compra",
    "cantidad_compra",
    "precio_venta",
    "cantidad_venta",
)


@dataclass(frozen=True, slots=True)
class ResultadoOverlay:
    """El universo de BYMA con data912 superpuesto, más lo que se pudo observar del cruce."""

    especies_por_endpoint: dict[str, list[FilaRueda]]
    alertas: list[Alerta] = field(default_factory=list)
    conteos: dict[str, int] = field(default_factory=dict)
    """`pisados`, `arrastres`, `solo_data912`, `sin_precio_data912`, `contrastes` — para el log y
    para que la demo pueda medirse sin ir a buscar en la base."""


def _indice_live(live_por_tramo: Mapping[str, list[FilaLive]]) -> dict[str, tuple[str, FilaLive]]:
    """Ticker → (tramo, fila). Determinístico ante un ticker repetido entre tramos: gana la fila
    con operaciones en la sesión del payload; a igualdad, el tramo por orden alfabético — mismo
    criterio de desempate que `_colapsar` en `armado.py`.
    """
    agrupadas: dict[str, list[tuple[str, FilaLive]]] = {}
    for tramo, filas in live_por_tramo.items():
        for fila in filas:
            ticker = fila["ticker"]
            if not ticker:
                continue
            agrupadas.setdefault(ticker, []).append((tramo, fila))

    def _clave(par: tuple[str, FilaLive]) -> tuple[int, str]:
        tramo, fila = par
        operaciones = fila["operaciones"] or 0
        return (0 if operaciones > 0 else 1, tramo)

    return {ticker: min(candidatas, key=_clave) for ticker, candidatas in agrupadas.items()}


def _contraste_fuentes(muestra: list[tuple[str, float, float]], tolerancia: float) -> Alerta:
    """BYMA y data912 declaran precios distintos para el mismo ticker, más allá de la tolerancia.

    Es INFO y no ADVERTENCIA: no invalida nada — el precio elegido sigue siendo el de data912 — y
    vale la pena verlo, no actuar sobre él. Estilo `contraste_iamc` de `consolidacion/metricas.py`.
    """
    visibles = sorted(muestra, key=lambda t: t[0])[:MUESTRA_ALERTA]
    resto = len(muestra) - len(visibles)
    texto = ", ".join(f"{t} (BYMA {b:.2f} / data912 {d:.2f})" for t, b, d in visibles)
    if resto > 0:
        texto += f" y {resto} más"
    return Alerta(
        codigo=CODIGO_CONTRASTE_FUENTES,
        mensaje=(
            f"{len(muestra)} especies difieren más de {tolerancia:.0%} entre BYMA y data912: "
            f"{texto}. Se conserva el precio de data912."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={
            "cantidad": len(muestra),
            "tolerancia": tolerancia,
            "muestra": [{"ticker": t, "byma": b, "data912": d} for t, b, d in visibles],
        },
    )


def aplicar_overlay(
    especies_byma: Mapping[str, list[FilaRueda]],
    live_por_tramo: Mapping[str, list[FilaLive]],
    *,
    monedas_previas: Mapping[str, str] | None = None,
    tolerancia: float = TOLERANCIA_CONTRASTE,
) -> ResultadoOverlay:
    """Superpone data912 sobre BYMA por ticker. Ver el docstring del módulo para las reglas."""
    monedas_previas = monedas_previas or {}
    live_por_ticker = _indice_live(live_por_tramo)

    resultado: dict[str, list[FilaRueda]] = {
        endpoint: list(filas) for endpoint, filas in especies_byma.items()
    }

    # Ticker → posiciones (endpoint, índice) en `resultado`, para pisar sin recorrer todo el
    # universo por cada ticker de data912.
    indice_byma: dict[str, list[tuple[str, int]]] = {}
    for endpoint, filas in resultado.items():
        for indice, fila in enumerate(filas):
            ticker = fila["ticker"]
            if ticker:
                indice_byma.setdefault(ticker, []).append((endpoint, indice))

    conteos = {
        "pisados": 0,
        "arrastres": 0,
        "solo_data912": 0,
        "sin_precio_data912": 0,
        "contrastes": 0,
    }
    contrastes_muestra: list[tuple[str, float, float]] = []

    for ticker, (tramo, fila_live) in live_por_ticker.items():
        precio_live = fila_live["ultimo"]
        tiene_precio_valido = precio_live is not None and precio_live > 0
        posiciones = indice_byma.get(ticker)

        if posiciones is not None:
            # Ticker en ambas fuentes.
            if not tiene_precio_valido:
                # data912 no tiene un precio utilizable para esta especie: la fila de BYMA no se
                # toca (coherente con `_precio()` de armado.py — un precio de cero no es un precio).
                conteos["sin_precio_data912"] += 1
                continue

            origen = rotulo_de(fila_live)
            conteos["arrastres" if origen == "data912-arrastre" else "pisados"] += 1

            cambios = {
                "precio_ultimo": fila_live["ultimo"],
                "monto_operado": fila_live["monto"],
                "operaciones": fila_live["operaciones"],
                "precio_compra": fila_live["px_bid"],
                "cantidad_compra": fila_live["cantidad_bid"],
                "precio_venta": fila_live["px_ask"],
                "cantidad_venta": fila_live["cantidad_ask"],
                "origen_precio": origen,
            }

            hubo_contraste = False
            for endpoint, indice in posiciones:
                fila_byma = resultado[endpoint][indice]
                precio_byma = fila_byma["precio_ultimo"]
                if (
                    not hubo_contraste
                    and precio_byma is not None
                    and precio_byma > 0
                    and abs(precio_live - precio_byma) / precio_byma > tolerancia
                ):
                    contrastes_muestra.append((ticker, precio_byma, precio_live))
                    hubo_contraste = True
                resultado[endpoint][indice] = {**fila_byma, **cambios}
            if hubo_contraste:
                conteos["contrastes"] += 1

        else:
            # Ticker sólo en data912.
            if not tiene_precio_valido:
                continue
            conteos["solo_data912"] += 1
            endpoint = ENDPOINT_BYMA_POR_TRAMO[tramo]
            resultado.setdefault(endpoint, []).append(
                como_fila_rueda(fila_live, moneda=monedas_previas.get(ticker))
            )

    alertas: list[Alerta] = []
    if contrastes_muestra:
        alertas.append(_contraste_fuentes(contrastes_muestra, tolerancia))

    return ResultadoOverlay(especies_por_endpoint=resultado, alertas=alertas, conteos=conteos)
