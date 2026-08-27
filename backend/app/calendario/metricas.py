"""TIR, duración y paridad de una especie, calculadas sobre su propio flujo contractual.

Continúa la matemática de `cupones.py`: opera sobre sus `Pago` y sobre `valor_tecnico`. Lo que
`cupones.py` traduce a fracciones del monto invertido, este módulo lo resuelve como rendimiento.

**F-040 (sensibilidad por repricing) importa de acá.** `valor_presente` y `anios_entre` son las dos
piezas que su tabla de escenarios necesita, y por eso tienen la misma forma que en el motor
(`tools/cupones.py::_valor_presente`, secuencias `t` y `cf` paralelas): el port de `retorno_por_tir`
tiene que ser una lectura, no una traducción.

## La precondición que este módulo no puede verificar solo

Descontar un flujo contra un precio exige que los dos estén en la misma moneda. Acá eso se asume:
el llamador es el que sabe en qué moneda cotiza la especie y en cuál paga la emisión. Quien decide
—y quien deja afuera a las especies donde no coinciden— es
`app/ingesta/consolidacion/metricas.py`. Si esa precondición se rompe, este módulo devuelve un
número perfectamente calculado que no significa nada, que es exactamente lo que la regla 3 del
proyecto prohíbe.

## Por qué bisección y no Newton

Con todos los flujos positivos, el valor presente es estrictamente decreciente en la tasa: hay una
sola raíz y el bracketing la encuentra siempre. Newton converge más rápido pero necesita derivada,
puede divergir según el punto de partida y hace que el resultado dependa de él. La regla 6 del
proyecto pide análisis determinístico, y determinístico significa que dos corridas sobre el mismo
insumo devuelven el mismo bit. Con ~2.000 especies de ~20 flujos, las iteraciones de más no se
notan.

## Cuándo no hay número

Nunca se estima. Si el precio queda fuera del rango que el flujo puede explicar, o si el bono ya
venció, la métrica sale `None` con un motivo que el llamador cuenta y nombra. Un rendimiento
inventado es peor que un campo vacío: el campo vacío se ve.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.calendario.cupones import Pago, componentes_valor_tecnico

# Días por año para llevar una fecha a la exponente del descuento. Es la convención del motor
# (`tools/cupones.py`), no un estándar de mercado: la base de cálculo real de cada bono depende de
# su `days_convention`, que la fuente publica pero el universo todavía no persiste. Cambiar esto
# mueve todas las TIR del sistema.
DIAS_POR_ANIO = 365.25

# Piso del bracket. Por debajo de -1 el factor de descuento cambia de signo y el valor presente deja
# de tener sentido; el motor corta en -0,99 y acá se respeta ese límite.
TASA_PISO = -0.99

# Techo del bracket: 10.000 % efectivo anual.
#
# **Era 10.0 (1000 % EA) hasta el 26/08/2026, y ese techo cortaba rendimientos reales.** El
# antecedente está medido en `docs/ESTADO.md:194`: SNSBO rindiendo 245 % es dato correcto —un bono
# a 80 días al 78 % de su valor técnico anualiza ahí—, y esa misma aritmética con plazos más
# cortos se pasa del 1000 % sin dejar de ser aritmética. Un bono a 60 días al 61 % de paridad
# anualiza al 1900 % EA: con el techo viejo salía `tir_sobre_techo`, sin número, cuando el número
# existía y era exacto.
#
# Medido el 26/08/2026 sobre un cupón cero: la paridad por debajo de la cual el solver dejaba de
# devolver número, por plazo al vencimiento, con cada techo.
#
#     plazo    techo 10.0    techo 100.0
#      15 d        90,6 %         82,7 %
#      30 d        82,1 %         68,5 %
#      60 d        67,4 %         46,9 %
#      90 d        55,4 %         32,1 %
#     180 d        30,7 %         10,3 %
#
# Leído en la primera fila: con el techo viejo, **cualquier** especie a 30 días que cotizara por
# debajo del 82 % de su valor técnico salía sin TIR. En `cashflow_completo.csv` hay 56 emisiones
# con vencimiento dentro de los 90 días —SNSBO entre ellas—, que son las que quedaban expuestas.
#
# **El solver no es quien decide qué rendimiento es creíble.** El bracket sólo tiene que contener
# la raíz; el filtro de plausibilidad es la capa de sanidad por segmento
# (`app/universo/sanidad.py`, `TOPE_SANIDAD_SEGMENTO`), que aplica topes por naturaleza de tasa y
# **rotula** la especie sospechosa en vez de vaciarle la celda. Vaciar acá pierde el dato; rotular
# allá lo conserva con su advertencia, que es lo que la regla 1 pide.
#
# El bracket más ancho no compromete la convergencia: la bisección parte de un intervalo de
# 100,99 y lo parte al medio, así que hace falta n con 100,99/2ⁿ < 1e-10, o sea n = 40. Con el
# techo viejo hacían falta 37. `MAX_ITERACIONES = 200` cubre las dos con margen de sobra.
TASA_TECHO = 100.0

TOLERANCIA_SOLVER = 1e-10
MAX_ITERACIONES = 200

MOTIVO_VENCIDA = "vencida"
MOTIVO_TIR_BAJO_PISO = "tir_bajo_piso"
MOTIVO_TIR_SOBRE_TECHO = "tir_sobre_techo"
MOTIVO_SIN_CONVERGENCIA = "sin_convergencia"

MOTIVO_SIN_PRECIO_POSITIVO = "sin_precio_positivo"
"""El precio operado vino en cero o negativo. Hasta el 26/08/2026 esto salía rotulado `vencida`,
que es falso: un bono vivo sin precio publicado no venció, le falta el precio del día."""

MOTIVO_RESIDUAL_CONTRADICTORIO = "residual_contradictorio"
"""Relevamiento de confiabilidad de datos (16/08/2026): el residual que declara el cronograma para
el último pago pasado no coincide con `100 - Σ capital` de los pagos ya cobrados (ver
`cupones.componentes_valor_tecnico`) — la fuente dejó el residual clavado en 100 mientras el bono
amortizaba.

