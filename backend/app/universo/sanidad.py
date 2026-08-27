"""Sanidad del dato en dos capas — F-010.

**No es criterio económico: es integridad.** El tope anti-distress que decide el asesor opera dentro
del rango de lo posible; esto descarta lo que directamente no puede ser cierto. Un swap hacia un
ticker que figura rindiendo 34 millones por ciento no es una oportunidad, es un error de datos
disfrazado de oportunidad.

**Capa 1 — coherencia entre especies del mismo bono.** Un bono tiene UNA TIR: sus especies de
liquidación (O/D/C) tienen que declarar la misma, y en la práctica lo hacen (MR46D 13,08 % vs MR46O
13,10 %; PQCTD 55,13 % vs PQCTO 54,81 %). Cuando una especie se despega de las otras por más de
100 pp, lo que está mal es el precio de esa especie: VSCQD figuraba con 34.627.917 % mientras VSCQO,
el mismo bono, rendía 6,75 %. El umbral es de 100 pp y no menos porque hay discordancias legítimas —
DICPD rinde 51 pp más que DICP y son datos válidos.

**Capa 2 — techo de lo posible, por segmento y en la unidad de cada segmento.** Un tope único
cruzaría naturalezas de tasa: 300 % de TNA nominal en pesos y 300 % de TIR en dólares no son la
misma magnitud, así que un solo número descartaría de más en una unidad y de menos en otra. Los
topes son holgados a propósito, porque tienen que dejar pasar el distress real: SNSBO rinde 245,5 %
en dólares y es dato **correcto** —bono a 80 días cotizando al 78 % de su valor técnico, donde la
TIR anualizada explota por el plazo corto— y un umbral ajustado lo mataría junto con la basura.

**Nada se corrige y nada se estima.** El instrumento descartado sigue en el universo para poder
auditarlo; lo que cambia es que no se propone. Y sobre una especie sin rendimiento la sanidad no
opina: un valor ausente no es un valor imposible, y tratarlo como descarte sería confundir "no lo
sé" con "es mentira".

Portado de `tools/segmentos.py:133-279` (`DISCORDANCIA_ESPECIES`, `TOPE_SANIDAD_SEGMENTO` y
`marcar_datos_sanos`), que es lógica ya verificada contra el universo real. Los umbrales **no son
configuración**: son criterio de dominio verificado caso por caso, y hacerlos ajustables por entorno
invitaría a subirlos cuando descarten algo molesto — que es exactamente cuando hay que mirarlos.
"""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.ingesta.alertas import Alerta, especie_incoherente, rendimiento_fuera_de_rango
from app.universo.segmentacion import (
    NOMBRE_NATURALEZA,
    EspecieUniverso,
)

# 100 pp. Ver el docstring del módulo: por qué 100 y no menos.
DISCORDANCIA_ESPECIES = 1.0

# El techo de cada segmento, EN LA UNIDAD DE ESE SEGMENTO. Cambiar cualquiera de estos números sin
# el caso real que lo justifique es lo mismo que borrar la verificación que los puso acá.
TOPE_SANIDAD_SEGMENTO: dict[str, float] = {
    "usd_hard": 3.0,  # TIR en USD
    "dollar_linked": 3.0,  # rendimiento dólar linked
    "cer": 1.0,  # tasa REAL sobre CER
    # TIR efectiva anual en pesos. Fue letra muerta hasta el 26/08/2026 —el rendimiento del segmento
    # salía de la columna `tna`, que nunca tuvo fuente, así que la capa 2 nunca tenía qué evaluar—.
    # Desde que `tasa_fija` declara su TIR, el tope evalúa de verdad. Se mantiene en 5.0: una TIR EA
    # en pesos y una TNA en pesos no son la misma magnitud, pero el techo de lo posible en pesos es
    # el mismo orden y bajarlo sin un caso real que lo justifique sería inventar un descarte.
    "tasa_fija": 5.0,
    "badlar": 5.0,  # TNA nominal en pesos
    "tamar": 5.0,  # TNA nominal en pesos
}


