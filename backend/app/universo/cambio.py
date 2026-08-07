"""Tipo de cambio implícito, normalización de volumen y contraste — F-012.

Portado de `tools/segmentos.py:178-232` (`tipo_cambio_implicito`) y `:331-352` (el bloque de
liquidez comparable). El backend no importa de `tools/`: la lógica se copia con su razón de ser, y
las dos tienen que seguir coincidiendo.

## El tipo de cambio sale del propio universo

La misma emisión cotiza en pesos (especie O, o el ticker pelado) y en dólares (especies D y C), y el
cociente entre esos dos precios **es** el tipo de cambio al que opera el mercado. No hace falta
ninguna fuente externa: el dato ya está adentro. Es la regla 3 del dominio, y no es una preferencia
de implementación — un tipo de cambio traído de afuera valuaría este universo con un número que no
salió de él.

Se toma la **mediana** sobre todas las emisiones que cotizan en las dos puntas, así un precio
desactualizado no mueve el resultado, y se exige un **mínimo de 20 pares**: con menos, la mediana la
puede correr un solo precio raro. Por debajo de ese mínimo no se normaliza nada y se declara.

**La especie D (MEP) es la referencia y la C (Cable) sólo entra si no hay D.** Los separa el canje,
y eso no es teoría: sobre el universo de hoy la mediana de los cocientes contra la D da 1521,53 y
contra la C da 1576,21 — un 3,6 % de diferencia. Mezclarlas correría la mediana por un spread
estructural conocido y no por lo que el mercado hizo. Cuando una emisión entra por la C, el hecho
queda registrado con nombre y apellido.

## En qué moneda cotiza cada especie: se lee, no se deduce

El volumen (`effectiveVolume`) es **monto operado en la moneda de cotización de cada especie**,
igual que el precio. La especie en pesos de un bono muestra ~1.500 veces más volumen que su hermana
en dólares por el tipo de cambio y no por operarse más; con los números crudos, un filtro de
liquidez descarta sistemáticamente las especies en dólares.

Para saber en qué moneda está ese número se usa `instrumentos.moneda_cotizacion` —el
`denominationCcy` que declara BYMA, sin traducir— y **no el sufijo del ticker**, que es lo que hace
el motor. La diferencia no es cosmética: sobre el universo de hoy hay seis especies con sufijo D
declaradas en ARS (BA37D, BB37D, BC37D, SA24D y dos sin precio) y sus precios —121.100, 123.800,
117.010— son precios en pesos sin ninguna duda. La regla del sufijo las habría tomado por dólares y
habría multiplicado su liquidez por 1.500.

`EXT` cuenta como dólar: es la denominación con la que BYMA publica la especie C, y el cociente
contra su hermana en pesos da 1576 —un dólar cable—, no 1.

**Cuando la fuente no declara la moneda se cae a la regla del sufijo**, que es la del motor, y se
cuenta cuántas especies quedaron con la moneda asumida en vez de leída. Es el único camino por el
que este módulo supone algo, y por eso el número se reporta en vez de esconderse. Pasa sobre el
consolidado histórico, que no tiene la columna; sobre la base de hoy la cobertura de
`moneda_cotizacion` es del 100 %.

## El índice de BYMA contrasta, no alimenta

El `index-price` de BYMA es un **control**, nunca la fuente: si el implícito difiere del índice
publicado más allá de la tolerancia sale alerta, y el que se sigue usando es el implícito.

Dos hallazgos sobre esa fuente, medidos contra el endpoint vivo, que contradicen lo que la ficha del
plan da por sentado:

1. **`index-price` no publica ningún "Índice Dólar".** Son 16 filas y ninguna lo es. Lo que sí
   publica es el mismo índice en las dos monedas: `M` (S&P MERVAL, en pesos) y `SPMERVDT` (S&P
   MERVAL USD). Su cociente es el tipo de cambio que BYMA usa para valuar su propio índice, y ése
   es el número contra el que se contrasta.
2. **Coincide.** Hoy el cociente publicado da 1519,47 contra 1521,53 del implícito: 0,14 % de
   diferencia.

La tolerancia se fija por encima del canje MEP/cable a propósito. Si algún día BYMA calculara su
índice en dólares al cable en vez de al MEP, la diferencia saltaría a ~3,6 % por un spread
estructural conocido y no por un error, y una alerta que grita por eso todos los días es una alerta
que nadie mira.

**Que el contraste no esté disponible no rompe el cálculo del implícito.** Son dos cosas distintas y
la que manda es la primera: el implícito se deriva del universo y no necesita a BYMA para existir.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from statistics import median, quantiles

from app.ingesta.alertas import Alerta, Severidad
from app.universo.segmentacion import EspecieUniverso, a_numero

# Mínimo de pares para confiar en el implícito. Con menos, la mediana la puede mover un solo precio
# raro. Portado del motor (`MIN_PARES_FX`).
MIN_PARES_FX = 20

# Un cociente fuera de este rango no es un tipo de cambio: es una de las dos puntas con el precio
# mal cargado. Portado del motor, que lo escribe en línea.
FX_MINIMO = 500.0
FX_MAXIMO = 5000.0

# Por encima de esta dispersión intercuartil hay precios desactualizados en alguna punta y las
# comparaciones de liquidez pierden precisión. El implícito se usa igual: es el mejor que hay.
DISPERSION_ACEPTABLE = 0.05

# Cuánto puede separarse el implícito del cociente que publica BYMA antes de que salga alerta. Está
# por encima del canje MEP/cable (~3,6 % medido) para que un día en que BYMA valúe su índice al
# cable no dispare una alerta por un spread estructural conocido.
TOLERANCIA_CONTRASTE = 0.05

# Los dos símbolos de `index-price` que son el mismo índice en las dos monedas. Su cociente es el
# tipo de cambio con el que BYMA valúa su propio índice. No hay un "Índice Dólar" en esa respuesta.
INDICE_EN_PESOS = "M"
INDICE_EN_DOLARES = "SPMERVDT"

# Las especies de liquidación. La D es MEP y la C es Cable; los separa el canje.
SUFIJO_MEP = "D"
SUFIJO_CABLE = "C"

# Lo que `denominationCcy` puede decir. `EXT` es la denominación de la especie cable y cotiza en
# dólares; `ARS` es la única que se divide por el tipo de cambio.
MONEDAS_EN_DOLARES = frozenset({"USD", "EXT"})
MONEDA_EN_PESOS = "ARS"

CODIGO_FX_SIN_PARES = "tipo_de_cambio_sin_pares"
CODIGO_FX_DISPERSO = "tipo_de_cambio_disperso"
CODIGO_FX_POR_CABLE = "tipo_de_cambio_por_cable"
CODIGO_FX_PRECIO_IMPOSIBLE = "tipo_de_cambio_precio_imposible"
CODIGO_FX_CONTRASTE = "tipo_de_cambio_contraste"
CODIGO_FX_SIN_CONTRASTE = "tipo_de_cambio_sin_contraste"
CODIGO_MONEDA_ASUMIDA = "moneda_de_cotizacion_asumida"

# Cuántos tickers se nombran en el cuerpo de una alerta. La lista entera va en el detalle.
MUESTRA_ALERTA = 6


@dataclass(frozen=True, slots=True)
class Contraste:
    """El implícito contra el cociente que BYMA publica entre sus dos índices.

    `publicado` no es un tipo de cambio que BYMA declare como tal: es el que se deduce de valuar el
    mismo índice en pesos y en dólares. Por eso contrasta y no alimenta — es tan derivado como el
    nuestro, sólo que de otro universo.
    """

    publicado: float
    implicito: float
    indice_pesos: float
    indice_dolares: float

    @property
    def diferencia(self) -> float:
        """Cuánto se separan, en fracción del publicado. Negativo es implícito más bajo."""
        return (self.implicito - self.publicado) / self.publicado

    @property
    def coincide(self) -> bool:
        return abs(self.diferencia) <= TOLERANCIA_CONTRASTE

    def como_dict(self) -> dict[str, object]:
        return {
            "publicado": self.publicado,
            "implicito": self.implicito,
            "diferencia": self.diferencia,
            "tolerancia": TOLERANCIA_CONTRASTE,
            "coincide": self.coincide,
            "indices": {
                INDICE_EN_PESOS: self.indice_pesos,
                INDICE_EN_DOLARES: self.indice_dolares,
            },
        }


@dataclass(frozen=True, slots=True)
class TipoDeCambio:
    """El implícito del día con todo lo que hace falta para saber si se le puede creer.

    `valor` es `None` cuando no hubo pares suficientes. En ese caso **no se normaliza nada**: el
    volumen crudo queda como está y las comparaciones de liquidez entre monedas no son confiables,
    que es exactamente lo que la alerta declara. Rellenarlo con cualquier otro número sería inventar
    el dato que la feature existe para derivar.
    """

    valor: float | None = None
    pares: int = 0
    dispersion: float | None = None
    """Rango intercuartil sobre la mediana. `None` con menos de dos pares: no hay qué dispersar."""

    por_cable: list[str] = field(default_factory=list)
    """Emisiones que entraron por la especie C porque no tienen D. Se registran porque MEP y Cable
    son tipos de cambio distintos y el promedio de la muestra se corre un poco por cada una."""

    precio_imposible: list[str] = field(default_factory=list)
    """Emisiones cuyo cociente cayó fuera del rango: una de las dos puntas tiene el precio mal
    cargado. Se nombran en vez de descartarse en silencio."""

    moneda_asumida: list[str] = field(default_factory=list)
    """Especies cuya moneda de cotización se dedujo del sufijo porque la fuente no la declaró."""

    contraste: Contraste | None = None
    """`None` cuando el índice de BYMA no estuvo disponible. No invalida el implícito."""

    @property
    def disponible(self) -> bool:
        return self.valor is not None

    @property
    def alertas(self) -> list[Alerta]:
        """Todo lo que hay que saber antes de comparar liquidez con estos números.

        **Sin tipo de cambio no se alerta sobre el contraste.** No haber podido contrastar sólo es
        noticia cuando hay algo que contrastar; decirlo sobre un universo del que ni siquiera salió
        un implícito sería un segundo aviso del mismo hecho.
        """
        alertas: list[Alerta] = []
        if not self.disponible:
            return [_alerta_sin_pares(self.pares), *self._alertas_de_la_muestra()]
        if self.dispersion is not None and self.dispersion > DISPERSION_ACEPTABLE:
            alertas.append(_alerta_disperso(self.dispersion, self.pares))
        alertas.extend(self._alertas_de_la_muestra())
        if self.contraste is None:
            alertas.append(_alerta_sin_contraste())
        elif not self.contraste.coincide:
            alertas.append(_alerta_contraste(self.contraste))
        return alertas

    def _alertas_de_la_muestra(self) -> list[Alerta]:
        """Lo que se declara sobre cómo se armó la muestra, haya salido implícito o no."""
        alertas: list[Alerta] = []
        if self.por_cable:
            alertas.append(_alerta_por_cable(self.por_cable))
        if self.precio_imposible:
            alertas.append(_alerta_precio_imposible(self.precio_imposible))
        if self.moneda_asumida:
            alertas.append(_alerta_moneda_asumida(self.moneda_asumida))
        return alertas

    def a_dolares(self, monto: float | None, en_dolares: bool) -> float | None:
        """Un monto de la moneda de cotización de su especie a dólares.

        Sin tipo de cambio devuelve `None` y no el monto crudo: un número que no se sabe en qué
        unidad está no es comparable con otro, y devolverlo igual sería ofrecer una comparación que
        no se puede hacer. Es la diferencia con el motor, que ahí deja el crudo — y por eso su
        desempate por volumen, en un día sin pares, ordenaría por una magnitud mezclada.
        """
        if monto is None:
            return None
        if en_dolares:
            return monto
        return None if self.valor is None else monto / self.valor

    def como_dict(self) -> dict[str, object]:
        return {
            "valor": self.valor,
            "disponible": self.disponible,
            "pares": self.pares,
            "minimo_de_pares": MIN_PARES_FX,
            "dispersion": self.dispersion,
            "dispersion_aceptable": DISPERSION_ACEPTABLE,
            "por_cable": _conteo_y_muestra(self.por_cable),
            "precio_imposible": _conteo_y_muestra(self.precio_imposible),
            "moneda_asumida": _conteo_y_muestra(self.moneda_asumida),
            "contraste": self.contraste.como_dict() if self.contraste else None,
        }


def _conteo_y_muestra(nombres: Sequence[str]) -> dict[str, object]:
    """Cuántos son y unos cuantos con nombre y apellido.

    Es la forma que ya usan `emisiones.resumen()` y `servicio.resumen()` para lo mismo: el número
    entero es lo que se mira, y la muestra es para poder ir a buscar un caso sin pedir otra cosa.
    La lista completa viaja en el detalle de la alerta, no acá.
    """
    return {"cantidad": len(nombres), "muestra": list(nombres[:MUESTRA_ALERTA])}


def cotiza_en_dolares(especie: EspecieUniverso) -> bool:
    """Si el precio y el volumen de esta especie ya están en dólares.

    Manda lo que la fuente declara (`denominationCcy`). Sólo cuando no declara nada decide el sufijo
    de liquidación, que es la regla del motor: la D y la C son las especies en dólares. Esa segunda
    rama es una suposición y se cuenta aparte (`TipoDeCambio.moneda_asumida`) justamente por serlo.
    """
    if especie.moneda_cotizacion is not None:
        return especie.moneda_cotizacion.upper() in MONEDAS_EN_DOLARES
    return especie.sufijo_liquidacion in (SUFIJO_MEP, SUFIJO_CABLE)


def derivar_tipo_de_cambio(
    especies: Sequence[EspecieUniverso],
    indices: Sequence[Mapping[str, object]] | None = None,
) -> TipoDeCambio:
    """El tipo de cambio del día, derivado de las emisiones que cotizan en las dos puntas.

    `indices` son las filas de `index-price` de BYMA, y son opcionales: sirven para contrastar y no
    para calcular. Sin ellas el implícito sale igual, con una alerta que dice que no se lo pudo
    contrastar contra nada.
    """
    pares, por_cable, imposibles = _cocientes(especies)
    asumidas = sorted(e.ticker for e in especies if e.moneda_cotizacion is None)

    if len(pares) < MIN_PARES_FX:
        return TipoDeCambio(
            pares=len(pares),
            por_cable=por_cable,
            precio_imposible=imposibles,
            moneda_asumida=asumidas,
        )

    cocientes = sorted(pares.values())
    valor = median(cocientes)
    dispersion = _dispersion(cocientes, valor)
    return TipoDeCambio(
        valor=valor,
        pares=len(cocientes),
        dispersion=dispersion,
        por_cable=por_cable,
        precio_imposible=imposibles,
        moneda_asumida=asumidas,
        contraste=contrastar(valor, indices or []),
    )


def _cocientes(
    especies: Sequence[EspecieUniverso],
) -> tuple[dict[str, float], list[str], list[str]]:
    """Un cociente por emisión que cotice a la vez en pesos y en dólares.

    Se exige **exactamente una** especie de cada lado, igual que el motor: si una emisión tuviera
    dos tickers en pesos habría que elegir cuál usar, y elegir sería inventar. Se saltea entera.
    """
    por_raiz: dict[str, dict[str, list[EspecieUniverso]]] = {}
    for especie in especies:
        if especie.precio is None or especie.precio <= 0:
            continue
        sufijo = especie.sufijo_liquidacion
        lado = sufijo if sufijo in (SUFIJO_MEP, SUFIJO_CABLE) else MONEDA_EN_PESOS
        por_raiz.setdefault(especie.raiz, {}).setdefault(lado, []).append(especie)

    cocientes: dict[str, float] = {}
    por_cable: list[str] = []
    imposibles: list[str] = []

    for raiz in sorted(por_raiz):
        lados = por_raiz[raiz]
        en_pesos = lados.get(MONEDA_EN_PESOS, [])
        # La D primero y la C sólo si no hay D: los separa el canje y mezclarlas correría la mediana
        # por un spread estructural en vez de por lo que hizo el mercado.
        en_dolares = lados.get(SUFIJO_MEP, [])
        entro_por_cable = not en_dolares
        if entro_por_cable:
            en_dolares = lados.get(SUFIJO_CABLE, [])
        if len(en_pesos) != 1 or len(en_dolares) != 1:
            continue

        cociente = en_pesos[0].precio / en_dolares[0].precio  # type: ignore[operator]
        if not FX_MINIMO < cociente < FX_MAXIMO:
            imposibles.append(raiz)
            continue

        cocientes[raiz] = cociente
        if entro_por_cable:
            por_cable.append(raiz)

    return cocientes, por_cable, imposibles


def _dispersion(cocientes: Sequence[float], mediana: float) -> float | None:
    """Rango intercuartil sobre la mediana: cuánto se separan las puntas entre sí."""
    if len(cocientes) < 2:
        return None
    q1, _, q3 = quantiles(cocientes, n=4)
    return (q3 - q1) / mediana


def contrastar(implicito: float, indices: Sequence[Mapping[str, object]]) -> Contraste | None:
    """El implícito contra el cociente entre los dos índices que BYMA publica del mismo panel.

    Devuelve `None` —y no un contraste que falla— cuando los dos símbolos no están o no traen valor
    utilizable: no haber podido contrastar no es lo mismo que haber contrastado y no coincidir, y
    presentarlos igual haría que alguien desconfíe del implícito por una fuente que no respondió.
    """
    valores = {
        str(fila.get("indice")): fila.get("valor")
        for fila in indices
        if fila.get("indice") is not None
    }
    # Se reusa `a_numero` de `segmentacion` en vez de repetir la validación acá: además de bool y de
    # lo que no es número, filtra `NaN`, que es el caso que una copia a mano deja pasar. `nan` es un
    # `float` legítimo para `isinstance`, no es `bool`, y `nan <= 0` da `False`, así que se colaba
    # entero y producía un contraste de `nan / nan` que ninguna alerta detectaba.
    en_pesos = a_numero(valores.get(INDICE_EN_PESOS))
    en_dolares = a_numero(valores.get(INDICE_EN_DOLARES))
    if en_pesos is None or en_dolares is None or en_dolares <= 0:
        return None
    return Contraste(
        publicado=en_pesos / en_dolares,
        implicito=implicito,
        indice_pesos=en_pesos,
        indice_dolares=en_dolares,
    )


def normalizar_volumen(
    especies: Sequence[EspecieUniverso], cambio: TipoDeCambio
) -> list[EspecieUniverso]:
    """Devuelve las mismas especies con `volumen_usd` cargado, para poder comparar liquidez.

    Se lleva todo a **dólares y no a nominales**: liquidez es cuánta plata se puede mover sin correr
    el precio. Medirla en láminas sería otra distorsión — una lámina de DICP vale 33 veces una de
    TX31 y las dos cotizan en pesos.

    Sin tipo de cambio, las especies en pesos quedan con `volumen_usd` en `None` y no con su volumen
    crudo: mezclar pesos y dólares en la misma columna es el error que esta feature existe para
    evitar, y hacerlo cuando falta el dato lo haría igual de mal, sólo que en silencio.
    """
    return [
        replace(
            especie,
            volumen_usd=cambio.a_dolares(especie.volumen, cotiza_en_dolares(especie)),
        )
        for especie in especies
    ]


def _alerta_sin_pares(pares: int) -> Alerta:
    """Sin pares suficientes no hay tipo de cambio, y sin tipo de cambio no hay comparación."""
    return Alerta(
        codigo=CODIGO_FX_SIN_PARES,
        mensaje=(
            f"Sólo {pares} emisiones cotizan a la vez en pesos y en dólares: no alcanza para "
            f"derivar el tipo de cambio del día (hacen falta {MIN_PARES_FX}). El volumen queda sin "
            "normalizar y las comparaciones de liquidez entre monedas no están disponibles."
        ),
        severidad=Severidad.ERROR,
        accion_requerida=(
            "Verificar que la ingesta de precios de BYMA haya traído las especies en dólares: sin "
            "ellas no hay de dónde derivar el tipo de cambio."
        ),
        detalle={"pares": pares, "minimo": MIN_PARES_FX},
    )


def _alerta_disperso(dispersion: float, pares: int) -> Alerta:
    """El implícito se usa igual: es el mejor que hay. Lo que se declara es cuánto confiar en él."""
    return Alerta(
        codigo=CODIGO_FX_DISPERSO,
        mensaje=(
            f"El tipo de cambio implícito tiene dispersión alta ({dispersion:.1%} entre {pares} "
            "emisiones): hay precios desactualizados en alguna punta. Las comparaciones de "
            "liquidez pierden precisión."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Revisar la hora de captura de los precios: una punta de una rueda anterior separa los "
            "cocientes sin que nada más lo delate."
        ),
        detalle={
            "dispersion": dispersion,
            "aceptable": DISPERSION_ACEPTABLE,
            "pares": pares,
        },
    )


def _alerta_por_cable(emisiones: Sequence[str]) -> Alerta:
    """Emisiones que entraron a la muestra por la C. Es información, no un problema."""
    return Alerta(
        codigo=CODIGO_FX_POR_CABLE,
        mensaje=(
            f"{len(emisiones)} emisiones entraron al tipo de cambio por su especie cable porque no "
            f"tienen MEP ({', '.join(emisiones[:MUESTRA_ALERTA])}): MEP y cable son tipos de "
            "cambio distintos y los separa el canje."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={"cantidad": len(emisiones), "emisiones": list(emisiones)},
    )


def _alerta_precio_imposible(emisiones: Sequence[str]) -> Alerta:
    """Un cociente fuera de rango no es tipo de cambio: es una punta con el precio mal cargado."""
    return Alerta(
        codigo=CODIGO_FX_PRECIO_IMPOSIBLE,
        mensaje=(
            f"{len(emisiones)} emisiones dan un cociente entre su precio en pesos y su precio en "
            f"dólares fuera del rango posible ({', '.join(emisiones[:MUESTRA_ALERTA])}): no entran "
            "al tipo de cambio, porque una de las dos puntas tiene el precio mal cargado."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar en la fuente el precio de las dos especies: una de las dos está en otra "
            "escala o es de otra rueda."
        ),
        detalle={
            "cantidad": len(emisiones),
            "emisiones": list(emisiones),
            "rango": [FX_MINIMO, FX_MAXIMO],
        },
    )


def _alerta_moneda_asumida(especies: Sequence[str]) -> Alerta:
    """Lo único que este módulo supone, dicho en voz alta y con el número exacto."""
    return Alerta(
        codigo=CODIGO_MONEDA_ASUMIDA,
        mensaje=(
            f"{len(especies)} especies no traen declarada su moneda de cotización "
            f"({', '.join(especies[:MUESTRA_ALERTA])}): se la dedujo del sufijo de liquidación "
            "para poder normalizar su volumen. Es la regla del motor y es una suposición, no un "
            "dato."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar que la ingesta de BYMA haya cargado `denominationCcy` para esas especies: "
            "declarada, la moneda no hace falta suponerla."
        ),
        detalle={"cantidad": len(especies), "especies": list(especies)},
    )


def _alerta_contraste(contraste: Contraste) -> Alerta:
    """El implícito se conserva como fuente. Lo que cambia es que ahora hay algo que averiguar."""
    return Alerta(
        codigo=CODIGO_FX_CONTRASTE,
        mensaje=(
            f"El tipo de cambio implícito ({contraste.implicito:,.2f}) difiere un "
            f"{contraste.diferencia:+.1%} del que se deduce de los índices que publica BYMA "
            f"({contraste.publicado:,.2f}). Se sigue usando el implícito, que es el que sale de "
            "este universo."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar si los precios de la corrida son de la misma rueda que el índice publicado, "
            "y si BYMA está valuando su índice en dólares al MEP o al cable."
        ),
        detalle=contraste.como_dict(),
    )


def _alerta_sin_contraste() -> Alerta:
    """No haber podido contrastar no es haber contrastado mal. El implícito no depende de esto."""
    return Alerta(
        codigo=CODIGO_FX_SIN_CONTRASTE,
        mensaje=(
            "No se pudo contrastar el tipo de cambio implícito contra los índices de BYMA: faltan "
            f"{INDICE_EN_PESOS} o {INDICE_EN_DOLARES} en index-price. El implícito se calcula "
            "igual y se usa igual: el contraste es un control, no la fuente."
        ),
        severidad=Severidad.INFO,
        accion_requerida=None,
        detalle={"indices": [INDICE_EN_PESOS, INDICE_EN_DOLARES]},
    )
