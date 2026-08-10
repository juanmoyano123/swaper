"""Costo real de rotar: arancel + spread bid/ask en las dos patas — F-035.

Port de `costo_rotacion` (`tools/mercado.py`), con una divergencia deliberada contra el CLI: ahí un
spread faltante cuenta como cero y el costo devuelto es un "piso" (subestimado, nunca sobreestimado
— ver el docstring de `costo_rotacion`). Acá NO: sin dos puntas vivas en alguna pata,
`verificable=False` y el costo entero viaja `None`. Mostrar un costo parcial como si fuera el costo
real sería rellenar el hueco entre lo que la fuente dice y lo que se necesita que diga — exactamente
lo que prohíbe la regla 1/11 del dominio (nunca se inventa un dato; sin certeza, el espacio va en
blanco).

Módulo puro, sin I/O: quien lo llama ya resolvió las puntas (`app/rotaciones/puntas.py`).
"""

from dataclasses import dataclass

from app.rotaciones.constantes import ARANCEL_POR_PATA, MAX_RELACION_PUNTAS, UMBRAL_COSTO_ELEVADO


def spread_pct(px_bid: float | None, px_ask: float | None) -> float | None:
    """El spread bid/ask como porcentaje del punto medio, o `None` si no hay dos puntas vivas.

    `None` cuando falta alguna punta, cuando están cruzadas o invertidas (`ask <= bid`), o cuando
    la relación `ask/bid` alcanza `MAX_RELACION_PUNTAS`: puntas en escalas distintas (ej. bid 125 /
    ask 127.000) no describen un spread real de un mismo mercado.
    """
    if px_bid is None or px_ask is None:
        return None
    if not (px_bid > 0 and px_ask > px_bid):
        return None
    if px_ask / px_bid >= MAX_RELACION_PUNTAS:
        return None
    return (px_ask - px_bid) / ((px_ask + px_bid) / 2) * 100


@dataclass(frozen=True, slots=True)
class CostoRotacion:
    """El costo real de ejecutar una rotación candidata, o el aviso de que no es verificable.

    `verificable` es `True` sólo cuando las dos patas (origen y destino) tienen spread real: con
    una sola pata sin puntas vivas, `total_pct`, `elevado` y `payback_meses` viajan `None` en vez
    de calcularse sobre un supuesto.
    """

    arancel_pct_por_pata: float
    spread_origen_pct: float | None
    spread_destino_pct: float | None
    total_pct: float | None
    verificable: bool
    elevado: bool | None
    payback_meses: float | None

    def como_dict(self) -> dict[str, object]:
        return {
            "arancel_pct_por_pata": self.arancel_pct_por_pata,
            "spread_origen_pct": self.spread_origen_pct,
            "spread_destino_pct": self.spread_destino_pct,
            "total_pct": self.total_pct,
            "verificable": self.verificable,
            "elevado": self.elevado,
            "payback_meses": self.payback_meses,
        }


def calcular_costo(
    spread_origen: float | None, spread_destino: float | None, d_rend_pp: float
) -> CostoRotacion:
    """El costo de rotar: dos patas de arancel más media punta de spread en cada una.

    `d_rend_pp` es `Candidata.d_rend_pp`, ya en PUNTOS PORCENTUALES (no una fracción). El payback
    sale de `total_pct / d_rend_pp * 12`, equivalente en unidades a la fórmula del CLI
    (`costo_fracción / d_rend_fracción * 12`, `tools/detectar_swaps.py:328`) porque `total_pct` y
    `d_rend_pp` comparten el mismo factor 100 que se cancela en el cociente.
    """
    arancel_pct = ARANCEL_POR_PATA * 100
    spread_o = round(spread_origen, 2) if spread_origen is not None else None
    spread_d = round(spread_destino, 2) if spread_destino is not None else None

    if spread_o is None or spread_d is None:
        return CostoRotacion(
            arancel_pct_por_pata=round(arancel_pct, 2),
            spread_origen_pct=spread_o,
            spread_destino_pct=spread_d,
            total_pct=None,
            verificable=False,
            elevado=None,
            payback_meses=None,
        )

    total_pct = round(2 * arancel_pct + spread_o / 2 + spread_d / 2, 2)
    elevado = total_pct > UMBRAL_COSTO_ELEVADO * 100
    payback_meses = round(total_pct / d_rend_pp * 12, 1) if d_rend_pp > 0 else None

    return CostoRotacion(
        arancel_pct_por_pata=round(arancel_pct, 2),
        spread_origen_pct=spread_o,
        spread_destino_pct=spread_d,
        total_pct=total_pct,
        verificable=True,
        elevado=elevado,
        payback_meses=payback_meses,
    )
