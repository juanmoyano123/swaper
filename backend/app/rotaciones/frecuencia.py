"""Frecuencia de cobro y próximo cupón — port de `tools/cupones.py::frecuencia_pagos` y
`proximo_cupon` — F-032, adaptado a `app.calendario.cupones.Cronograma`/`Flujos` (ya agrupados,
a diferencia del cashflow crudo y el DataFrame de flujos propios del CLI).
"""

from datetime import date
from itertools import pairwise
from statistics import median

from app.calendario.cupones import Cronograma, Flujos

# Los topes están holgados a propósito: los calendarios reales se corren por fines de semana y
# feriados, un semestral no cae exacto en 182 días.
ESCALA_FRECUENCIA: tuple[tuple[int, str, int], ...] = (
    (45, "mensual", 1),
    (75, "bimestral", 2),
    (135, "trimestral", 3),
    (225, "semestral", 6),
    (400, "anual", 12),
)
# Orden de "menos frecuente que cualquier etiqueta conocida", para desempatar.
MESES_DESCONOCIDO = 99


def frecuencia_por_raiz(cronograma: Cronograma, hoy: date) -> dict[str, tuple[str, int]]:
    """`{raiz: (etiqueta, meses)}`, medida sobre los pagos FUTUROS de renta > 0 de cada raíz.

    Una raíz con menos de dos pagos futuros de renta > 0 y al menos uno → `('al vencimiento',
    MESES_DESCONOCIDO)`. Una raíz sin ningún pago futuro de renta no entra al dict (mismo criterio
    que el CLI: sale ausente, no un default).
    """
    resultado: dict[str, tuple[str, int]] = {}
    for raiz, pagos in cronograma.por_raiz.items():
        fechas = sorted({p.fecha for p in pagos if p.fecha > hoy and p.interes > 0})
        if not fechas:
            continue
        if len(fechas) < 2:
            resultado[raiz] = ("al vencimiento", MESES_DESCONOCIDO)
            continue
        dias = median((b - a).days for a, b in pairwise(fechas))
        etiqueta, meses = "irregular", MESES_DESCONOCIDO
        for tope, et, m in ESCALA_FRECUENCIA:
            if dias <= tope:
                etiqueta, meses = et, m
                break
        resultado[raiz] = (etiqueta, meses)
    return resultado


def proximo_cupon(flujos: Flujos, ticker: str, hoy: date) -> dict[str, object] | None:
    """El próximo pago futuro de `ticker` con `pct_renta > 0`, o `None`."""
    futuros = [f for f in flujos.flujos if f.ticker == ticker and f.fecha > hoy and f.pct_renta > 0]
    if not futuros:
        return None
    proximo = min(futuros, key=lambda f: f.fecha)
    return {
        "fecha": proximo.fecha,
        "dias": (proximo.fecha - hoy).days,
        "pct_renta": proximo.pct_renta,
        "pct_total": proximo.pct_total,
    }
