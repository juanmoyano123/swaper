"""La matemática de los cupones: de un cronograma en nominales a plata sobre el monto invertido.

Portado de `tools/cupones.py` (`raiz_ticker`, `valor_tecnico` y `flujos_por_peso`), que es lógica ya
verificada contra el universo real. El backend **no importa de `tools/`**: la matemática se copia
con su razón de ser, y `tests/test_calendario_paridad_motor.py` es lo que impide que las dos copias
diverjan sin que nadie se entere.

## El problema que resuelve

El cronograma trae, por ticker y fecha, cuánto paga el bono **cada 100 nominales y en su moneda de
emisión**. Para traducir eso a plata sobre un monto invertido hay que pasar por nominales, y ahí
aparece la trampa que la regla 3 del proyecto nombra: `lastPrice` viene en monedas mezcladas. La
misma emisión cotiza en pesos sin sufijo y en dólares con sufijo D o C —AE38 a 127.360 son pesos,
PNDCD a 43,77 son dólares— y dividir un monto por ese precio da cualquier cosa.

La salida es normalizar contra la **paridad**, que es adimensional:

    precio sucio (moneda de emisión, c/100 nominales) = paridad x valor técnico
    valor técnico = residual vivo + intereses corridos
    nominales = monto / (precio sucio / 100)

y entonces cada pago, como fracción del monto invertido, es:

    cobro / monto = pago / precio sucio

que es adimensional y por lo tanto independiente de la moneda de cotización. **No hay un tipo de
cambio acá y no lo va a haber**: no hace falta ninguno, que es justamente por qué esta forma es la
correcta.

## El cruce por raíz es un lookup y nunca genera un ticker

El cronograma indexa **una sola especie por emisión** —RUCEO, no RUCED ni RUCEC (ver
`docs/esquema-datos.md`)— mientras el universo trae las tres especies de liquidación. Buscar el
cronograma de RUCED bajo la raíz `RUCE` es la única forma de encontrarlo.

Lo que no se hace jamás es el camino inverso. **Si la raíz no encuentra cronograma, el instrumento
queda fuera del calendario y se lo nombra en una alerta**; no se le asigna el cronograma de un bono
parecido ni se deriva un ticker nuevo. Cortar strings para generar tickers ya produjo una vez 121
tickers inexistentes que hubo que revertir, y ésa es la regla 1 del proyecto.

La raíz se calcula con `raiz_emision`, la misma función con la que F-011 agrupa las especies de una
emisión — y no con una segunda copia. El motor usa `len(t) > 4` donde `raiz_emision` usa `len >= 4`,
así que difieren en los tickers de cuatro letras terminados en O, D o C. Medido sobre el dato real:
**cero casos**, ni entre los 816 tickers del cronograma ni entre los 937 de renta fija del universo
(los 153 que existen en el universo son CEDEARs, que salen antes de segmentar). Tener dos funciones
de raíz sería garantizar que una emisión se agrupe distinto según quién la mire.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from app.calendario.alertas import sin_cronograma, sin_paridad
from app.ingesta.alertas import Alerta
from app.ingesta.raiz import raiz_emision
from app.universo.segmentacion import EspecieUniverso, a_numero

# Residual de un bono que todavía no pagó ningún cupón, cada 100 nominales. No es un default
# arbitrario: un bono que no amortizó nada tiene sus 100 vivos.
RESIDUAL_ENTERO = 100.0


@dataclass(frozen=True, slots=True)
class Pago:
    """Un pago del cronograma, **por 100 de valor nominal y en la moneda de emisión del bono**.

    Nunca se suma un `Pago` con otro de distinta emisión: son montos en monedas distintas hasta que
    `flujos_por_peso` los divide por el precio sucio y los vuelve adimensionales.
    """

    fecha: date
    capital: float
    """Amortización. **Cobrar amortización no es renta**: es la devolución del capital prestado."""

    interes: float
    total: float
    """`cash_flow` de la fuente. Se lee y no se recalcula como capital + interés: si la fuente
    declara un total distinto de la suma, eso es un dato de la fuente y no un error a corregir."""

    residual: float | None
    """Cuánto capital queda vivo después de este pago. Es lo que hace que un bono amortizing no se
    valúe como si tuviera los 100 nominales enteros."""

    emision: date | None
    """`issue_date`. Sólo se usa para devengar los corridos de un bono que todavía no pagó nada."""


@dataclass(frozen=True, slots=True)
class FlujoPorPeso:
    """Un pago futuro expresado como **fracción del monto invertido** en ese instrumento.

    Multiplicando por el monto de la posición se obtiene la plata, en la moneda de ese monto. Los
    dos componentes viajan separados y nunca sumados: `pct_renta` es lo que rinde el bono y
    `pct_amortizacion` es plata que vuelve, y confundirlos hace parecer que un bono que amortiza
    fuerte paga más renta de la que paga.
    """

    ticker: str
    fecha: date
    pct_renta: float
    """`interest_amount / precio_sucio`. `pct_interes` en el motor."""

    pct_amortizacion: float
    """`capital / precio_sucio`. `pct_capital` en el motor."""

    pct_total: float


@dataclass(frozen=True, slots=True)
class Flujos:
    """Los flujos futuros del universo, más qué instrumentos quedaron afuera y por qué."""

    flujos: list[FlujoPorPeso] = field(default_factory=list)
    sin_cronograma: list[str] = field(default_factory=list)
    """Su raíz de emisión no tiene ningún pago en la fuente. No se les inventa uno."""

    sin_paridad: list[str] = field(default_factory=list)
    """**Todos** los que no declaran paridad utilizable, coticen o no. Sin paridad no hay precio
    sucio y el cupón no se puede pasar a plata."""

    sin_paridad_que_cotizan: list[str] = field(default_factory=list)
    """El subconjunto de `sin_paridad` que declara rendimiento o duración: los que alguna vez fueron
    candidatos de cartera. Es el que se alerta en la vista del universo, porque el otro son cientos
    de instrumentos que no cotizan y taparían los casos que importan. Criterio del motor.

    **Que este subconjunto esté vacío no significa que no falte nada.** Medido contra la base del 7
    de agosto de 2026: de 431 emisiones de la vista colapsada, 360 quedan afuera por falta de
    paridad y **ninguna** entra acá, porque su representante tampoco publica rendimiento. Ver el
    docstring de `servicio.py`."""

    vencidos: list[str] = field(default_factory=list)
    """No les queda ningún pago futuro, o su residual ya está en cero. No es un problema del dato:
    es un bono que terminó, y por eso se cuenta pero no se alerta en la vista del universo."""

    evaluados: int = 0

    @property
    def alertas(self) -> list[Alerta]:
        """Los dos faltantes que hay que nombrar en la vista del universo.

        Un bono vencido no es un faltante, y un instrumento que no cotiza tampoco: los dos se
        cuentan en el resumen. Quien pregunta por una **cartera** necesita otra cosa —ahí toda
        posición que no se pueda calcular tiene que nombrarse— y eso lo arma `servicio.py` con
        `motivo_de`, porque es quien sabe qué se le pidió calcular.
        """
        alertas: list[Alerta] = []
        if self.sin_cronograma:
            alertas.append(sin_cronograma(self.sin_cronograma))
        if self.sin_paridad_que_cotizan:
            alertas.append(sin_paridad(self.sin_paridad_que_cotizan))
        return alertas

    @property
    def tickers(self) -> set[str]:
        return {f.ticker for f in self.flujos}

    def motivo_de(self, ticker: str) -> str | None:
        """Por qué un instrumento no tiene flujos, o `None` si los tiene.

        Existe para que una posición de cartera que no se pudo calcular se pueda nombrar **con su
        motivo**: "no está" y "está pero no se puede valuar" se arreglan de formas distintas, y
        presentarlas como lo mismo manda a alguien a buscar donde no es.
        """
        if ticker in self.tickers:
            return None
        if ticker in set(self.sin_cronograma):
            return "sin cronograma de pagos en la fuente"
        if ticker in set(self.sin_paridad):
            return "sin paridad: no se puede pasar el cupón a plata"
        if ticker in set(self.vencidos):
            return "sin pagos futuros: la emisión ya venció"
        return None

    def resumen(self) -> dict[str, object]:
        return {
            "evaluados": self.evaluados,
            "con_flujos": len(self.tickers),
            "pagos": len(self.flujos),
            "sin_cronograma": len(self.sin_cronograma),
            "sin_paridad": len(self.sin_paridad),
            "sin_paridad_que_cotizan": len(self.sin_paridad_que_cotizan),
            "vencidos": len(self.vencidos),
        }


@dataclass(frozen=True, slots=True)
class Cronograma:
    """Los pagos de la fuente agrupados por raíz de emisión, más lo que no se pudo usar.

    Los descartes viajan con el índice y no se pierden en el camino: un pago que no entró es un mes
    que va a mostrar menos renta de la que el bono paga, y eso tiene que poder verse.
    """

    por_raiz: dict[str, list[Pago]] = field(default_factory=dict)
    sin_fecha: list[str] = field(default_factory=list)
    """Pagos sin fecha: no se pueden ubicar en ningún mes."""

    sin_monto: list[str] = field(default_factory=list)
    """Pagos con algún monto vacío. Medido sobre los 6.111 pagos del cronograma versionado: cero
    casos. Se cuentan igual, porque el día que la fuente empiece a dejar celdas vacías el síntoma
    sería una renta más chica sin ninguna explicación a la vista."""

    def pagos_de(self, raiz: str) -> list[Pago]:
        return self.por_raiz.get(raiz, [])

    def resumen(self) -> dict[str, object]:
        return {
            "emisiones": len(self.por_raiz),
            "pagos": sum(len(p) for p in self.por_raiz.values()),
            "descartados_sin_fecha": len(self.sin_fecha),
            "descartados_sin_monto": len(self.sin_monto),
        }


def indexar_cronograma(filas: Sequence[Mapping[str, object]]) -> Cronograma:
    """Agrupa los pagos por **raíz de emisión**, que es la clave con la que se los busca.

    Recibe mappings y no un tipo propio para que el mismo código sirva sobre los `Record` de asyncpg
    y sobre los diccionarios de un test, que es lo que permite probar toda la matemática sin
    Postgres. Es la misma decisión que tomó `segmentar`.

    **Un pago incompleto se descarta y se cuenta; no se completa con un cero.** Sin fecha no se lo
    puede ubicar en ningún mes, y sin monto no se lo puede repartir entre renta y amortización —
    ponerle cero afirmaría que ese día no se cobra nada, que es justamente lo que no se sabe.
    """
    por_raiz: dict[str, list[Pago]] = {}
    sin_fecha: list[str] = []
    sin_monto: list[str] = []

    for fila in filas:
        ticker = str(fila["ticker"])
        fecha = _a_fecha(fila.get("payment_date"))
        if fecha is None:
            sin_fecha.append(ticker)
            continue

        capital = a_numero(fila.get("capital"))
        interes = a_numero(fila.get("interest_amount"))
        total = a_numero(fila.get("cash_flow"))
        if capital is None or interes is None or total is None:
            sin_monto.append(f"{ticker} {fecha.isoformat()}")
            continue

        por_raiz.setdefault(raiz_emision(ticker), []).append(
            Pago(
                fecha=fecha,
                capital=capital,
                interes=interes,
                total=total,
                residual=a_numero(fila.get("residual_value")),
                emision=_a_fecha(fila.get("issue_date")),
            )
        )

    return Cronograma(
        por_raiz={raiz: sorted(pagos, key=lambda p: p.fecha) for raiz, pagos in por_raiz.items()},
        sin_fecha=sin_fecha,
        sin_monto=sin_monto,
    )


def valor_tecnico(pagos: Sequence[Pago], hoy: date) -> float | None:
    """Residual vivo + intereses corridos, cada 100 nominales. `None` si el bono no proyecta nada.

    Los corridos se devengan **linealmente** entre el último pago y el próximo. Es una convención y
    no la exactitud del bono —que depende de su base de cálculo de días, que la fuente no publica—
    pero es la misma que usa el motor y la que reproduce los nominales verificados de la mesa.

    Si el bono todavía no pagó ningún cupón se usa la fecha de emisión como inicio del
    devengamiento; si tampoco está, se asumen 0 corridos. Ese default **subestima el precio sucio,
    nunca lo infla**, y por lo tanto sobreestima levemente la fracción que representa cada cupón. Es
    el lado prudente para caer: el error es visible en el sentido de "este bono rinde menos de lo
    que dice la grilla", que es el que un asesor puede corregir mirando.
    """
    pasados = [p for p in pagos if p.fecha <= hoy]
    futuros = [p for p in pagos if p.fecha > hoy]
    if not futuros:
        return None  # bono ya vencido: no proyecta nada

    residual = pasados[-1].residual if pasados else RESIDUAL_ENTERO
    if residual is None or residual <= 0:
        return None

    proximo = futuros[0]
    # De dónde arranca el devengamiento: el último cupón cobrado, o la emisión si no cobró ninguno.
    desde = pasados[-1].fecha if pasados else proximo.emision

    corridos = 0.0
    if desde is not None and proximo.fecha > desde:
        transcurrido = (hoy - desde).days
        total = (proximo.fecha - desde).days
        if total > 0 and transcurrido > 0:
            corridos = proximo.interes * min(transcurrido / total, 1.0)
    return residual + corridos


def flujos_por_peso(
    especies: Sequence[EspecieUniverso],
    cronograma: Cronograma,
    paridades: Mapping[str, float | None],
    hoy: date,
) -> Flujos:
    """Los pagos futuros de cada especie, como fracción del monto que se invierta en ella.

    La paridad es **de la especie** y no de la emisión: MR46O y MR46D cotizan a precios distintos en
    monedas distintas, y por eso cada una tiene su propio precio sucio aunque compartan cronograma.
    Ésa es la razón por la que la clave del resultado es el ticker y no la raíz.
    """
    flujos: list[FlujoPorPeso] = []
    faltan_cronograma: list[str] = []
    faltan_paridad: list[str] = []
    faltan_paridad_cotizando: list[str] = []
    vencidos: list[str] = []

    for especie in especies:
        pagos = cronograma.pagos_de(especie.raiz)
        if not pagos:
            faltan_cronograma.append(especie.ticker)
            continue

        paridad = paridades.get(especie.ticker)
        if paridad is None or paridad <= 0:
            faltan_paridad.append(especie.ticker)
            # Sin rendimiento ni duración el instrumento no cotiza: en la vista del universo nunca
            # iba a ser candidato, así que no se lo alerta —listarlos a todos haría un padrón que
            # taparía los casos que importan—. Criterio del motor, y por eso los dos listados: el
            # completo no se pierde, porque quien pregunta por una cartera sí necesita saber que su
            # posición no se pudo calcular.
            if especie.rendimiento is not None or especie.duracion is not None:
                faltan_paridad_cotizando.append(especie.ticker)
            continue

        vt = valor_tecnico(pagos, hoy)
        if vt is None:
            vencidos.append(especie.ticker)
            continue

        precio_sucio = paridad * vt  # moneda de emisión, c/100 nominales
        if precio_sucio <= 0:
            vencidos.append(especie.ticker)
            continue

        flujos.extend(
            FlujoPorPeso(
                ticker=especie.ticker,
                fecha=pago.fecha,
                pct_renta=pago.interes / precio_sucio,
                pct_amortizacion=pago.capital / precio_sucio,
                pct_total=pago.total / precio_sucio,
            )
            for pago in pagos
            if pago.fecha > hoy
        )

    return Flujos(
        flujos=flujos,
        sin_cronograma=faltan_cronograma,
        sin_paridad=faltan_paridad,
        sin_paridad_que_cotizan=faltan_paridad_cotizando,
        vencidos=vencidos,
        evaluados=len(especies),
    )


def indexar_paridades(filas: Sequence[Mapping[str, object]]) -> dict[str, float | None]:
    """Las paridades por ticker. Un valor que no es número queda en `None`, no en cero.

    La diferencia importa: cero sería "cotiza a paridad cero", que es un dato, y `None` es "no se
    sabe", que es lo que hace que el instrumento se alerte en vez de calcularse mal.
    """
    return {str(fila["ticker"]): a_numero(fila.get("paridad")) for fila in filas}


def _a_fecha(valor: object) -> date | None:
    """La fecha de una columna `date` de Postgres, o de un `Timestamp` de pandas en un test.

    Es a propósito más angosta que `segmentacion._fecha`: acá no se interpreta ninguna cadena,
    porque las dos columnas de fecha del cronograma son `date` en la base y lo único que llega por
    otro camino son los `Timestamp` de la prueba de regresión contra el motor. Aceptar texto abriría
    la puerta a adivinar si `10/03/2030` es marzo o octubre, y una fecha de pago inventada corre el
    cupón de mes — que es exactamente el número que esta feature existe para decir.
    """
    if valor is None or valor != valor:  # `None`, `NaN` o `NaT`
        return None
    if isinstance(valor, datetime):
        return valor.date()
    return valor if isinstance(valor, date) else None