class MotivoDescarte(StrEnum):
    """Por qué un instrumento no se propone. Cada valor es una de las dos capas."""

    ESPECIE_INCOHERENTE = "especie_incoherente"
    """Se despegó de las otras especies del mismo bono: su precio está mal escalado en la fuente."""

    FUERA_DE_RANGO = "rendimiento_fuera_de_rango"
    """Superó el techo de lo posible de su segmento, medido en la unidad de ese segmento."""


@dataclass(frozen=True, slots=True)
class Descarte:
    """Un instrumento que no se propone, con el número exacto que lo disparó.

    Lleva `naturaleza` además de `segmento` porque sin la unidad el valor no se puede leer: 4,8 es
    un descarte en CER y un instrumento sano en tasa fija, y quien audite el listado tiene que poder
    ver contra qué se comparó sin ir a buscar la tabla de topes.
    """

    ticker: str
    motivo: MotivoDescarte
    rendimiento: float
    """El valor declarado que disparó el descarte, en fracción (0,0675 = 6,75 %)."""

    segmento: str
    naturaleza: str
    umbral: float
    """Contra qué se comparó: el techo del segmento, o los 100 pp de despegue entre especies."""

    ticker_referencia: str | None = None
    """La especie hermana que fija el rendimiento verdadero de la emisión. Sólo en la capa 1."""

    rendimiento_referencia: float | None = None

    def como_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "motivo": self.motivo.value,
            "rendimiento": self.rendimiento,
            "segmento": self.segmento,
            "naturaleza": self.naturaleza,
            "naturaleza_nombre": NOMBRE_NATURALEZA[self.naturaleza],
            "umbral": self.umbral,
            "ticker_referencia": self.ticker_referencia,
            "rendimiento_referencia": self.rendimiento_referencia,
        }


@dataclass(frozen=True, slots=True)
class Sanidad:
    """El veredicto sobre un universo: qué se descarta, por qué capa y qué hay que avisar."""

    descartes: list[Descarte] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)
    evaluados: int = 0
    """Especies que pasaron por las dos capas, tengan rendimiento o no."""

    @property
    def descartados(self) -> frozenset[str]:
        return frozenset(d.ticker for d in self.descartes)

    def es_sano(self, ticker: str) -> bool:
        """Si el instrumento se puede proponer. Una especie sin rendimiento es sana: la sanidad no
        opina sobre lo que la fuente no publicó — de eso se ocupa el filtro de operables."""
        return ticker not in self.descartados

    def por_motivo(self, motivo: MotivoDescarte) -> list[Descarte]:
        return [d for d in self.descartes if d.motivo is motivo]


def evaluar_sanidad(especies: Sequence[EspecieUniverso]) -> Sanidad:
    """Corre las dos capas sobre el universo segmentado y devuelve los descartes con su motivo.

    Las capas se aplican en orden y **un instrumento se lista una sola vez**: cuando una especie ya
    se descartó por incoherencia, su valor absurdo va a violar además cualquier techo, y contarla en
    las dos capas duplicaría el mismo problema haciendo creer que hay dos. La capa 1 tiene prioridad
    porque explica mejor qué pasó — nombra la especie hermana que sí tiene el precio bien.
    """
    incoherentes = _capa_coherencia_entre_especies(especies)
    ya_descartados = {d.ticker for d in incoherentes}
    fuera_de_rango = [
        d for d in _capa_techo_por_segmento(especies) if d.ticker not in ya_descartados
    ]

    descartes = sorted(incoherentes + fuera_de_rango, key=lambda d: d.ticker)
    alertas: list[Alerta] = []
    if incoherentes:
        alertas.append(
            especie_incoherente(
                cantidad=len(incoherentes),
                tickers=[d.ticker for d in incoherentes],
                umbral=DISCORDANCIA_ESPECIES,
            )
        )
    if fuera_de_rango:
        alertas.append(
            rendimiento_fuera_de_rango(
                cantidad=len(fuera_de_rango),
                tickers=[d.ticker for d in fuera_de_rango],
                topes=dict(TOPE_SANIDAD_SEGMENTO),
            )
        )

    return Sanidad(descartes=descartes, alertas=alertas, evaluados=len(especies))


