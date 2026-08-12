"""Deduplicación de especies de liquidación: la emisión como unidad, en doble vista — F-011.

MR46O, MR46D y MR46C son el mismo bono cotizando en pesos, en MEP y en cable. Comprar dos de ellos
es comprar el mismo bono dos veces creyendo que se diversifica, y un límite de concentración que
cuente tres posiciones donde hay una está midiendo mal el riesgo.

**Deduplicar no es descartar: es tener dos vistas del mismo universo.**

- **Colapsada** — una fila por emisión. Es la que usa el armador y la que cuenta para
  concentración, porque ahí una emisión tiene que valer uno.
- **Viva** — todas las especies, cada una con lo suyo. Es la que usa el optimizador, porque los
  swaps de perfil rotan justamente entre especies de la misma emisión: pasar de MEP a Cable es
  cambiar de especie sin cambiar de bono, y una vista colapsada no lo dejaría ni ver.

Las dos llevan la clave de emisión explícita (`EspecieUniverso.raiz`). Ésa es la única forma de que
el armador pueda avisar que MR46C no suma diversificación sobre un MR46D que la cartera ya tiene.

Portado de `tools/segmentos.py:399-444` (`deduplicar_emisiones`). F-011 lo dejó con **un criterio
menos** —el desempate por volumen, que necesitaba el tipo de cambio— y F-012 lo completó.

## Qué especie representa a la emisión

1. **Chequeo de sanidad primero.** La misma emisión tiene la misma duración. Si las duraciones del
   grupo difieren más de un 5 %, **no son la misma emisión** —son emisiones distintas que comparten
   raíz— y el grupo no se colapsa: sus especies quedan enteras también en la vista colapsada. Es lo
   que evita fusionar dos bonos distintos en una sola fila.
2. **El dato sano manda.** Una especie que la sanidad de F-010 descartó no puede representar a su
   emisión: sería elegir como cara visible del bono a la especie con el precio mal escalado. Por eso
   la deduplicación parte del universo **ya saneado** y no de la lectura cruda.
3. **Completitud de datos.** A igualdad de sanidad gana la especie con más campos presentes entre
   vencimiento, ley, moneda de pago y emisor: los cuatro son atributos de la emisión, así que la
   especie que más de ellos tenga es la que mejor la describe.
4. **Liquidez.** A igualdad de completitud gana la que más se opera, y ese número es el volumen
   **en dólares** (`volumen_usd`), nunca el crudo. El comentario del motor dice por qué: *"con el
   volumen crudo siempre ganaba la especie en pesos por el tipo de cambio, no por liquidez"* — la
   especie en pesos muestra ~1.500 veces más volumen porque el número está en otra unidad. Ese
   volumen normalizado lo produce F-012 (`cambio.normalizar_volumen`) y llega en `EspecieUniverso`.
5. **El ticker, de último recurso.** Cuando ninguna de las hermanas se operó —o cuando no se pudo
   normalizar su volumen— decide el orden alfabético. Es arbitrario y se sabe: lo único que se le
   pide es ser estable, para que dos corridas sobre el mismo universo elijan el mismo representante.

## Lo que el desempate por liquidez arregló, y lo que no

El desempate decide **todos** los grupos multiespecie, porque las hermanas empatan en completitud:
los cuatro campos son de la emisión y vienen iguales en las tres. Eso arrastra un efecto que
importa: IAMC publica la TIR **sólo en el ticker que su informe nombra**, y si ese ticker no gana el
desempate, la fila colapsada queda sin rendimiento y el armador no la propone, aunque el número
exista en la vista viva.

Medido sobre el universo real, enchufar el volumen normalizado bajó ese número de **199 a 146** de
431 emisiones, cambiando de representante en 190. De las 146 que siguen sin rendimiento, 28 son
grupos donde ninguna especie se operó —el desempate no tiene con qué decidir— y 118 son grupos donde
la especie más líquida sencillamente **no es** la que IAMC nombra.

**Ese resto no se corrige acá.** Preferir a la especie que publica rendimiento sería un quinto
criterio que el motor no tiene, y agregarlo por cuenta propia sería cambiar el criterio de armado
sin que nadie lo haya decidido. Se sigue contando y alertando en cada corrida
(`rendimiento_perdido_al_colapsar`), para que la decisión se tome mirando el número.
"""

