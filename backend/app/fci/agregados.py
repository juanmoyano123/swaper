"""Agregados de FCI — F-067 (comparador, categorías, gestoras). Dominio puro, probable sin
Postgres, mismo criterio que `fondos.py`: recibe `FondoFci` ya parseados, no filas crudas.

**El AUM nunca cruza monedas (regla 3).** Un FCI no cotiza en dos monedas, así que no hay
cociente del cual derivar un tipo de cambio propio — sumar `ARS` con `USD` o con `USB` sería
comparar magnitudes sin normalizar. Cada bloque de moneda es un total aparte.

**`gerente` es una llave textual, no un dato curado (regla 11).** Se agrupa tal cual viene en la
fila, sin normalizar grafías: dos filas con "Gainvest S.A." y "GAINVEST SA" quedan en gestoras
distintas porque unificarlas sería una interpretación que la fuente no declaró.

**El flujo neto no se calcula.** Requeriría la diferencia de patrimonio entre dos planillas, y la
planilla de CAFCI se pisa (wipe-and-replace, decisión del 23/08/2026): no hay serie histórica de
la que restar. Se declara `disponible: False` con el motivo, nunca se omite.
"""

from collections.abc import Iterable

from app.fci.fondos import FondoFci

FLUJO_NETO_NO_DISPONIBLE = {
    "disponible": False,
    "motivo": (
        "requiere acumular planillas diarias; el producto no acumula series históricas "
        "(decisión del 23/08/2026)"
    ),
}


def _suma_opcional(valores: Iterable[float | None]) -> float | None:
    """`None` si ningún fondo del grupo declaró el valor — no 0, que sería inventar un AUM."""
    presentes = [v for v in valores if v is not None]
    return sum(presentes) if presentes else None


def _participacion_pct(patrimonio: float | None, aum_moneda: float | None) -> float | None:
    if patrimonio is None or aum_moneda is None or aum_moneda == 0:
        return None
    return patrimonio / aum_moneda * 100


def _orden_patrimonio(fondo: FondoFci) -> tuple[int, float]:
    """Patrimonio descendente, con los fondos sin patrimonio informado al final."""
    if fondo.patrimonio is None:
        return (1, 0.0)
    return (0, -fondo.patrimonio)


def _agrupar_por_moneda(fondos: list[FondoFci]) -> dict[str, list[FondoFci]]:
    por_moneda: dict[str, list[FondoFci]] = {}
    for fondo in fondos:
        por_moneda.setdefault(fondo.moneda, []).append(fondo)
    return por_moneda


def agregados_por_categoria(fondos: list[FondoFci]) -> list[dict[str, object]]:
    """Un bloque por `tipo_renta`, roto por moneda dentro. Cada moneda lleva su propio AUM y la
    participación de cada fondo dentro de ese AUM — nunca contra el total de la categoría entera,
    que mezclaría monedas."""
    por_tipo: dict[str, list[FondoFci]] = {}
    for fondo in fondos:
        por_tipo.setdefault(fondo.tipo_renta, []).append(fondo)

    resultado: list[dict[str, object]] = []
    for tipo_renta in sorted(por_tipo):
        fondos_tipo = por_tipo[tipo_renta]
        por_moneda = _agrupar_por_moneda(fondos_tipo)

        bloques_moneda: list[dict[str, object]] = []
        for moneda in sorted(por_moneda):
            fondos_moneda = por_moneda[moneda]
            aum = _suma_opcional(f.patrimonio for f in fondos_moneda)
            fondos_ordenados = sorted(fondos_moneda, key=_orden_patrimonio)
            bloques_moneda.append(
                {
                    "moneda": moneda,
                    "aum": aum,
                    "cantidad_fondos": len(fondos_moneda),
                    "fondos": [
                        {
                            "codigo_cafci": f.codigo_cafci,
                            "fondo": f.fondo,
                            "patrimonio": f.patrimonio,
                            "participacion_pct": _participacion_pct(f.patrimonio, aum),
                        }
                        for f in fondos_ordenados
                    ],
                }
            )

        resultado.append(
            {
                "tipo_renta": tipo_renta,
                "cantidad_fondos": len(fondos_tipo),
                "por_moneda": bloques_moneda,
            }
        )
    return resultado


def agregados_por_gestora(fondos: list[FondoFci]) -> list[dict[str, object]]:
    """Un bloque por `gerente` tal cual viene en la fila (sin normalizar), roto por moneda dentro
    con el mismo criterio que `agregados_por_categoria`. El flujo neto siempre viaja declarado
    como no disponible."""
    por_gerente: dict[str | None, list[FondoFci]] = {}
    for fondo in fondos:
        por_gerente.setdefault(fondo.gerente, []).append(fondo)

    # `None` (gerente no informado) al final: no es una gestora, es un faltante.
    claves = sorted(por_gerente, key=lambda g: (g is None, g or ""))

    resultado: list[dict[str, object]] = []
    for gerente in claves:
        fondos_gestora = por_gerente[gerente]
        por_moneda = _agrupar_por_moneda(fondos_gestora)

        bloques_moneda = [
            {
                "moneda": moneda,
                "aum": _suma_opcional(f.patrimonio for f in fondos_moneda),
                "cantidad_fondos": len(fondos_moneda),
            }
            for moneda, fondos_moneda in sorted(por_moneda.items())
        ]

        resultado.append(
            {
                "gerente": gerente,
                "cantidad_fondos": len(fondos_gestora),
                "por_moneda": bloques_moneda,
                "market_share": _suma_opcional(f.market_share for f in fondos_gestora),
                "flujo_neto": FLUJO_NETO_NO_DISPONIBLE,
            }
        )
    return resultado
