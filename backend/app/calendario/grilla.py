"""La grilla de doce meses: qué cobra el asesor cada mes y de qué instrumento — F-015.

Portado de `tools/cupones.py` (`calendario`), con dos diferencias declaradas más abajo. Es la
estructura que consumen **F-016** (la grilla-selector), **F-021** (el panel de renta de una cartera)
y **F-036**; las tres leen esto y ninguna vuelve a decidir por su cuenta qué mes es cuál.

## La ventana arranca el mes que viene

Los doce meses se cuentan desde el **mes siguiente** al de hoy, no desde el mes en curso. La razón
es que los cupones de este mes con fecha anterior a hoy **ya se pagaron**: contarlos como parte de
la proyección diría que el asesor va a cobrar algo que ya cobró, y no contarlos dejando el mes en la
grilla marcaría al mes en curso como "mes sin renta" — un falso negativo que aparecería el 28 de
cada mes en casi todos los bonos y arruinaría el criterio que la grilla existe para aplicar.

Consecuencia medible y declarada: **los pagos que faltan de este mes quedan fuera de la grilla**. No
se pierden en silencio — se cuentan en `pendientes_este_mes`, para que nadie tenga que descubrirlo
comparando totales.

## Los meses sin pagos vienen con cero explícito

Los doce meses están **siempre**, completos y en orden, aunque ninguno de sus instrumentos pague.
Un cero vale más que una celda faltante cuando lo que se evalúa es la continuidad del ingreso: es
justamente el mes vacío el que hay que ver, y una fila ausente se lee como si no existiera el mes.

## Renta y amortización no se suman, y los totales no cruzan monedas

**Cobrar amortización no es renta**: es la devolución del capital prestado. Van en campos separados
en todos los niveles —instrumento, mes y año— y no hay ningún campo que los sume.

Y acá hay una diferencia deliberada con el motor: `tools/cupones.py` devuelve **un** total de renta
por mes, sumando todas las posiciones de la cartera. Eso vale mientras la cartera esté toda en una
moneda, que es como la usa el motor de línea de comandos, pero deja de valer apenas conviven un bono
hard dollar y una LECAP: cada `pct` es adimensional, así que al multiplicarlo por el monto de la
posición el resultado queda **en la moneda de esa posición**, y sumar pesos con dólares sería la
regla 3 del proyecto rota en el último paso. Por eso los totales del mes vienen **abiertos por
moneda de cobro**, derivada del segmento de cada instrumento (`MONEDA_SEGMENTO`), y no hay un total
único. Todas las monedas presentes aparecen en todos los meses, con cero explícito donde no se cobra
nada.

## Sin montos no hay totales, y eso es a propósito

La grilla del universo (F-016) no tiene montos: sus números son **fracciones del monto que se
invierta** en cada instrumento. Sumar esas fracciones entre instrumentos distintos no da plata ni da
nada — daría "cuánto rendiría poner un peso en cada uno", que nadie pidió y que se leería como si
fuera renta. Así que en esa vista el mes reporta cuántos instrumentos pagan y el detalle de cada
uno, y los totales quedan en `None`. La plata aparece cuando hay montos, que es cuando existe.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

from app.calendario.cupones import FlujoPorPeso, Flujos
from app.ingesta.alertas import Alerta
from app.universo.segmentacion import (
    MONEDA_SEGMENTO,
    NOMBRE_NATURALEZA,
    EspecieUniverso,
)

HORIZONTE_MESES = 12

MESES_ES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)


@dataclass(frozen=True, slots=True)
class InstrumentoDelMes:
    """Lo que un instrumento paga en un mes de la grilla.

    Un bono que paga en marzo y en septiembre aparece en los dos meses **con la misma clave de
    emisión**: es el mismo crédito cobrando dos veces, y quien mire la grilla tiene que poder verlo
    sin volver a cortar el ticker por su cuenta.
    """

    ticker: str
    emision: str
    fechas: list[date]
    """Las fechas exactas de cobro dentro del mes. Son una lista porque un bono puede pagar dos
    veces en el mismo mes, y aplanarlo a una sola fecha perdería un cobro."""

    pct_renta: float
    """Renta del mes como fracción del monto invertido en este instrumento."""

    pct_amortizacion: float
    renta: float | None
    """La renta en plata, en la moneda de cobro del instrumento. `None` sin monto: no se puede."""

    amortizacion: float | None
    moneda: str
    """En qué moneda cobra este instrumento, derivada de su segmento. Es lo que impide sumar un
    cupón en dólares con uno en pesos."""

    rendimiento: float | None
    """El número con el que se mide el instrumento, **en la unidad de su segmento**. Una LECAP trae
    TNA nominal en pesos y un global trae TIR en dólares: por eso viaja siempre con su naturaleza y
    nunca se lo rotula "TIR" a secas."""

    naturaleza: str
    vencimiento: date | None

    def como_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "emision": self.emision,
            "fechas": [f.isoformat() for f in self.fechas],
            "pct_renta": self.pct_renta,
            "pct_amortizacion": self.pct_amortizacion,
            "renta": self.renta,
            "amortizacion": self.amortizacion,
            "moneda": self.moneda,
            "rendimiento": self.rendimiento,
            "naturaleza": self.naturaleza,
            "naturaleza_nombre": NOMBRE_NATURALEZA[self.naturaleza],
            "vencimiento": self.vencimiento.isoformat() if self.vencimiento else None,
        }


@dataclass(frozen=True, slots=True)
class MesDelCalendario:
    """Un mes de la grilla, presente aunque no pague nadie."""

    anio: int
    mes: int
    instrumentos: list[InstrumentoDelMes] = field(default_factory=list)
    renta: dict[str, float] | None = None
    """Total de renta del mes, **abierto por moneda de cobro**. `None` cuando no hay montos."""

    amortizacion: dict[str, float] | None = None

    @property
    def etiqueta(self) -> str:
        return f"{self.mes:02d}/{self.anio}"

    @property
    def nombre(self) -> str:
        return f"{MESES_ES[self.mes - 1]} {self.anio}"

    @property
    def con_renta(self) -> int:
        """Cuántos instrumentos pagan renta este mes. Es el número que hace legible la grilla del
        universo, donde no hay plata que sumar."""
        return sum(1 for i in self.instrumentos if i.pct_renta > 0)

    @property
    def con_amortizacion(self) -> int:
        return sum(1 for i in self.instrumentos if i.pct_amortizacion > 0)

    @property
    def sin_renta(self) -> bool:
        """El mes que la grilla existe para encontrar: ninguno de los instrumentos paga renta."""
        return self.con_renta == 0

    def como_dict(self, *, detalle: bool = True) -> dict[str, object]:
        """El mes como viaja por el API.

        Sin detalle se va la lista de instrumentos y **queda el mes**, con sus totales y sus
        conteos: el mes vacío es el dato que la grilla existe para mostrar, no el relleno.
        """
        cuerpo: dict[str, object] = {
            "anio": self.anio,
            "mes": self.mes,
            "etiqueta": self.etiqueta,
            "nombre": self.nombre,
            "con_renta": self.con_renta,
            "con_amortizacion": self.con_amortizacion,
            "sin_renta": self.sin_renta,
            "renta": self.renta,
            "amortizacion": self.amortizacion,
        }
        if detalle:
            cuerpo["instrumentos"] = [i.como_dict() for i in self.instrumentos]
        return cuerpo


@dataclass(frozen=True, slots=True)
class Calendario:
    """La grilla de doce meses, con la trazabilidad de lo que quedó afuera al armarla."""

    meses: list[MesDelCalendario]
    hoy: date
    flujos: Flujos
    """De dónde salieron estos números. Viaja con la grilla porque un calendario sin saber cuántos
    instrumentos no entraron es un calendario que se lee como si el universo fuera el que
    muestra."""

    con_montos: bool = False
    """Si la grilla habla en plata o en fracciones del monto que se invierta en cada instrumento."""

    monedas: list[str] = field(default_factory=list)
    """Las monedas de cobro de la cartera. Vacía sin montos: no hay plata que separar por moneda."""

    pendientes_este_mes: int = 0
    """Pagos que caen entre hoy y el fin del mes en curso. Quedan fuera de la ventana por el
    criterio del módulo, y se cuentan acá para que la diferencia no aparezca como un descuadre sin
    origen."""

    alertas_de_la_vista: list[Alerta] = field(default_factory=list)
    """Lo que hay que avisar y **depende de quién pregunta**, no del cálculo: cuánto del universo
    cubre la grilla si la pregunta es por el universo, y qué posición no se pudo calcular si la
    pregunta es por una cartera. Las arma el servicio, que es el que sabe qué se le pidió."""

    @property
    def alertas(self) -> list[Alerta]:
        """Todo lo que hay que saber de esta grilla, en una sola lista.

        Va junto por la misma razón que en `UniversoSaneado.alertas`: quien las lee tiene un solo
        lugar donde mirar, y separar las del cálculo de las de la vista haría que uno de los dos
        grupos se mire menos que el otro."""
        return self.alertas_de_la_vista + self.flujos.alertas

    @property
    def meses_sin_renta(self) -> list[str]:
        """Los meses en los que no cobra renta ningún instrumento. El criterio de armado, en una
        línea: es lo que el asesor tiene que salir a cubrir."""
        return [m.etiqueta for m in self.meses if m.sin_renta]

    @property
    def renta_anual(self) -> dict[str, float] | None:
        return self._sumar_por_moneda([m.renta for m in self.meses])

    @property
    def amortizacion_anual(self) -> dict[str, float] | None:
        return self._sumar_por_moneda([m.amortizacion for m in self.meses])

    def _sumar_por_moneda(
        self, mensuales: Sequence[dict[str, float] | None]
    ) -> dict[str, float] | None:
        """La suma de los doce meses, por moneda y nunca entre monedas. `None` sin montos."""
        if not self.con_montos:
            return None
        total = dict.fromkeys(self.monedas, 0.0)
        for valores in mensuales:
            for moneda, valor in (valores or {}).items():
                total[moneda] += valor
        return total

    def resumen(self) -> dict[str, object]:
        """Los números que dicen si esta grilla sirve y qué se ve en ella.

        `renta_anual` y `amortizacion_anual` van **abiertos por moneda y nunca sumados**, y no hay
        un promedio mensual de renta: promediar doce meses en monedas distintas daría un número que
        no está en ninguna moneda.
        """
        return {
            "hoy": self.hoy.isoformat(),
            "desde": self.meses[0].etiqueta if self.meses else None,
            "hasta": self.meses[-1].etiqueta if self.meses else None,
            "con_montos": self.con_montos,
            "monedas": list(self.monedas),
            "instrumentos": len({i.ticker for m in self.meses for i in m.instrumentos}),
            "meses_sin_renta": self.meses_sin_renta,
            "renta_anual": self.renta_anual,
            "amortizacion_anual": self.amortizacion_anual,
            "pendientes_este_mes": self.pendientes_este_mes,
            "flujos": self.flujos.resumen(),
        }

    def como_dict(self, *, detalle: bool = True) -> dict[str, object]:
        return {
            "resumen": self.resumen(),
            "meses": [m.como_dict(detalle=detalle) for m in self.meses],
            "alertas": [a.como_dict() for a in self.alertas],
        }


def ventana(hoy: date, horizonte: int = HORIZONTE_MESES) -> list[tuple[int, int]]:
    """Los meses de la grilla, como pares (año, mes). Arranca el mes que viene: ver el módulo."""
    return [_sumar_meses(hoy.year, hoy.month, n) for n in range(1, horizonte + 1)]


def armar_calendario(
    flujos: Flujos,
    especies: Sequence[EspecieUniverso],
    hoy: date,
    *,
    montos: Mapping[str, float] | None = None,
    horizonte: int = HORIZONTE_MESES,
    alertas_de_la_vista: Sequence[Alerta] = (),
) -> Calendario:
    """Reparte los flujos futuros en los doce meses que vienen.

    `montos` es lo que separa las dos vistas: sin él la grilla habla en fracciones del monto que se
    invierta —es la del universo, la que consume F-016— y con él habla en plata, que es la de una
    cartera concreta (F-021). Un ticker con monto pero sin flujos simplemente no aparece: su
    faltante ya está nombrado en las alertas de `flujos`, y meterlo en la grilla con ceros diría que
    ese bono no paga nada, que es distinto de no saber cuánto paga.
    """
    datos = {e.ticker: e for e in especies}
    meses = ventana(hoy, horizonte)
    indice_de_mes = {mes: n for n, mes in enumerate(meses)}

    en_ventana: list[list[FlujoPorPeso]] = [[] for _ in meses]
    pendientes = 0
    for flujo in flujos.flujos:
        if montos is not None and flujo.ticker not in montos:
            continue
        posicion = indice_de_mes.get((flujo.fecha.year, flujo.fecha.month))
        if posicion is None:
            if (flujo.fecha.year, flujo.fecha.month) == (hoy.year, hoy.month):
                pendientes += 1
            continue
        en_ventana[posicion].append(flujo)

    # Las monedas salen de las posiciones y no de lo que se cobra en la ventana: una cartera con un
    # bono en dólares que no paga ningún cupón en los próximos doce meses tiene que mostrar doce
    # ceros en dólares, y no una moneda ausente que se leería como si el bono no estuviera.
    monedas = (
        sorted({_moneda(datos[t]) for t in montos if t in datos}) if montos is not None else []
    )

    return Calendario(
        meses=[
            _armar_mes(anio, mes, grupo, datos, montos, monedas)
            for (anio, mes), grupo in zip(meses, en_ventana, strict=True)
        ],
        hoy=hoy,
        flujos=flujos,
        con_montos=montos is not None,
        monedas=monedas,
        pendientes_este_mes=pendientes,
        alertas_de_la_vista=list(alertas_de_la_vista),
    )


def _armar_mes(
    anio: int,
    mes: int,
    grupo: Sequence[FlujoPorPeso],
    datos: Mapping[str, EspecieUniverso],
    montos: Mapping[str, float] | None,
    monedas: Sequence[str],
) -> MesDelCalendario:
    """Un mes de la grilla, con sus instrumentos agregados y sus totales por moneda.

    Los pagos se agregan **por instrumento y no por pago**: un bono que paga dos veces en el mismo
    mes es una sola línea del mes con las dos fechas, porque lo que la grilla contesta es "quién me
    paga en marzo", no "cuántas transferencias entran en marzo".
    """
    por_ticker: dict[str, list[FlujoPorPeso]] = {}
    for flujo in grupo:
        por_ticker.setdefault(flujo.ticker, []).append(flujo)

    # `datos[ticker]` sin `.get`: los flujos se calculan sobre estas mismas especies, así que un
    # ticker sin especie sería un error de programación y no un faltante de dato. Taparlo con un
    # valor por defecto haría aparecer un instrumento sin moneda ni naturaleza en la grilla.
    instrumentos = [
        _armar_instrumento(ticker, pagos, datos[ticker], montos)
        for ticker, pagos in sorted(por_ticker.items())
    ]

    if montos is None:
        return MesDelCalendario(anio=anio, mes=mes, instrumentos=instrumentos)

    # Con montos, **todas** las monedas aparecen en todos los meses: un mes en el que no se cobra
    # nada en dólares tiene que decir cero en dólares, no omitir la moneda.
    renta = dict.fromkeys(monedas, 0.0)
    amortizacion = dict.fromkeys(monedas, 0.0)
    for instrumento in instrumentos:
        renta[instrumento.moneda] += instrumento.renta or 0.0
        amortizacion[instrumento.moneda] += instrumento.amortizacion or 0.0

    return MesDelCalendario(
        anio=anio,
        mes=mes,
        instrumentos=instrumentos,
        renta=renta,
        amortizacion=amortizacion,
    )


def _armar_instrumento(
    ticker: str,
    pagos: Sequence[FlujoPorPeso],
    especie: EspecieUniverso,
    montos: Mapping[str, float] | None,
) -> InstrumentoDelMes:
    """Lo que un instrumento paga en un mes, sumando sus pagos de ese mes.

    Se suman entre sí porque son el mismo instrumento y la misma moneda: acá no se cruza nada.
    """
    pct_renta = sum(p.pct_renta for p in pagos)
    pct_amortizacion = sum(p.pct_amortizacion for p in pagos)
    monto = montos.get(ticker) if montos is not None else None
    return InstrumentoDelMes(
        ticker=ticker,
        emision=especie.raiz,
        fechas=sorted(p.fecha for p in pagos),
        pct_renta=pct_renta,
        pct_amortizacion=pct_amortizacion,
        renta=pct_renta * monto if monto is not None else None,
        amortizacion=pct_amortizacion * monto if monto is not None else None,
        moneda=_moneda(especie),
        rendimiento=especie.rendimiento,
        naturaleza=especie.naturaleza,
        vencimiento=especie.vencimiento,
    )


def _moneda(especie: EspecieUniverso) -> str:
    """En qué moneda cobra el inversor, derivada del segmento.

    Dólar linked paga **en pesos** aunque siga al dólar, y por eso la moneda sale de
    `MONEDA_SEGMENTO` y no del sufijo del ticker ni de la moneda de cotización: lo que se está
    separando es la moneda en la que entra la plata del cupón.
    """
    return MONEDA_SEGMENTO[especie.segmento]


def _sumar_meses(anio: int, mes: int, cantidad: int) -> tuple[int, int]:
    indice = anio * 12 + (mes - 1) + cantidad
    return indice // 12, indice % 12 + 1
