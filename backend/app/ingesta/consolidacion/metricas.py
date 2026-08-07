"""Qué especie tiene métricas propias, cuál conserva las de IAMC, y cuál no tiene ninguna — F-051.

`app/calendario/metricas.py` sabe resolver una TIR. Este módulo sabe **cuándo tiene sentido
pedirla**, que es la parte que las reglas del dominio deciden y la matemática no.

## La regla que gobierna todo: precio y flujo en la misma moneda

Descontar un flujo contra un precio da un rendimiento sólo si los dos están en la misma unidad. Una
especie D de un bono hard-dollar cotiza en dólares y paga en dólares: se calcula. La especie sin
sufijo del mismo bono cotiza en pesos y paga en dólares: **no se calcula**. Traerla al mismo plano
pediría un tipo de cambio, y el único disponible sale de dividir el precio de la especie D por el de
la pelada — es decir, del propio bono. Usarlo sería derivar la TIR de AL30 desde AL30D, que es
copiarle la métrica a la hermana: exactamente lo que la regla 1 prohíbe y lo que el test
`test_la_tir_de_una_especie_no_se_copia_a_sus_hermanas` viene cuidando desde F-007.

Para esas especies **IAMC sigue siendo fuente** donde publica. No es una excepción silenciosa: la
columna `fuente` de cada fila dice de dónde salió su número.

## Las naturalezas que quedan afuera, y por qué cada una

No es una lista de casos difíciles: es una lista de flujos que no alcanzan para la tasa que el
segmento reporta.

- **CER**: el cronograma trae los montos contractuales, sin el coeficiente. Medido sobre el dato
  versionado: TX26 paga 1,0 de interés, que es 2 % semestral sobre un residual de 100 exacto, y su
  residual baja 100→80→60→40→20→0. Si vinieran ajustados serían crecientes y de otro orden. El
  precio en pesos **sí** incorpora el CER acumulado, así que descontarlo contra estos flujos mezcla
  una punta ajustada con otra que no lo está. La tasa real limpia necesita el índice CER, que el
  proyecto no ingiere.
- **Dollar-linked**: el pago en pesos depende del tipo de cambio del día de pago. El flujo no está
  determinado en la moneda del precio hasta que ese día llega.
- **Badlar y Tamar**: los intereses futuros del feed son proyección a la tasa vigente, no montos
  contratados. Descontar una proyección y presentar el resultado como rendimiento del bono sería
  presentar un supuesto como dato.

En los cuatro casos la especie queda fuera **con su motivo nombrado**, y jamás se le reporta la tasa
de otra naturaleza para llenar la celda.

## El contraste contra IAMC

IAMC deja de ser fuente para lo que calculamos y pasa a ser control, el mismo movimiento que F-012
hizo con el Índice Dólar de BYMA. Se compara por raíz de emisión porque TIR en dólares, duración y
paridad son magnitudes de la emisión y no de la especie de liquidación —es el mismo hecho que F-011
usa para agrupar—, así que el valor que IAMC publica para la especie pelada es contrastable contra
el que calculamos para la D. Lo que los separa es el canje MEP/cable, y las tolerancias están
fijadas por encima de él a propósito: una alerta que grita todos los días por un spread
estructural es una alerta que nadie mira.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.calendario.metricas import MetricasEspecie
from app.ingesta.alertas import Alerta, Severidad

# Cuántos tickers se nombran en el cuerpo de una alerta antes de cortar. El detalle lleva la lista
# entera; el mensaje tiene que poder leerse. Mismo criterio que `universo/cambio.py`.
MUESTRA_ALERTA = 6

# Qué moneda de cotización hace comparable el precio con el flujo, por tipo de tasa. `EXT` es la
# denominación de la especie cable y cotiza en dólares igual que `USD` (ver `universo/cambio.py`).
MONEDAS_DEL_FLUJO: dict[str, frozenset[str]] = {
    "hard-dollar": frozenset({"USD", "EXT"}),
    "bopreal": frozenset({"USD", "EXT"}),
    "tasa-fija": frozenset({"ARS"}),
}

# Tipos de tasa cuyo flujo contractual no alcanza para la unidad del segmento. El texto es el motivo
# que viaja a la alerta: se declara por qué, no sólo que quedó afuera.
NATURALEZAS_FUERA: dict[str, str] = {
    "cer": (
        "el cronograma trae los montos contractuales sin el coeficiente CER y el precio en pesos "
        "sí lo incorpora: sin el índice no hay tasa real limpia"
    ),
    "dollar-linked": (
        "el pago en pesos depende del tipo de cambio de la fecha de pago: el flujo no está "
        "determinado en la moneda del precio"
    ),
    "badlar": (
        "los cupones futuros dependen de una tasa variable: el flujo publicado es una proyección, "
        "no un monto contratado"
    ),
    "tamar": (
        "los cupones futuros dependen de una tasa variable: el flujo publicado es una proyección, "
        "no un monto contratado"
    ),
}

FUENTE_CALCULO = "calculo"
FUENTE_IAMC = "iamc"
FUENTE_FUERA = "fuera"

MOTIVO_MONEDA_CRUZADA = "moneda_cruzada"
MOTIVO_SIN_PRECIO = "sin_precio"
MOTIVO_SIN_CRONOGRAMA = "sin_cronograma"
MOTIVO_SIN_TIPO_TASA = "sin_tipo_de_tasa"

# Cuánto pueden separarse el cálculo propio y lo publicado antes de que valga la pena mirarlo.
# La TIR: 100 pb absolutos. El canje MEP/cable (~3,6 % de precio) sobre una duración de 5 a 7 años
# ya explica 50 a 70 pb, y encima se suman la base de días y la hora de captura —IAMC cierra al
# final de la rueda y BYMA es intradía—. Por debajo de 100 pb la diferencia es convención, no dato.
TOLERANCIA_TIR = 0.01

# La duración: media año. La diferencia de convención de capitalización entre su modificada y la
# nuestra mueve décimas; medio año es holgado para eso y sigue siendo chico contra una duración mal
# calculada, que se iría en años.
TOLERANCIA_DURATION = 0.5

# La paridad: 5 %, el mismo `TOLERANCIA_CONTRASTE` que F-012 usa para el tipo de cambio, y por la
# misma razón: está por encima del canje conocido.
TOLERANCIA_PARIDAD = 0.05

CODIGO_METRICAS_SIN_INSUMO = "metricas_propias_sin_insumo"
CODIGO_METRICAS_FUERA_DE_NATURALEZA = "metricas_fuera_de_naturaleza"
CODIGO_METRICAS_CONTRASTE_IAMC = "metricas_contraste_iamc"


def fuente_de_metricas(tipo_tasa: str | None, moneda_cotizacion: str | None) -> str:
    """De dónde salen `tir`, `duration` y `paridad` para esta especie.

    `FUENTE_CALCULO` si el flujo y el precio comparten moneda; `FUENTE_FUERA` si la naturaleza de la
    tasa no se puede calcular con el flujo disponible o si las monedas no coinciden; `FUENTE_IAMC`
    si el tipo de tasa no se conoce, único caso en el que lo publicado es todo lo que hay.
    """
    if tipo_tasa is None:
        return FUENTE_IAMC
    if tipo_tasa in NATURALEZAS_FUERA:
        return FUENTE_FUERA
    monedas = MONEDAS_DEL_FLUJO.get(tipo_tasa)
    if monedas is None:
        return FUENTE_IAMC  # naturaleza nueva sin tabla: se conserva lo publicado, no se improvisa
    if moneda_cotizacion is None or moneda_cotizacion not in monedas:
        return FUENTE_FUERA
    return FUENTE_CALCULO


def motivo_de_exclusion(tipo_tasa: str | None, moneda_cotizacion: str | None) -> str:
    """Por qué esta especie quedó fuera del cálculo. Sólo se llama cuando la fuente es `fuera`."""
    if tipo_tasa is None:
        return MOTIVO_SIN_TIPO_TASA
    if tipo_tasa in NATURALEZAS_FUERA:
        return tipo_tasa
    del moneda_cotizacion  # la única otra razón de exclusión es que no coincida con el flujo
    return MOTIVO_MONEDA_CRUZADA


@dataclass(frozen=True, slots=True)
class ContrasteMetricas:
    """Lo calculado contra lo que IAMC publica para la misma emisión.

    `ticker_propio` y `ticker_iamc` pueden ser distintos: IAMC nombra una especie por emisión —casi
    siempre la pelada— y nosotros calculamos las que cotizan en la moneda del flujo. Se contrastan
    igual porque la TIR en dólares es de la emisión, no de la especie.
    """

    raiz: str
    ticker_propio: str
    ticker_iamc: str
    tir_propia: float | None = None
    tir_iamc: float | None = None
    duration_propia: float | None = None
    duration_iamc: float | None = None
    paridad_propia: float | None = None
    paridad_iamc: float | None = None

    def divergencias(self) -> dict[str, dict[str, float]]:
        """Las métricas que se separan más allá de su tolerancia. Vacío es coincidencia."""
        pares = (
            ("tir", self.tir_propia, self.tir_iamc, TOLERANCIA_TIR),
            ("duration", self.duration_propia, self.duration_iamc, TOLERANCIA_DURATION),
            ("paridad", self.paridad_propia, self.paridad_iamc, TOLERANCIA_PARIDAD),
        )
        fuera: dict[str, dict[str, float]] = {}
        for nombre, propio, publicado, tolerancia in pares:
            if propio is None or publicado is None:
                continue  # no se contrasta contra un faltante: no hay divergencia que medir
            diferencia = propio - publicado
            if abs(diferencia) > tolerancia:
                fuera[nombre] = {
                    "propio": propio,
                    "publicado": publicado,
                    "diferencia": diferencia,
                    "tolerancia": tolerancia,
                }
        return fuera

    @property
    def coincide(self) -> bool:
        return not self.divergencias()

    def como_dict(self) -> dict[str, object]:
        return {
            "raiz": self.raiz,
            "ticker_propio": self.ticker_propio,
            "ticker_iamc": self.ticker_iamc,
            "divergencias": self.divergencias(),
        }


@dataclass
class ResultadoMetricas:
    """Qué se calculó en una corrida, qué quedó afuera y por qué, y qué dijo el contraste."""

    calculadas: int = 0
    por_motivo: dict[str, list[str]] = field(default_factory=dict)
    contrastes: list[ContrasteMetricas] = field(default_factory=list)

    def registrar(self, ticker: str, metricas: MetricasEspecie) -> None:
        self.calculadas += 1
        if metricas.motivo is not None:
            self.anotar(metricas.motivo, ticker)

    def anotar(self, motivo: str, ticker: str) -> None:
        self.por_motivo.setdefault(motivo, []).append(ticker)

    @property
    def divergentes(self) -> list[ContrasteMetricas]:
        return [c for c in self.contrastes if not c.coincide]

    @property
    def alertas(self) -> list[Alerta]:
        alertas = []
        sin_insumo = {
            m: t for m, t in self.por_motivo.items() if m not in NATURALEZAS_FUERA_O_CRUCE
        }
        fuera = {m: t for m, t in self.por_motivo.items() if m in NATURALEZAS_FUERA_O_CRUCE}
        if sin_insumo:
            alertas.append(metricas_sin_insumo(sin_insumo))
        if fuera:
            alertas.append(metricas_fuera_de_naturaleza(fuera))
        if self.divergentes:
            alertas.append(contraste_iamc(self.divergentes))
        return alertas

    def resumen(self) -> dict[str, object]:
        return {
            "calculadas": self.calculadas,
            "sin_metrica": {motivo: len(t) for motivo, t in sorted(self.por_motivo.items())},
            "contrastadas": len(self.contrastes),
            "divergentes": len(self.divergentes),
        }


# Los motivos que son "esta especie no entra al cálculo" y no "el insumo no alcanzó". Se separan
# porque piden acciones distintas: uno es una decisión de diseño declarada, el otro es un faltante
# del día que puede resolverse mañana.
NATURALEZAS_FUERA_O_CRUCE = frozenset(NATURALEZAS_FUERA) | {
    MOTIVO_MONEDA_CRUZADA,
    MOTIVO_SIN_TIPO_TASA,
}


def _muestra(tickers: Sequence[str]) -> str:
    visibles = ", ".join(sorted(tickers)[:MUESTRA_ALERTA])
    resto = len(tickers) - MUESTRA_ALERTA
    return f"{visibles} y {resto} más" if resto > 0 else visibles


def metricas_sin_insumo(por_motivo: Mapping[str, Sequence[str]]) -> Alerta:
    """Especies que se iban a calcular y no se pudo. El campo queda vacío y acá van sus nombres."""
    total = sum(len(t) for t in por_motivo.values())
    detalle = {motivo: sorted(tickers) for motivo, tickers in por_motivo.items()}
    partes = [f"{motivo}: {_muestra(t)}" for motivo, t in sorted(por_motivo.items())]
    return Alerta(
        codigo=CODIGO_METRICAS_SIN_INSUMO,
        mensaje=(
            f"{total} especies quedaron sin métricas propias por falta de insumo. "
            + " · ".join(partes)
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Revisar si falta el precio del día o el cronograma de la emisión. No se completan por "
            "analogía ni con la métrica de otra especie de la misma emisión."
        ),
        detalle={"cantidad": total, "por_motivo": detalle},
    )


def metricas_fuera_de_naturaleza(por_motivo: Mapping[str, Sequence[str]]) -> Alerta:
    """Especies que no entran al cálculo por diseño, cada una con el porqué de su naturaleza."""
    total = sum(len(t) for t in por_motivo.values())
    detalle = {
        motivo: {
            "porque": NATURALEZAS_FUERA.get(motivo, _PORQUE_CRUCE.get(motivo, "")),
            "cantidad": len(tickers),
            "tickers": sorted(tickers),
        }
        for motivo, tickers in por_motivo.items()
    }
    return Alerta(
        codigo=CODIGO_METRICAS_FUERA_DE_NATURALEZA,
        mensaje=(
            f"{total} especies quedan fuera del cálculo propio porque su flujo no permite la "
            f"unidad de su segmento: {', '.join(sorted(por_motivo))}. Conservan lo que IAMC "
            "publique y no se les reporta una tasa de otra naturaleza."
        ),
        severidad=Severidad.INFO,
        detalle={"cantidad": total, "por_motivo": detalle},
    )


_PORQUE_CRUCE = {
    MOTIVO_MONEDA_CRUZADA: (
        "la especie cotiza en otra moneda que su flujo: descontarla pediría un tipo de cambio, y "
        "el único disponible se deriva de su propia emisión"
    ),
    MOTIVO_SIN_TIPO_TASA: "sin tipo de tasa reconocible no se sabe en qué unidad reportar",
}


def contraste_iamc(divergentes: Sequence[ContrasteMetricas]) -> Alerta:
    """El cálculo propio se separó de lo publicado. **El propio se conserva como dato.**"""
    return Alerta(
        codigo=CODIGO_METRICAS_CONTRASTE_IAMC,
        mensaje=(
            f"{len(divergentes)} emisiones donde la métrica propia difiere de la publicada por "
            f"IAMC más allá de la tolerancia: {_muestra([c.raiz for c in divergentes])}. Se "
            "conserva el cálculo propio."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Contrastar contra el informe del día. Una divergencia grande suele ser un precio "
            "desactualizado en una de las dos puntas, no un error de cálculo."
        ),
        detalle={"cantidad": len(divergentes), "emisiones": [c.como_dict() for c in divergentes]},
    )