Vive acá y no en `app/ingesta/consolidacion/metricas.py`, donde estuvo hasta el 26/08/2026, porque
desde esa fecha `metricas_de` también lo emite: ese módulo importa de éste, así que la constante
tiene que estar del lado del que no importa a nadie. Es un faltante del dato de hoy —no una
decisión de diseño— y por eso cae en el balde "sin insumo" de las alertas, no en el de las
naturalezas excluidas."""

MOTIVO_SIN_RESIDUAL_VIGENTE = "sin_residual_vigente"
"""El cronograma tiene pagos futuros pero el residual que declara ya está agotado o no viene. Sin
residual vivo no hay valor técnico contra el cual medir, y tampoco es un vencimiento: el
calendario sigue proyectando pagos."""


@dataclass(frozen=True, slots=True)
class MetricasEspecie:
    """Lo que se pudo calcular de una especie, y el motivo de lo que no.

    Las métricas son independientes entre sí a propósito: la paridad sale del valor técnico y no
    necesita la TIR, así que un bono cuya TIR no resuelve **igual reporta su paridad**. Vaciar las
    tres porque una falló sería perder dato que sí existe.
    """

    tir: float | None
    """Efectiva anual, en fracción, en la moneda y la naturaleza del flujo."""

    duration: float | None
    """Duración modificada, en años. Es la que viaja a la columna `duration` del universo."""

    duration_macaulay: float | None
    """No se persiste. Queda expuesta porque es la que tiene forma cerrada conocida en los casos de
    prueba (la de un cupón cero es exactamente su plazo) y porque F-040 la necesita como cota."""

    paridad: float | None
    motivo: str | None


def anios_entre(desde: date, hasta: date) -> float:
    """Plazo en años entre dos fechas, para usar de exponente en el descuento."""
    return (hasta - desde).days / DIAS_POR_ANIO


def valor_presente(t: Sequence[float], cf: Sequence[float], tasa: float) -> float:
    """Valor presente de los flujos `cf` a los plazos `t`, descontados a `tasa` efectiva anual.

    `t` y `cf` son secuencias paralelas, misma forma que en el motor. La tasa se asume por encima de
    `TASA_PISO`: el llamador es quien acota, porque quien itera sabe qué está buscando.
    """
    return sum(flujo / (1.0 + tasa) ** plazo for plazo, flujo in zip(t, cf, strict=True))


def resolver_tir(t: Sequence[float], cf: Sequence[float], precio_sucio: float) -> float | None:
    """La tasa que iguala el valor presente de los flujos al precio, o `None` con su motivo aparte.

    Devuelve sólo la tasa. El motivo del `None` lo deriva `metricas_de`, que es quien arma el
    resultado completo: acá alcanza con distinguir "no hay raíz" de "hay raíz", y el llamador
    reconstruye cuál de los dos extremos falló volviendo a evaluar el valor presente.
    """
    if not t or precio_sucio <= 0:
        return None

    piso = TASA_PISO + 1e-9
    techo = TASA_TECHO
    # f decrece en la tasa: f(piso) es el valor presente más alto posible y f(techo) el más bajo.
    f_piso = valor_presente(t, cf, piso) - precio_sucio
    f_techo = valor_presente(t, cf, techo) - precio_sucio
    if f_piso <= 0.0 or f_techo >= 0.0:
        return None  # el precio no está dentro de lo que este flujo puede explicar

    for _ in range(MAX_ITERACIONES):
        medio = (piso + techo) / 2.0
        if techo - piso < TOLERANCIA_SOLVER:
            return medio
        if valor_presente(t, cf, medio) - precio_sucio > 0.0:
            piso = medio
        else:
            techo = medio
    return None  # no convergió: con bracket válido no debería pasar, y si pasa no se inventa


def duracion_macaulay(t: Sequence[float], cf: Sequence[float], tasa: float) -> float | None:
    """Plazo promedio de los flujos, ponderado por su valor presente. En años."""
    presentes = [flujo / (1.0 + tasa) ** plazo for plazo, flujo in zip(t, cf, strict=True)]
    total = sum(presentes)
    if total <= 0:
        return None
    return sum(plazo * vp for plazo, vp in zip(t, presentes, strict=True)) / total


def duracion_modificada(t: Sequence[float], cf: Sequence[float], tasa: float) -> float | None:
    """Macaulay dividida por (1 + tasa), coherente con el descuento efectivo anual de este módulo.

    **IAMC publica su duración modificada con su propia convención de capitalización** —que no
    declara— así que las dos no tienen por qué coincidir al decimal. La diferencia es de décimas y
    es lo que absorbe la tolerancia del contraste; no es un error a corregir acá.
    """
    macaulay = duracion_macaulay(t, cf, tasa)
    if macaulay is None:
        return None
    return macaulay / (1.0 + tasa)


def paridad_de(precio_sucio: float, tecnico: float | None) -> float | None:
    """Precio sobre valor técnico. Adimensional **sólo si los dos están en la misma moneda**."""
    if tecnico is None or tecnico <= 0:
        return None
    return precio_sucio / tecnico


def _sin_metricas(motivo: str, paridad: float | None = None) -> MetricasEspecie:
    """Las tres métricas vacías con su motivo. La paridad se pasa aparte porque hay casos donde sí
    se pudo calcular aunque la TIR no —ver el docstring de `MetricasEspecie`—."""
    return MetricasEspecie(
        tir=None, duration=None, duration_macaulay=None, paridad=paridad, motivo=motivo
    )


def metricas_de(pagos: Sequence[Pago], precio_sucio: float, hoy: date) -> MetricasEspecie:
    """Las tres métricas de una especie a partir de su cronograma y su precio del día.

    `precio_sucio` es el precio operado de la especie, cada 100 nominales y en la moneda en que
    cotiza — que el llamador ya verificó que es la del flujo. No se ajusta por corridos: el precio
    de mercado ya los incluye, que es por qué se lo compara contra el valor técnico y no contra el
    residual pelado.

    **Cada motivo nombra lo que efectivamente pasó (26/08/2026).** Hasta esa fecha tres
    situaciones distintas salían las tres como `vencida`: el bono sin pagos futuros, el precio en
    cero y el residual que no cierra. Sólo la primera es un vencimiento; las otras dos son
    faltantes del dato del día, y rotularlas como vencidas mandaba a buscar el problema al lugar
    equivocado —a la emisión, cuando estaba en el precio o en el cronograma—.
    """
    futuros = [p for p in pagos if p.fecha > hoy]
    if not futuros:
        return _sin_metricas(MOTIVO_VENCIDA)
    if precio_sucio <= 0:
        return _sin_metricas(MOTIVO_SIN_PRECIO_POSITIVO)

    componentes = componentes_valor_tecnico(pagos, hoy)
    tecnico = componentes.valor_tecnico
    paridad = paridad_de(precio_sucio, tecnico)
    if tecnico is None:
        # Sin residual vivo el bono no proyecta nada aunque tenga fechas futuras cargadas, y las
        # dos razones por las que puede no haberlo piden acciones distintas: el residual que se
        # contradice con lo amortizado es un dato a corregir en la fuente, el residual agotado o
        # ausente es un faltante a completar. `coherente` es lo que las separa.
        return _sin_metricas(
            MOTIVO_RESIDUAL_CONTRADICTORIO
            if not componentes.coherente
            else MOTIVO_SIN_RESIDUAL_VIGENTE
        )

    t = [anios_entre(hoy, p.fecha) for p in futuros]
    cf = [p.total for p in futuros]
    tir = resolver_tir(t, cf, precio_sucio)
    if tir is None:
        return _sin_metricas(_motivo_sin_tir(t, cf, precio_sucio), paridad=paridad)

    return MetricasEspecie(
        tir=tir,
        duration=duracion_modificada(t, cf, tir),
        duration_macaulay=duracion_macaulay(t, cf, tir),
        paridad=paridad,
        motivo=None,
    )


def _motivo_sin_tir(t: Sequence[float], cf: Sequence[float], precio_sucio: float) -> str:
    """De qué lado del bracket se cayó el precio. Se nombra el extremo, no un genérico."""
    if valor_presente(t, cf, TASA_PISO + 1e-9) - precio_sucio <= 0.0:
        return MOTIVO_TIR_BAJO_PISO
    if valor_presente(t, cf, TASA_TECHO) - precio_sucio >= 0.0:
        return MOTIVO_TIR_SOBRE_TECHO
    return MOTIVO_SIN_CONVERGENCIA


def retorno_por_tir(
    pagos: Sequence[Pago],
    tir_actual: float | None,
    deltas: Sequence[float],
    hoy: date,
) -> dict[float, float] | None:
    """Cuánto se movería el precio si la TIR del bono cambiara.

    Repricing completo del cashflow contractual, no una aproximación por duración: se descuentan
    todos los flujos futuros a la TIR nueva y se compara contra descontarlos a la TIR de hoy. En
    bonos largos la aproximación lineal subestima fuerte la suba ante compresiones grandes, y
    justamente esos son los escenarios que interesan (F-040). Port de `tools/cupones.py`.

    `deltas` en fracciones (-0.01 = comprime 100 bps). Devuelve {delta: retorno} o `None` si falta
    TIR, no quedan pagos futuros o el valor presente base no es positivo. Un delta que deje la tasa
    en `TASA_PISO` o por debajo se omite del resultado: descuento degenerado, no se reporta un
    número inventado.
    """
    if tir_actual is None:
        return None
    futuros = [p for p in pagos if p.fecha > hoy]
    if not futuros:
        return None
    t = [anios_entre(hoy, p.fecha) for p in futuros]
    cf = [p.total for p in futuros]
    base = valor_presente(t, cf, tir_actual)
    if base <= 0:
        return None
    out: dict[float, float] = {}
    for d in deltas:
        y = tir_actual + d
        if y <= TASA_PISO:
            continue
        out[d] = valor_presente(t, cf, y) / base - 1
    return out or None