from collections import defaultdict
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.raiz import raiz_emision
from app.universo.segmentacion import EspecieUniverso

# 5 % de diferencia entre las duraciones de un grupo. Por encima de eso no son la misma emisión.
TOLERANCIA_DURACION = 0.05

# Piso del divisor del chequeo de duración, portado tal cual del motor. Con duraciones en cero o
# negativas —que no son duraciones— la dispersión se dispara y el grupo no se colapsa, que es el
# lado correcto para caer: ante la duda, no se fusiona.
PISO_DIVISION = 1e-9

# Los atributos que son de la emisión y no de la especie. Cuántos de ellos tiene cargados una
# especie es lo que mide cuán bien describe a su emisión.
CAMPOS_COMPLETITUD: tuple[str, ...] = ("vencimiento", "ley", "moneda_cupon", "emisor")

# Los códigos de alerta de la deduplicación. Viven acá y no en `app/ingesta/alertas.py` porque no
# son de una corrida de ingesta: no hablan de una fuente que falló, hablan de cómo quedó armado el
# universo. Quien las agrupe o las filtre usa estos códigos.
CODIGO_ESPECIES_COLAPSADAS = "especies_colapsadas"
CODIGO_EMISION_NO_COLAPSADA = "emision_no_colapsada"
CODIGO_RENDIMIENTO_PERDIDO_AL_COLAPSAR = "rendimiento_perdido_al_colapsar"
CODIGO_MISMA_EMISION = "misma_emision"

# Cuántos tickers se nombran en el cuerpo de una alerta. La lista entera va en el detalle.
MUESTRA_ALERTA = 6


@dataclass(frozen=True, slots=True)
class Emision:
    """Un bono con todas sus especies de liquidación, y cuál de ellas lo representa.

    Es la unidad de la vista colapsada. Lleva las especies enteras y no sólo el representante
    porque el armador necesita poder contestar "¿cuál de las tres compro?" después de haber contado
    la emisión una sola vez.
    """

    raiz: str
    """La clave de emisión. Explícita en las dos vistas: es lo que las hace conmensurables."""

    especies: list[EspecieUniverso]
    """Todas las especies del grupo, ordenadas por ticker."""

    representante: EspecieUniverso | None = None
    """La especie que ocupa la fila colapsada. `None` cuando el chequeo de duración dice que estas
    especies no son la misma emisión: ahí no hay a quién elegir, porque no hay una sola emisión."""

    dispersion_duracion: float | None = None
    """Cuánto difieren las duraciones del grupo, en fracción. `None` cuando menos de dos especies
    publican duración: sin dos números no hay nada que comparar, y eso no es evidencia en contra."""

    @property
    def colapsada(self) -> bool:
        return self.representante is not None

    @property
    def tickers(self) -> list[str]:
        return [e.ticker for e in self.especies]

    @property
    def colapsadas(self) -> int:
        """Cuántas especies dejaron de ocupar una fila propia en la vista del armador."""
        return len(self.especies) - 1 if self.colapsada else 0

    @property
    def perdio_el_rendimiento_al_colapsar(self) -> bool:
        """Si la emisión tiene rendimiento publicado pero su representante no lo trae.

        Es un efecto colateral del desempate y no un error: IAMC publica la TIR sólo en el ticker
        que su informe nombra, así que las hermanas empatan en completitud y decide la liquidez; si
        la especie más operada no es la que trae el número, la fila colapsada queda sin él. El
        armador no propone lo que no tiene rendimiento, así que la emisión desaparece de su lista
        aunque el dato exista en la vista viva.

        No se corrige acá: corregirlo sería agregar un quinto criterio que el motor no tiene, y eso
        es una decisión de dominio. Se cuenta y se alerta, que es lo que corresponde ante algo que
        se sabe y no se puede resolver sin inventar un criterio.
        """
        if self.representante is None:
            return False
        return self.representante.rendimiento is None and any(
            e.rendimiento is not None for e in self.especies
        )

    def filas_colapsadas(self) -> list[EspecieUniverso]:
        """Lo que esta emisión aporta a la vista colapsada.

        Una fila cuando el grupo es una emisión; todas cuando el chequeo de duración dijo que no lo
        es. Colapsar igual sería fusionar dos bonos distintos, que es peor que duplicar uno.
        """
        return [self.representante] if self.representante is not None else list(self.especies)


