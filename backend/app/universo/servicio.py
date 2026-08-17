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
resultado de `sanear_universo` y no la lectura cruda. La deduplicación vive en
`UniversoSaneado.emisiones()`, y recibe los descartes de la sanidad como lo que son, el veredicto de
la capa de más abajo.

## Por qué el tipo de cambio se calcula antes que la deduplicación

El orden de `sanear` es: segmentar, derivar el tipo de cambio, normalizar el volumen, evaluar
sanidad. **La deduplicación desempata por volumen normalizado**, así que si el tipo de cambio se
calculara después, el representante de cada emisión se elegiría con la columna vacía y el desempate
volvería a caer en el ticker sin que nada lo dijera.

El tipo de cambio se deriva sobre el universo segmentado entero, descartados incluidos, que es el
mismo conjunto que usa el motor. No hace falta sacarles los descartes: la sanidad juzga el
*rendimiento* y no el precio, y contra un precio mal cargado ya protege el chequeo de rango de
`cambio._cocientes` — un cociente fuera de rango no entra a la mediana y se nombra aparte.
"""

import asyncio
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.ingesta.alertas import Alerta, Severidad, precio_desactualizado
from app.ingesta.byma.normalizacion import FilaIndice
from app.universo.cambio import TipoDeCambio, derivar_tipo_de_cambio, normalizar_volumen
from app.universo.emisiones import UniversoDeduplicado, deduplicar
from app.universo.indice import leer_indices
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

# Cuántas especies se nombran en el cuerpo de una alerta. Mismo criterio que `cambio.py`: el número
# entero es lo que se mira y la lista completa va en el detalle.
MUESTRA_ALERTA = 6

CODIGO_LEY_EN_CONFLICTO = "ley_en_conflicto"
CODIGO_EMISOR_ESCRITO_DISTINTO = "emisor_escrito_distinto"


@dataclass(frozen=True, slots=True)
class UniversoSaneado:
    """El universo comparable con su veredicto de sanidad, más lo que quedó afuera y por qué."""

    especies: list[EspecieUniverso] = field(default_factory=list)
    sanidad: Sanidad = field(default_factory=Sanidad)
    renta_variable: int = 0
    sin_segmento: list[str] = field(default_factory=list)
    leidos: int = 0
    cambio: TipoDeCambio = field(default_factory=TipoDeCambio)
    """El tipo de cambio implícito del día. Viaja con el universo porque es el que normalizó el
    volumen de estas especies: separarlos dejaría números en dólares sin el número que los
    produjo."""

    ley_en_conflicto: list[str] = field(default_factory=list)
    """Especies cuya ley quedó vacía porque las dos fuentes declaran leyes distintas."""

    emisor_escrito_distinto: list[str] = field(default_factory=list)
    """Especies cuyo emisor las dos fuentes escriben distinto. No vacía nada: gana la vista."""

    huerfanas: list[str] = field(default_factory=list)
    """Especies cuya última fila de precios no es de la corrida más reciente (F-010, relevamiento
    de confiabilidad de datos del 16/08/2026). No se excluyen del universo ni de `operables()`: se
    declaran con la alerta `precio_desactualizado`, mismo criterio que el resto de la sanidad."""

    @property
    def alertas(self) -> list[Alerta]:
        """Las de la sanidad, las del tipo de cambio y las del cruce de fuentes, juntas.

        Van en la misma lista porque quien las lee —la barra de estado del dato de F-013— tiene una
        sola: un universo del que no se puede comparar la liquidez está tan incompleto como uno con
        instrumentos descartados, y presentarlos en dos lugares distintos haría que uno se mire
        menos que el otro.
        """
        alertas = self.sanidad.alertas + self.cambio.alertas
        if self.ley_en_conflicto:
            alertas.append(_alerta_ley_en_conflicto(self.ley_en_conflicto))
        if self.emisor_escrito_distinto:
            alertas.append(_alerta_emisor_escrito_distinto(self.emisor_escrito_distinto))
        if self.huerfanas:
            alertas.append(
                precio_desactualizado(cantidad=len(self.huerfanas), tickers=self.huerfanas)
            )
        return alertas

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
            "huerfanas": len(self.huerfanas),
            "operables": len(self.operables()),
            "tipo_de_cambio": self.cambio.como_dict(),
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


def sanear(
    segmentacion: Segmentacion,
    leidos: int,
    indices: Sequence[FilaIndice] | None = None,
) -> UniversoSaneado:
    """La parte pura: sobre un universo ya segmentado, deriva el tipo de cambio y corre las capas.

    Está separada de `sanear_universo` para que toda la lógica se pueda probar sin Postgres y sin
    red, que es la misma división que `armar_consolidacion` / `consolidar` en F-007. `indices` entra
    por parámetro justamente por eso: es lo único de acá que sale de una fuente viva, y sin ellos
    todo lo demás sale igual.
    """
    cambio = derivar_tipo_de_cambio(segmentacion.especies, indices)
    especies = normalizar_volumen(segmentacion.especies, cambio)
    return UniversoSaneado(
        especies=especies,
        sanidad=evaluar_sanidad(especies),
        renta_variable=segmentacion.renta_variable,
        sin_segmento=segmentacion.sin_segmento,
        leidos=leidos,
        cambio=cambio,
        ley_en_conflicto=segmentacion.ley_en_conflicto,
        emisor_escrito_distinto=segmentacion.emisor_escrito_distinto,
        huerfanas=segmentacion.huerfanas,
    )


def _alerta_ley_en_conflicto(especies: Sequence[str]) -> Alerta:
    """Dos fuentes oficiales diciendo cosas distintas sobre el eje de riesgo más caro de equivocar.

    No es un aviso cosmético: la ley decide en qué tribunal se cobra, y una cartera armada creyendo
    que un papel es ley extranjera cuando es local tiene un riesgo que nadie declaró. Por eso la ley
    queda vacía y esto sale como advertencia: el hueco es visible y el dato falso no existe.
    """
    return Alerta(
        codigo=CODIGO_LEY_EN_CONFLICTO,
        mensaje=(
            f"{len(especies)} especies tienen ley distinta según IAMC y según la tabla curada "
            f"({', '.join(especies[:MUESTRA_ALERTA])}): su ley queda vacía porque elegir una de "
            "las dos sin ir al prospecto sería inventar el dato."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar la ley en el prospecto de esas emisiones y corregir la fuente que esté mal: "
            "hasta entonces no se pueden filtrar ni proponer por legislación."
        ),
        detalle={"cantidad": len(especies), "especies": list(especies)},
    )


def _alerta_emisor_escrito_distinto(especies: Sequence[str]) -> Alerta:
    """Informativa a propósito: no falta ningún dato, sobra una forma de escribirlo."""
    return Alerta(
        codigo=CODIGO_EMISOR_ESCRITO_DISTINTO,
        mensaje=(
            f"{len(especies)} especies tienen el nombre del emisor escrito distinto en IAMC y en "
            f"la tabla curada ({', '.join(especies[:MUESTRA_ALERTA])}): se muestra el de IAMC. No "
            "se los empareja por regla de strings, que sería decidir si S.A. y S.A.U. son lo mismo."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={"cantidad": len(especies), "especies": list(especies)},
    )


async def sanear_universo(conn: Any, *, con_contraste: bool = False) -> UniversoSaneado:
    """Lee el universo, deriva el tipo de cambio del día y le aplica las dos capas de sanidad.

    **El índice de BYMA no se pide salvo que lo pidan.** El contraste es lo único de este servicio
    que sale a la red, y sólo dos de los siete endpoints de `/universo` lo exponen: los otros cinco
    resuelven con `cambio.valor`, que se deriva del propio universo y no necesita a BYMA. Traerlo
    siempre acoplaba consultas puramente SQL a que una fuente externa esté viva — y no sólo por
    latencia: `descargar_endpoint` reintenta cinco veces con 90 s de timeout, así que un BYMA
    colgado bloqueaba hasta ocho minutos endpoints que no lo usan para nada. Lo mismo hacía que la
    suite offline saliera a Internet sin que ningún test lo hubiera decidido.

    Cuando sí se pide, **la lectura y el índice van en paralelo**: no dependen uno del otro y en
    serie la corrida tarda 0,55 s contra 0,20 s, medido sobre el universo real. `leer_indices`
    devuelve una lista vacía ante cualquier fallo, así que el `gather` nunca ve una excepción de
    BYMA y el implícito se calcula igual: **el contraste es un control, no una fuente**.
    """
    if con_contraste:
        filas, indices = await asyncio.gather(leer_universo(conn), leer_indices())
    else:
        filas, indices = await leer_universo(conn), None
    saneado = sanear(segmentar(filas), leidos=len(filas), indices=indices)
    logger.info(
        "universo_saneado",
        leidos=saneado.leidos,
        evaluados=len(saneado.especies),
        descartados=len(saneado.sanidad.descartados),
        sin_segmento=len(saneado.sin_segmento),
        tipo_de_cambio=saneado.cambio.valor,
        pares_tipo_de_cambio=saneado.cambio.pares,
    )
    return saneado
