"""Con quién es comparable cada especie, y en qué unidad está el número que la mide.

Portado de `tools/segmentos.py` (`asignar_segmento` y los diccionarios que lo acompañan). El backend
no importa de `tools/`, así que la lógica se copia con su razón de ser y las dos tienen que seguir
coincidiendo, igual que pasa con `raiz_emision`: si divergen, el backend y el motor dejan de hablar
del mismo universo.

**Los segmentos se clasifican sólo por tipo de tasa.** La clase de activo —soberano, subsoberano,
ON— es riesgo de crédito, no naturaleza de tasa, y por lo tanto no define con quién es comparable un
instrumento. Un Tamar provincial y un Tamar corporativo se miden con la misma vara; que uno sea más
riesgoso que el otro se resuelve después, en los límites de concentración y en las notas de riesgo.

**`NATURALEZA_TASA` es lo que impide cruzar unidades por descuido.** Una TIR en dólares, una tasa
real sobre CER y una TNA nominal en pesos son magnitudes distintas y no comparten eje. El tope de
sanidad de F-010 se elige por segmento justamente porque el segmento es lo que determina la unidad
del número que se está comparando.

La renta variable sale del universo **antes** de segmentar y no por "no tener segmento": una acción
no tiene TIR, ni duración, ni cronograma, así que nunca fue comparable con un bono. Si se la dejara
caer por el camino de "sin segmento", la alerta diría 750+ instrumentos en todas las corridas y
taparía el caso que esa alerta existe para mostrar — un bono cuyo tipo de tasa no se reconoció.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from math import isnan

from app.ingesta.consolidacion import raiz_emision

# Clases del universo que no son renta fija: sin TIR, sin duración y sin cashflow.
CLASES_RENTA_VARIABLE = ("accion", "cedear")

# Tipos de tasa que caen en el mismo segmento comparable. `bopreal` va con hard-dollar porque cobra
# en dólares como cualquier global: el emisor es otro, la naturaleza de la tasa es la misma.
SEGMENTO_POR_TIPO_TASA: dict[str, str] = {
    "hard-dollar": "usd_hard",
    "bopreal": "usd_hard",
    "cer": "cer",
    "tasa-fija": "tasa_fija",
    "dollar-linked": "dollar_linked",
    "badlar": "badlar",
    "tamar": "tamar",
}

# En qué moneda cobra el inversor. Dólar linked paga en pesos aunque siga al dólar: la distinción
# importa para valuar, no para comparar rendimientos.
MONEDA_SEGMENTO: dict[str, str] = {
    "usd_hard": "usd",
    "dollar_linked": "ars",
    "cer": "ars",
    "tasa_fija": "ars",
    "badlar": "ars",
    "tamar": "ars",
}

# La unidad del rendimiento de cada segmento. Dos segmentos con la misma naturaleza son promediables
# entre sí; dos con naturaleza distinta, nunca.
NATURALEZA_TASA: dict[str, str] = {
    "usd_hard": "tir_usd",
    "dollar_linked": "tir_dolar_linked",
    "cer": "tasa_real_cer",
    "tasa_fija": "tna_nominal_ars",
    "badlar": "tna_nominal_ars",
    "tamar": "tna_nominal_ars",
}

NOMBRE_NATURALEZA: dict[str, str] = {
    "tir_usd": "TIR en dólares (hard dollar)",
    "tir_dolar_linked": "Rendimiento dólar linked",
    "tasa_real_cer": "Tasa real sobre CER (por encima de inflación)",
    "tna_nominal_ars": "TNA nominal en pesos",
}

DESC_SEGMENTO: dict[str, str] = {
    "usd_hard": "Hard dollar (globales, bonares, ONs y bopreales en USD)",
    "dollar_linked": "Dólar linked (pesos ajustados por tipo de cambio)",
    "cer": "CER (pesos ajustados por inflación)",
    "tasa_fija": "Tasa fija en pesos (LECAP/BONCAP y ONs)",
    "badlar": "Badlar (pesos, tasa variable)",
    "tamar": "Tamar (pesos, tasa variable)",
}

# El único segmento que no cotiza por TIR. Una LECAP se negocia por TNA y su TIR, cuando existe, no
# es el número con el que el mercado la mira.
SEGMENTO_POR_TNA = "tasa_fija"


def asignar_segmento(tipo_tasa: str | None) -> str | None:
    """El segmento comparable de una especie, o `None` si su tipo de tasa no se reconoce.

    Devolver `None` en vez de un segmento por defecto es deliberado: un bono cuyo tipo de tasa no
    entró al mapa no es "de tasa fija hasta que se demuestre lo contrario", es un bono que todavía
    no se sabe con quién comparar, y meterlo en un segmento cualquiera lo haría comparable contra
    una vara que no es la suya.
    """
    return SEGMENTO_POR_TIPO_TASA.get(tipo_tasa) if tipo_tasa else None


def rendimiento_declarado(segmento: str, tir: float | None, tna: float | None) -> float | None:
    """El número con el que se mide una especie, en la unidad de su segmento.

    TIR para todo, salvo tasa fija, que cotiza por TNA. No hay conversión entre las dos ni relleno
    de una con la otra: son unidades distintas y elegir la que esté cargada sería inventar el dato.
    """
    return tna if segmento == SEGMENTO_POR_TNA else tir


@dataclass(frozen=True, slots=True)
class EspecieUniverso:
    """Una especie del universo, ya segmentada y con su rendimiento en la unidad que le corresponde.

    Es el tipo sobre el que trabaja todo el paquete. F-011 le va a agregar lo que necesita para
    decidir el representante de una emisión (duración, completitud, volumen) y F-012 lo que necesita
    para derivar el tipo de cambio (precio y moneda de cotización); ninguna de las dos tiene que
    tocar lo que ya está acá.
    """

    ticker: str
    raiz: str
    """La emisión a la que pertenece: AL30, AL30D y AL30C comparten `AL30`."""

    clase_activo: str
    segmento: str
    rendimiento: float | None
    """`None` cuando la fuente no publicó el número. No se estima: la sanidad no opina sobre lo
    que no existe, y el armador no propone lo que no tiene rendimiento."""

    @property
    def naturaleza(self) -> str:
        return NATURALEZA_TASA[self.segmento]


@dataclass(frozen=True, slots=True)
class Segmentacion:
    """El universo repartido en tres: lo comparable, lo que nunca lo fue y lo que no se supo."""

    especies: list[EspecieUniverso]
    renta_variable: int
    """Acciones y CEDEARs. Salen antes de segmentar y no son un problema: no tienen tasa."""

    sin_segmento: list[str]
    """Renta fija cuyo tipo de tasa no se reconoce. Esto sí es un problema y por eso se lista."""


def segmentar(filas: Iterable[Mapping[str, object]]) -> Segmentacion:
    """Segmenta las filas de la vista `resumen` y separa lo que no entra al universo comparable.

    Recibe mappings y no un tipo propio para que el mismo código sirva sobre los `Record` de asyncpg
    y sobre los diccionarios de un test, que es lo que permite probar toda la sanidad sin Postgres.
    """
    especies: list[EspecieUniverso] = []
    renta_variable = 0
    sin_segmento: list[str] = []

    for fila in filas:
        clase = str(fila["clase_activo"])
        if clase in CLASES_RENTA_VARIABLE:
            renta_variable += 1
            continue

        ticker = str(fila["ticker"])
        tipo_tasa = fila.get("tipo_tasa")
        segmento = asignar_segmento(str(tipo_tasa) if tipo_tasa else None)
        if segmento is None:
            sin_segmento.append(ticker)
            continue

        especies.append(
            EspecieUniverso(
                ticker=ticker,
                raiz=raiz_emision(ticker),
                clase_activo=clase,
                segmento=segmento,
                rendimiento=rendimiento_declarado(
                    segmento, _numero(fila.get("tir")), _numero(fila.get("tna"))
                ),
            )
        )

    return Segmentacion(especies=especies, renta_variable=renta_variable, sin_segmento=sin_segmento)


def _numero(valor: object) -> float | None:
    """`Decimal` de asyncpg, `float` de un test o `None`. Un valor que no es número es `None`.

    No se intenta interpretar un string ni completar un faltante: si la fuente no publicó un número,
    el rendimiento queda vacío y el instrumento no se propone.

    **`NaN` cuenta como faltante y por eso se traduce a `None`.** asyncpg nunca lo devuelve, pero
    pandas sí —es su forma de decir "esta celda estaba vacía"— y cualquiera que alimente esto desde
    un Excel lo trae. Dejarlo pasar como número es peligroso de un modo silencioso: `nan <= tope` es
    `False`, así que un faltante se leería como una violación del techo y el sistema descartaría por
    roto lo que simplemente no se sabe. Verificado: sobre el consolidado histórico eran 366 falsos
    descartes contra los 2 que marca el motor.
    """
    if isinstance(valor, bool) or valor is None:
        return None
    if isinstance(valor, int | float):
        numero = float(valor)
    else:
        try:
            numero = float(valor)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
    return None if isnan(numero) else numero