@dataclass(frozen=True, slots=True)
class UniversoDeduplicado:
    """El universo en sus dos vistas, indexado por clave de emisión.

    `por_raiz` es la única estructura que se guarda: la vista colapsada, la viva y el listado
    ordenado se derivan de ella. Un índice y una lista con lo mismo adentro se desincronizan el día
    que alguien filtre uno de los dos.
    """

    por_raiz: dict[str, Emision] = field(default_factory=dict)

    @property
    def emisiones(self) -> list[Emision]:
        """Las emisiones ordenadas por clave, que es como se paginan."""
        return [self.por_raiz[raiz] for raiz in sorted(self.por_raiz)]

    def colapsado(self) -> list[EspecieUniverso]:
        """La vista del armador: una fila por emisión, ordenada por ticker.

        No siempre son tantas filas como emisiones: un grupo que no pasó el chequeo de duración
        aporta todas sus especies, porque no es una emisión sino varias.
        """
        filas = [fila for emision in self.emisiones for fila in emision.filas_colapsadas()]
        return sorted(filas, key=lambda e: e.ticker)

    def vivo(self) -> list[EspecieUniverso]:
        """La vista del optimizador: todas las especies, cada una entera y con su clave de emisión.

        Nada se filtra acá. Deduplicar no descarta, y el optimizador necesita ver las tres especies
        de MR46 para poder proponer rotar de una a otra.
        """
        return sorted(
            (e for emision in self.emisiones for e in emision.especies), key=lambda e: e.ticker
        )

    def emision_de(self, ticker: str) -> Emision | None:
        """La emisión a la que pertenece un ticker, esté o no en el universo.

        Se resuelve por `raiz_emision` y no por búsqueda directa a propósito: el armador pregunta
        por lo que el asesor quiere agregar, y eso puede ser una especie que hoy no cotiza. Lo que
        se contesta es a qué emisión pertenecería.
        """
        return self.por_raiz.get(raiz_emision(ticker))

    def hermanas(self, ticker: str) -> list[EspecieUniverso]:
        """Las otras especies de la misma emisión. Es entre éstas que rota un swap de perfil."""
        emision = self.emision_de(ticker)
        return [] if emision is None else [e for e in emision.especies if e.ticker != ticker]

    def advertencia_de_duplicado(self, ticker: str, cartera: Iterable[str]) -> Alerta | None:
        """Si agregar `ticker` a una cartera que ya tiene alguna hermana suma diversificación.

        Es lo que el armador (F-018) necesita para avisar, y por eso es servicio y no interfaz: la
        decisión de qué es la misma emisión se toma acá, con el mismo criterio que colapsa las
        filas. Si estuviera en la pantalla, la pantalla tendría que volver a cortar tickers.

        **Sobre un grupo que no se colapsó no se advierte nada.** El chequeo de duración ya dijo que
        esas especies son emisiones distintas; avisar igual sería llamar duplicado a algo que sí
        diversifica, que es tan falso como el error que la feature ataca.
        """
        emision = self.emision_de(ticker)
        if emision is None or not emision.colapsada:
            return None
        ya_en_cartera = sorted(
            {t for t in cartera if t != ticker and raiz_emision(t) == emision.raiz}
        )
        if not ya_en_cartera:
            return None
        return _alerta_misma_emision(ticker, emision.raiz, ya_en_cartera)

    @property
    def alertas(self) -> list[Alerta]:
        """Qué hay que saber de cómo quedó armado este universo."""
        alertas: list[Alerta] = []
        colapsadas = sum(e.colapsadas for e in self.por_raiz.values())
        if colapsadas:
            alertas.append(
                _alerta_especies_colapsadas(colapsadas, len(self._emisiones_colapsadas()))
            )
        sin_colapsar = self._no_colapsadas()
        if sin_colapsar:
            alertas.append(_alerta_emisiones_no_colapsadas(sin_colapsar))
        sin_rendimiento = self._perdieron_el_rendimiento()
        if sin_rendimiento:
            alertas.append(_alerta_rendimiento_perdido_al_colapsar(sin_rendimiento))
        return alertas

    def resumen(self) -> dict[str, object]:
        """Los conteos que dicen si la deduplicación hizo algo y si hizo lo que tenía que hacer.

        `filas_colapsadas` y `emisiones` no son el mismo número cuando algún grupo no pasó el
        chequeo de duración, y esa diferencia es justamente lo que hay que poder ver.
        """
        sin_colapsar = self._no_colapsadas()
        sin_rendimiento = self._perdieron_el_rendimiento()
        return {
            "especies": sum(len(e.especies) for e in self.por_raiz.values()),
            "emisiones": len(self.por_raiz),
            "filas_colapsadas": sum(len(e.filas_colapsadas()) for e in self.por_raiz.values()),
            "especies_colapsadas": sum(e.colapsadas for e in self.por_raiz.values()),
            "emisiones_multiespecie": sum(1 for e in self.por_raiz.values() if len(e.especies) > 1),
            "no_colapsadas_por_duracion": {
                "cantidad": len(sin_colapsar),
                "muestra": [e.raiz for e in sin_colapsar[:MUESTRA_ALERTA]],
            },
            "rendimiento_perdido_al_colapsar": {
                "cantidad": len(sin_rendimiento),
                "muestra": [e.raiz for e in sin_rendimiento[:MUESTRA_ALERTA]],
            },
            "tolerancia_duracion": TOLERANCIA_DURACION,
            "desempate_por_volumen": self._desempata_por_volumen(),
        }

    def _desempata_por_volumen(self) -> bool:
        """Si el volumen normalizado de F-012 llegó a este universo o si sigue decidiendo el ticker.

        Es un hecho de la corrida y no una constante: el criterio está enchufado siempre, pero en un
        día sin tipo de cambio del día `volumen_usd` viene vacío en todas las especies y el orden lo
        termina fijando el alfabeto. Quien lee el resumen tiene que poder distinguir los dos casos.
        """
        return any(
            especie.volumen_usd is not None
            for emision in self.por_raiz.values()
            for especie in emision.especies
        )

    def como_dict(self) -> dict[str, object]:
        """El resumen más las alertas. Las dos vistas no viajan acá: son colecciones propias."""
        return {"resumen": self.resumen(), "alertas": [a.como_dict() for a in self.alertas]}

    def _emisiones_colapsadas(self) -> list[Emision]:
        return [e for e in self.emisiones if e.colapsadas]

    def _no_colapsadas(self) -> list[Emision]:
        return [e for e in self.emisiones if not e.colapsada]

    def _perdieron_el_rendimiento(self) -> list[Emision]:
        return [e for e in self.emisiones if e.perdio_el_rendimiento_al_colapsar]


