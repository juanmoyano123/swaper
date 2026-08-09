"""Premio por legislación — port de `tools/detectar_swaps.py::tabla_spread_legislacion` — F-032.

Cuánto más rinde un Ley Argentina que un bono de ley extranjera del MISMO EMISOR y duración
comparable. La restricción a mismo emisor es lo que hace que el número signifique algo: comparar
una ON en distress contra un Global sano daría un spread que es riesgo de crédito, no premio por
ley. Sirve como vara para leer los swaps que cambian de ley: si una rotación resigna 138 bps por
pasar a Ley N.Y. y la mediana de la curva es 86 bps, esa mejora de ley se está pagando cara.

`medianas_bps` queda indexado por la **clave cruda** del segmento (`'cer'`, `'usd_hard'`...) y no
por su descripción legible (`DESC_SEGMENTO`): es la misma clave con la que `evaluar_par` la busca
(`origen.segmento`), así que no hace falta un segundo mapeo sólo para presentación. Es la decisión
menor que el plan dejó abierta.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from app.rotaciones.constantes import LEY_LOCAL, TOL_DURACION_LEY, es_extranjera
from app.rotaciones.emisores import nombre_emisor
from app.universo.segmentacion import EspecieUniverso


@dataclass(frozen=True, slots=True)
class ParDeLey:
    """Un par ley local / ley extranjera del mismo emisor y duración comparable."""

    segmento: str
    emisor: str
    ticker_local: str
    rinde_local: float
    ticker_extranjero: str
    ley_extranjera: str
    rinde_extranjero: float
    duracion_local: float
    duracion_extranjera: float
    premio_bps: int

    def como_dict(self) -> dict[str, object]:
        return {
            "segmento": self.segmento,
            "emisor": self.emisor,
            "ticker_local": self.ticker_local,
            "rinde_local": self.rinde_local,
            "ticker_extranjero": self.ticker_extranjero,
            "ley_extranjera": self.ley_extranjera,
            "rinde_extranjero": self.rinde_extranjero,
            "duracion_local": self.duracion_local,
            "duracion_extranjera": self.duracion_extranjera,
            "premio_bps": self.premio_bps,
        }


def premio_por_legislacion(
    operables: Sequence[EspecieUniverso],
    claves_emisor: Mapping[str, str],
) -> tuple[list[ParDeLey], dict[str, int]]:
    """`operables` ya viene con `rendimiento is not None` (es `saneado.operables()`); acá sólo se
    exige además `duracion is not None`, igual que el CLI (`duration_aprox.notna()`)."""
    locales = [e for e in operables if e.ley == LEY_LOCAL and e.duracion is not None]
    extranjeras = [e for e in operables if es_extranjera(e.ley) and e.duracion is not None]

    pares: list[ParDeLey] = []
    for local in locales:
        assert local.duracion is not None  # el filtro de arriba ya lo garantiza
        candidatas = [
            e
            for e in extranjeras
            if e.segmento == local.segmento
            and claves_emisor.get(e.ticker) == claves_emisor.get(local.ticker)
            and e.duracion is not None
            and abs(e.duracion - local.duracion) <= TOL_DURACION_LEY
        ]
        if not candidatas:
            continue
        # El par más comparable es el de duración más parecida.
        mejor = min(candidatas, key=lambda e: abs((e.duracion or 0.0) - local.duracion))
        assert local.rendimiento is not None and mejor.rendimiento is not None
        assert mejor.duracion is not None
        pares.append(
            ParDeLey(
                segmento=local.segmento,
                emisor=nombre_emisor(local, claves_emisor[local.ticker]),
                ticker_local=local.ticker,
                rinde_local=local.rendimiento,
                ticker_extranjero=mejor.ticker,
                ley_extranjera=mejor.ley or "",
                rinde_extranjero=mejor.rendimiento,
                duracion_local=local.duracion,
                duracion_extranjera=mejor.duracion,
                premio_bps=round((local.rendimiento - mejor.rendimiento) * 10000),
            )
        )

    if not pares:
        return [], {}

    pares.sort(key=lambda p: (p.segmento, -p.premio_bps))
    por_segmento: dict[str, list[int]] = {}
    for par in pares:
        por_segmento.setdefault(par.segmento, []).append(par.premio_bps)
    medianas = {segmento: round(median(valores)) for segmento, valores in por_segmento.items()}
    return pares, medianas
