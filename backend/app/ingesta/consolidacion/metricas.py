"""Qué especie tiene métricas propias y cuál no, cada una con su motivo nombrado — F-051.

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

Esas especies quedan **sin métrica y con el motivo declarado**. Hasta el 26/08/2026 conservaban lo
que IAMC publicara; desde que se eliminó esa ingesta no hay nada que conservar, y la celda vacía con
su porqué es la única respuesta honesta.

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

## Dos destinos, no tres (26/08/2026)

Mientras IAMC existió, `fuente_de_metricas` tenía un tercer destino —`FUENTE_IAMC`— para las
especies sin `tipo_tasa` y para las naturalezas que no figuran en `MONEDAS_DEL_FLUJO`. Ese destino
tapaba un agujero: `armado.py` las devolvía `None` **sin anotar motivo**, así que ~535 especies
desaparecían del cálculo sin nombre y sin alerta (medición SQL en `docs/ESTADO.md`). Era razonable
mientras había una fuente publicando por ellas; sin esa fuente pasó a ser un faltante silencioso,
que es justo lo que la regla 1 prohíbe.

Ahora hay dos destinos y nada más: se calcula, o queda fuera con su motivo. Una naturaleza de tasa
que no tenga regla de cálculo declarada cae en `naturaleza_desconocida` y entra a la alerta con
nombre y apellido, en vez de irse en silencio esperando que otro la llene.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.calendario.metricas import MetricasEspecie
from app.ingesta.alertas import Alerta, Severidad

# Cuántos tickers se nombran en el cuerpo de una alerta antes de cortar. El detalle lleva la lista
# entera; el mensaje tiene que poder leerse. Mismo criterio que `universo/cambio.py`.
MUESTRA_ALERTA = 6

# Qué moneda de cotización hace comparable el precio con el flujo, por tipo de tasa. `EXT`
# —vocabulario propio de BYMA, sin documentar por la fuente— quedó fuera desde el 08/08/2026
# (regla 11) porque nada confirmaba qué denota. Dejó de ser un supuesto del código el 30/08/2026:
# el dueño del producto confirmó que `EXT` es liquidación cable y `USD` es liquidación MEP, ambas
# dólares — la misma distinción que ya usa renta variable con el sufijo del ticker (`D`=MEP,
# `C`=cable). Con la fuente puesta (la confirmación queda en CLAUDE.md, sección de reglas de
# dominio), cable deja de ser un código sin traducir para pasar a ser dólares confirmados, y por
# eso entra a `MONEDAS_DEL_FLUJO` igual que `USD`: cada especie sigue calculando con **su propio
# precio** —una fila `EXT` nunca usa el precio de su hermana `USD`, eso seguiría siendo copiarle la
# métrica, que es lo que prohíbe la regla 1—, sólo que ahora la fila `EXT` deja de descartarse antes
# de intentarlo. `tasa-fija` no suma `EXT` porque esa naturaleza paga en pesos: no hay bono
# tasa-fija que cotice en dólares, cable o MEP, así que el caso no existe.
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
FUENTE_FUERA = "fuera"

MOTIVO_MONEDA_CRUZADA = "moneda_cruzada"
MOTIVO_NATURALEZA_DESCONOCIDA = "naturaleza_desconocida"
MOTIVO_SIN_PRECIO = "sin_precio"
MOTIVO_SIN_CRONOGRAMA = "sin_cronograma"
MOTIVO_SIN_TIPO_TASA = "sin_tipo_de_tasa"

# `MOTIVO_RESIDUAL_CONTRADICTORIO` vivió acá hasta el 26/08/2026 y se mudó a
# `app.calendario.metricas`. El motivo del traslado: desde esa fecha `metricas_de` también lo
# emite —antes ese caso salía rotulado `vencida`, que era falso—, y este módulo importa de aquél,
# así que la constante tiene que estar del lado que no importa a nadie. Quien la necesite la trae
# de `app.calendario.metricas`. Sigue cayendo en el balde "sin insumo" (no está en
# `NATURALEZAS_FUERA_O_CRUCE`): es un faltante del dato de hoy, no una decisión de diseño.

CODIGO_METRICAS_SIN_INSUMO = "metricas_propias_sin_insumo"
CODIGO_METRICAS_FUERA_DE_NATURALEZA = "metricas_fuera_de_naturaleza"


def fuente_de_metricas(tipo_tasa: str | None, moneda_cotizacion: str | None) -> str:
    """De dónde salen `tir`, `duration` y `paridad` para esta especie: se calculan, o no hay.

    `FUENTE_CALCULO` si el flujo y el precio comparten moneda; `FUENTE_FUERA` en todo el resto —
    sin tipo de tasa, con una naturaleza que no se puede calcular contra el flujo disponible, con
    una naturaleza que no tiene regla declarada, o con monedas que no coinciden—. Cada uno de esos
    cuatro caminos tiene su motivo en `motivo_de_exclusion`, y ninguno sale sin nombrarlo.
    """
    if tipo_tasa is None:
        return FUENTE_FUERA
    if tipo_tasa in NATURALEZAS_FUERA:
        return FUENTE_FUERA
    if tipo_tasa not in MONEDAS_DEL_FLUJO:
        return FUENTE_FUERA
    monedas = MONEDAS_DEL_FLUJO[tipo_tasa]
    if moneda_cotizacion is None or moneda_cotizacion not in monedas:
        return FUENTE_FUERA
    return FUENTE_CALCULO


def motivo_de_exclusion(tipo_tasa: str | None, moneda_cotizacion: str | None) -> str:
    """Por qué esta especie quedó fuera del cálculo. Sólo se llama cuando la fuente es `fuera`."""
    if tipo_tasa is None:
        return MOTIVO_SIN_TIPO_TASA
    if tipo_tasa in NATURALEZAS_FUERA:
        return tipo_tasa
    if tipo_tasa not in MONEDAS_DEL_FLUJO:
        return MOTIVO_NATURALEZA_DESCONOCIDA
    del moneda_cotizacion  # la única razón que queda es que no coincida con la del flujo
    return MOTIVO_MONEDA_CRUZADA


@dataclass
class ResultadoMetricas:
    """Qué se calculó en una corrida, y qué quedó afuera con qué motivo."""

    calculadas: int = 0
    """Las que **produjeron** un rendimiento. Hasta el 26/08/2026 este contador se incrementaba en
    cada `registrar()`, así que sumaba también las que volvían con `tir=None` por bracket o por
    vencimiento: el número que la corrida publicaba como "cuántas se calcularon" venía inflado por
    los fallos, que son justo lo que hay que poder ver."""

    intentadas: int = 0
    """Las que entraron al solver, hayan resuelto o no. Es el denominador de `calculadas` y por eso
    se sigue reportando: sin él, una caída de calculadas no distingue "entraron menos especies" de
    "entraron las mismas y fallaron más"."""

    por_motivo: dict[str, list[str]] = field(default_factory=dict)

    def registrar(self, ticker: str, metricas: MetricasEspecie) -> None:
        self.intentadas += 1
        if metricas.tir is not None:
            self.calculadas += 1
        if metricas.motivo is not None:
            self.anotar(metricas.motivo, ticker)

    def anotar(self, motivo: str, ticker: str) -> None:
        self.por_motivo.setdefault(motivo, []).append(ticker)

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
        return alertas

    def resumen(self) -> dict[str, object]:
        return {
            "calculadas": self.calculadas,
            "intentadas": self.intentadas,
            "sin_metrica": {motivo: len(t) for motivo, t in sorted(self.por_motivo.items())},
        }


# Los motivos que son "esta especie no entra al cálculo" y no "el insumo no alcanzó". Se separan
# porque piden acciones distintas: uno es una decisión de diseño declarada, el otro es un faltante
# del día que puede resolverse mañana.
NATURALEZAS_FUERA_O_CRUCE = frozenset(NATURALEZAS_FUERA) | {
    MOTIVO_MONEDA_CRUZADA,
    MOTIVO_SIN_TIPO_TASA,
    MOTIVO_NATURALEZA_DESCONOCIDA,
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
            f"unidad de su segmento: {', '.join(sorted(por_motivo))}. Quedan sin métrica, cada "
            "una declarada con su motivo, y no se les reporta una tasa de otra naturaleza."
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
    MOTIVO_NATURALEZA_DESCONOCIDA: (
        "naturaleza de tasa sin regla de cálculo declarada: no se sabe en qué unidad reportar el "
        "rendimiento, y elegir una sería inventarla"
    ),
}

