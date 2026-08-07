"""El universo saneado como una sola llamada: leer, segmentar y aplicar las dos capas — F-010.

Es el equivalente de `corrida.py` en la consolidación: junta la capa de lectura con las funciones
puras y arma lo que se reporta. La conexión llega por parámetro y no de `app.state` para que un job
pueda invocarlo fuera del ciclo HTTP, igual que hace `consolidar()`.

**El universo saneado incluye a los descartados.** Se marca cada especie con `dato_sano` en vez de
sacarla de la lista, porque un instrumento con el precio mal escalado en la fuente tiene que poder
auditarse: si desapareciera, nadie podría contestar por qué VSCQD no está. Lo que cambia es que no
se propone. `operables()` es el corte para quien necesita la lista corta.

F-011 y F-012 se enganchan acá: las dos parten del universo **ya saneado** —deduplicar tomando como
representante de una emisión a la especie con el precio roto, o derivar el tipo de cambio de un
precio mal escalado, sería propagar el error en vez de contenerlo— así que ambas consumen el
resultado de `sanear_universo` y no la lectura cruda. F-011 ya lo hace: la deduplicación vive en
`UniversoSaneado.emisiones()`, y recibe los descartes de la sanidad como lo que son, el veredicto de
la capa de más abajo.
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.ingesta.alertas import Alerta
from app.universo.emisiones import UniversoDeduplicado, deduplicar
from app.universo.lectura import leer_universo
from app.universo.sanidad import Descarte, MotivoDescarte, Sanidad, evaluar_sanidad
from app.universo.segmentacion import (
    DESC_SEGMENTO,
    NATURALEZA_TASA,
    NOMBRE_NATURALEZA,
    EspecieUniverso,
    Segmentacion,
    segmentar,
)

logger = structlog.get_logger()

# Cuántos tickers sin segmento se nombran en el resumen. La lista completa no aporta: si son cientos
# es porque una fuente cambió, y para eso alcanza con el número y una muestra.
MUESTRA_SIN_SEGMENTO = 10


@dataclass(frozen=True, slots=True)
class UniversoSaneado:
    """El universo comparable con su veredicto de sanidad, más lo que quedó afuera y por qué."""

    especies: list[EspecieUniverso] = field(default_factory=list)
    sanidad: Sanidad = field(default_factory=Sanidad)
    renta_variable: int = 0
    sin_segmento: list[str] = field(default_factory=list)
    leidos: int = 0

    @property
    def alertas(self) -> list[Alerta]:
        return self.sanidad.alertas

    @property
    def descartes(self) -> list[Descarte]:
        return self.sanidad.descartes

    def operables(self) -> list[EspecieUniverso]:
        """Lo que se puede proponer: con rendimiento publicado y con el dato en un rango posible.

        Son dos condiciones y no una: la sanidad no descarta lo que no tiene rendimiento —no opina
        sobre lo que la fuente no publicó— así que el faltante se filtra acá.
        """
        descartados = self.sanidad.descartados
        return [
            e for e in self.especies if e.rendimiento is not None and e.ticker not in descartados
        ]

    def emisiones(self) -> UniversoDeduplicado:
        """El mismo universo visto por emisión: la doble vista de F-011.

        Se calcula sobre `especies` —el universo entero, descartados incluidos— y no sobre
        `operables()`: deduplicar no es filtrar. Lo que la sanidad aporta es el veredicto que
        impide que una especie descartada represente a su emisión, y por eso viaja aparte.
        """
        return deduplicar(self.especies, self.sanidad.descartados)

    def resumen(self) -> dict[str, object]:
        """Los conteos que hacen falta para saber si el universo de esta corrida sirve.

        Lleva el desglose por segmento porque un descarte sólo se lee contra su unidad: seis
        descartes en CER y seis en tasa fija no son el mismo problema, y el total los taparía.
        """
        descartados = self.sanidad.descartados
        evaluados_por_segmento = Counter(e.segmento for e in self.especies)
        descartados_por_segmento = Counter(d.segmento for d in self.descartes)
        return {
            "leidos": self.leidos,
            "renta_variable": self.renta_variable,
            "sin_segmento": {
                "cantidad": len(self.sin_segmento),
                "muestra": self.sin_segmento[:MUESTRA_SIN_SEGMENTO],
            },
            "evaluados": len(self.especies),
            "descartados": len(descartados),
            "operables": len(self.operables()),
            "por_capa": {
                motivo.value: len(self.sanidad.por_motivo(motivo)) for motivo in MotivoDescarte
            },
            "por_segmento": [
                {
                    "segmento": segmento,
                    "descripcion": DESC_SEGMENTO[segmento],
                    "naturaleza": NOMBRE_NATURALEZA[NATURALEZA_TASA[segmento]],
                    "evaluados": evaluados_por_segmento[segmento],
                    "descartados": descartados_por_segmento[segmento],
                }
                for segmento in sorted(evaluados_por_segmento)
            ],
        }

    def como_dict(self) -> dict[str, object]:
        """El resumen más las alertas. Los descartes no viajan acá: son una colección propia."""
        return {
            "resumen": self.resumen(),
            "alertas": [a.como_dict() for a in self.alertas],
        }


def sanear(segmentacion: Segmentacion, leidos: int) -> UniversoSaneado:
    """La parte pura: sobre un universo ya segmentado, corre las dos capas y arma el resultado.

    Está separada de `sanear_universo` para que toda la lógica se pueda probar sin Postgres, que es
    la misma división que `armar_consolidacion` / `consolidar` en F-007.
    """
    return UniversoSaneado(
        especies=segmentacion.especies,
        sanidad=evaluar_sanidad(segmentacion.especies),
        renta_variable=segmentacion.renta_variable,
        sin_segmento=segmentacion.sin_segmento,
        leidos=leidos,
    )


async def sanear_universo(conn: Any) -> UniversoSaneado:
    """Lee el universo de la vista `resumen`, lo segmenta y le aplica las dos capas de sanidad."""
    filas = await leer_universo(conn)
    saneado = sanear(segmentar(filas), leidos=len(filas))
    logger.info(
        "universo_saneado",
        leidos=saneado.leidos,
        evaluados=len(saneado.especies),
        descartados=len(saneado.sanidad.descartados),
        sin_segmento=len(saneado.sin_segmento),
    )
    return saneado