def _capa_coherencia_entre_especies(
    especies: Sequence[EspecieUniverso],
) -> list[Descarte]:
    """Capa 1: dentro de cada emisión, lo que se despega hacia arriba del piso por más de 100 pp.

    El piso es la especie de menor rendimiento de la emisión y no el promedio: un valor de 34
    millones por ciento arrastraría cualquier promedio y dejaría de detectarse a sí mismo. Y se mira
    sólo hacia arriba porque el error que esto ataca —un precio mal escalado— siempre infla la TIR:
    una especie que rinde de menos que sus hermanas está diciendo que cotiza más cara, que es un
    dato posible y no un error de escala.

    Una emisión con una sola especie con rendimiento no se evalúa: sin contra qué compararla, no hay
    nada que decir de ella. Ése es el trabajo de la capa 2.
    """
    # Se guarda el rendimiento junto a la especie, ya sabido no nulo, para no tener que volver a
    # descartar el `None` dentro del bucle que compara.
    por_raiz: dict[str, list[tuple[EspecieUniverso, float]]] = defaultdict(list)
    for especie in especies:
        if especie.rendimiento is not None:
            por_raiz[especie.raiz].append((especie, especie.rendimiento))

    descartes: list[Descarte] = []
    for hermanas in por_raiz.values():
        if len(hermanas) < 2:
            continue
        piso, rendimiento_piso = min(hermanas, key=lambda par: par[1])
        for especie, rendimiento in hermanas:
            if rendimiento - rendimiento_piso > DISCORDANCIA_ESPECIES:
                descartes.append(
                    Descarte(
                        ticker=especie.ticker,
                        motivo=MotivoDescarte.ESPECIE_INCOHERENTE,
                        rendimiento=rendimiento,
                        segmento=especie.segmento,
                        naturaleza=especie.naturaleza,
                        umbral=DISCORDANCIA_ESPECIES,
                        ticker_referencia=piso.ticker,
                        rendimiento_referencia=rendimiento_piso,
                    )
                )
    return sorted(descartes, key=lambda d: d.ticker)


def _capa_techo_por_segmento(especies: Sequence[EspecieUniverso]) -> list[Descarte]:
    """Capa 2: el rendimiento contra el techo de SU segmento, en la unidad de ese segmento.

    El tope sale de `TOPE_SANIDAD_SEGMENTO[especie.segmento]` y no de una constante única: es lo que
    hace que un CER al 150 % de tasa real se descarte contra 100 % mientras un tasa fija al 480 % de
    TNA nominal se conserve contra 500 %. Los dos números serían indistinguibles bajo un tope común.

    La condición se escribe en positivo —"descartar lo que supera el techo"— y no como la negación
    de "conservar lo que no lo supera". Con la negación, cualquier valor que no se pueda comparar
    caería del lado del descarte, que es exactamente al revés de la regla: lo que no se sabe no se
    inventa ni se condena.
    """
    descartes: list[Descarte] = []
    for especie in especies:
        tope = TOPE_SANIDAD_SEGMENTO.get(especie.segmento)
        if especie.rendimiento is None or tope is None or not especie.rendimiento > tope:
            continue
        descartes.append(
            Descarte(
                ticker=especie.ticker,
                motivo=MotivoDescarte.FUERA_DE_RANGO,
                rendimiento=especie.rendimiento,
                segmento=especie.segmento,
                naturaleza=especie.naturaleza,
                umbral=tope,
            )
        )
    return sorted(descartes, key=lambda d: d.ticker)