def deduplicar(
    especies: Sequence[EspecieUniverso], descartados: Collection[str] = frozenset()
) -> UniversoDeduplicado:
    """Agrupa las especies por emisión y elige a la que representa a cada una.

    `descartados` son los tickers que la sanidad de F-010 dejó afuera. Entran como parámetro y no
    se recalculan acá porque son un veredicto de otra capa, y porque así se ve en la firma que esto
    consume el universo saneado: una especie descartada no puede ser el representante de su emisión.
    """
    por_raiz: dict[str, list[EspecieUniverso]] = defaultdict(list)
    for especie in especies:
        por_raiz[especie.raiz].append(especie)

    return UniversoDeduplicado(
        por_raiz={
            raiz: _armar_emision(raiz, grupo, descartados) for raiz, grupo in por_raiz.items()
        }
    )


def _armar_emision(
    raiz: str, grupo: Sequence[EspecieUniverso], descartados: Collection[str]
) -> Emision:
    """Decide si el grupo es una emisión y, si lo es, cuál de sus especies la representa."""
    especies = sorted(grupo, key=lambda e: e.ticker)
    if len(especies) == 1:
        return Emision(raiz=raiz, especies=especies, representante=especies[0])

    dispersion = _dispersion_duracion(especies)
    if dispersion is not None and dispersion > TOLERANCIA_DURACION:
        return Emision(raiz=raiz, especies=especies, dispersion_duracion=dispersion)

    return Emision(
        raiz=raiz,
        especies=especies,
        representante=_representante(especies, descartados),
        dispersion_duracion=dispersion,
    )


def _dispersion_duracion(especies: Sequence[EspecieUniverso]) -> float | None:
    """Cuánto se separan las duraciones del grupo, en fracción de la mayor.

    Con menos de dos duraciones publicadas devuelve `None`: no saber no es evidencia de que sean
    emisiones distintas, y tratarlo como tal partiría en dos las emisiones cuyas especies todavía no
    tienen `duration` cargada — que hoy son casi todas.
    """
    duraciones = [e.duracion for e in especies if e.duracion is not None]
    if len(duraciones) < 2:
        return None
    mayor, menor = max(duraciones), min(duraciones)
    return (mayor - menor) / max(mayor, PISO_DIVISION)


def _representante(
    especies: Sequence[EspecieUniverso], descartados: Collection[str]
) -> EspecieUniverso:
    """La especie que mejor describe a su emisión: sana, completa, líquida y al final alfabética."""
    return min(especies, key=lambda e: _prioridad(e, descartados))


def _prioridad(
    especie: EspecieUniverso, descartados: Collection[str]
) -> tuple[bool, int, float, str]:
    """La clave de orden del representante: gana el menor.

    Los tres primeros elementos van negados porque `min` ordena ascendente y lo que se quiere es lo
    mejor: primero lo sano (`False` antes que `True`), después lo más completo, después lo más
    líquido. El ticker cierra sin negar, porque ahí lo que se pide es orden alfabético.

    **El volumen entra en dólares y sin volumen no hay crédito.** Un `volumen_usd` en `None`
    significa que no se pudo normalizar —no hubo tipo de cambio del día, o no se supo en qué moneda
    estaba el número— y cuenta como cero, no como "mucho": una liquidez que no se conoce no puede
    ganarle a una que sí. Entre las que empatan en cero decide el ticker, que es el mismo desempate
    arbitrario y estable de antes.
    """
    return (
        especie.ticker in descartados,
        -_completitud(especie),
        -(especie.volumen_usd or 0.0),
        especie.ticker,
    )


def _completitud(especie: EspecieUniverso) -> int:
    """Cuántos de los atributos de la emisión tiene cargados esta especie."""
    return sum(getattr(especie, campo) is not None for campo in CAMPOS_COMPLETITUD)


def _alerta_especies_colapsadas(especies: int, emisiones: int) -> Alerta:
    """Cuántas posiciones dejó de duplicar el armador. Es información, no un problema."""
    return Alerta(
        codigo=CODIGO_ESPECIES_COLAPSADAS,
        mensaje=(
            f"{especies} especies de liquidación se colapsaron en {emisiones} emisiones (el mismo "
            "bono cotizando en pesos, MEP y cable): en la vista del armador cada emisión cuenta "
            "una vez, y las especies siguen enteras en la vista viva."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={"especies": especies, "emisiones": emisiones},
    )


def _alerta_emisiones_no_colapsadas(emisiones: Sequence[Emision]) -> Alerta:
    """Grupos que comparten raíz pero no duración: casi seguro son bonos distintos.

    Se avisa con nombre y apellido en vez de resolverlo solo. Puede ser que de verdad sean dos
    emisiones —y entonces está bien que no se colapsen— o que una de las dos tenga la duración mal
    cargada; distinguirlo requiere mirar el bono, y adivinar sería inventar.
    """
    raices = [e.raiz for e in emisiones]
    return Alerta(
        codigo=CODIGO_EMISION_NO_COLAPSADA,
        mensaje=(
            f"{len(emisiones)} grupos de especies comparten raíz pero declaran duraciones que "
            f"difieren más de un {TOLERANCIA_DURACION:.0%} ({', '.join(raices[:MUESTRA_ALERTA])}): "
            "no se colapsan, porque no son la misma emisión."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar si son emisiones distintas que comparten raíz o si alguna especie tiene la "
            "duración mal cargada."
        ),
        detalle={
            "cantidad": len(emisiones),
            "emisiones": raices,
            "dispersiones": {e.raiz: e.dispersion_duracion for e in emisiones},
            "tolerancia": TOLERANCIA_DURACION,
        },
    )


def _alerta_rendimiento_perdido_al_colapsar(emisiones: Sequence[Emision]) -> Alerta:
    """Emisiones que tienen rendimiento publicado pero cuya fila colapsada no lo trae.

    Es la consecuencia medible del desempate, y por eso se cuenta en cada corrida en vez de
    descubrirse cuando el armador muestre una lista corta. IAMC publica la TIR sólo en el ticker que
    su informe nombra, así que las hermanas empatan en completitud y elige la liquidez; si la más
    operada no es la que trae el número, la emisión entera queda sin rendimiento para el armador
    aunque el dato exista en la vista viva.

    **No se corrige solo.** Preferir a la especie que publica rendimiento sería un quinto criterio
    que el motor no tiene, y agregarlo por cuenta propia sería cambiar el criterio de armado sin que
    nadie lo haya decidido. Lo que corresponde es alertarlo con el número exacto.
    """
    raices = [e.raiz for e in emisiones]
    return Alerta(
        codigo=CODIGO_RENDIMIENTO_PERDIDO_AL_COLAPSAR,
        mensaje=(
            f"{len(emisiones)} emisiones tienen rendimiento publicado en alguna de sus especies "
            f"pero no en la que las representa ({', '.join(raices[:MUESTRA_ALERTA])}): en la vista "
            "colapsada quedan sin rendimiento y el armador no las va a proponer. El dato sigue "
            "entero en la vista viva."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "El desempate por volumen normalizado ya está aplicado: decidir si hace falta además "
            "un criterio que prefiera a la especie que publica rendimiento."
        ),
        detalle={"cantidad": len(emisiones), "emisiones": raices},
    )


def _alerta_misma_emision(ticker: str, raiz: str, ya_en_cartera: Sequence[str]) -> Alerta:
    """Agregar otra especie del mismo bono no diversifica: cambia la liquidación, no el riesgo."""
    return Alerta(
        codigo=CODIGO_MISMA_EMISION,
        mensaje=(
            f"{ticker} es la misma emisión que {', '.join(ya_en_cartera)}, que la cartera ya tiene "
            f"({raiz}): agregarlo no suma diversificación, porque cambia la moneda de liquidación "
            "y no el crédito, el plazo ni la moneda de pago."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            f"Si lo que se busca es diversificar, elegir otra emisión; si lo que se busca es rotar "
            f"de especie, vender {ya_en_cartera[0]} en vez de sumar {ticker}."
        ),
        detalle={"ticker": ticker, "emision": raiz, "ya_en_cartera": list(ya_en_cartera)},
    )
