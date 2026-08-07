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
from datetime import date, datetime
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

    Es el tipo sobre el que trabaja todo el paquete. F-011 le sumó lo que decide el representante de
    una emisión —la duración y los cuatro campos cuya presencia mide la completitud del dato— y
    F-012 le sumó lo que hace falta para derivar el tipo de cambio y comparar liquidez: el precio,
    el volumen, la moneda en la que están los dos y el volumen ya llevado a dólares. Ninguna de las
    dos tocó lo que ya estaba.

    **La división entre lo que es de la emisión y lo que es de la especie no es decorativa.**
    Vencimiento, ley, moneda de pago y emisor son atributos de la emisión: las tres especies de
    liquidación del mismo bono los comparten, y por eso sirven para elegir cuál de ellas la
    representa. El precio, la punta y el volumen son de cada especie y nunca se cruzan entre
    hermanas.
    """

    ticker: str
    raiz: str
    """La emisión a la que pertenece: AL30, AL30D y AL30C comparten `AL30`."""

    clase_activo: str
    segmento: str
    rendimiento: float | None
    """`None` cuando la fuente no publicó el número. No se estima: la sanidad no opina sobre lo
    que no existe, y el armador no propone lo que no tiene rendimiento."""

    duracion: float | None = None
    """`duration` de la vista. Es de la emisión, no de la especie: el mismo bono liquidado en pesos
    o en dólares tiene la misma duración, y ése es justamente el chequeo que decide si un grupo de
    especies es de verdad una sola emisión (F-011)."""

    vencimiento: date | None = None
    ley: str | None = None
    moneda_cupon: str | None = None
    emisor: str | None = None
    """El nombre del emisor tal como lo publica la fuente (columna `underlying` de la vista)."""

    precio: float | None = None
    """`lastPrice`, en la moneda de cotización de esta especie. Es la punta del cociente del que
    F-012 deriva el tipo de cambio: el precio en pesos sobre el precio en dólares del mismo bono."""

    volumen: float | None = None
    """`effectiveVolume`: monto operado, en la moneda de cotización de esta especie. **Crudo no es
    comparable entre hermanas** —la especie en pesos muestra ~1.500 veces más por el tipo de cambio
    y no por operarse más—, y por eso quien compare liquidez usa `volumen_usd`."""

    moneda_cotizacion: str | None = None
    """`denominationCcy` tal como lo declara BYMA: `ARS`, `USD` o `EXT`, sin traducir. Es lo que
    dice en qué unidad están `precio` y `volumen`. Se lee y no se deduce del sufijo del ticker: hay
    seis especies con sufijo D declaradas en pesos, y sus precios lo confirman."""

    volumen_usd: float | None = None
    """El volumen llevado a dólares por F-012, que es la única forma de comparar liquidez entre
    especies de distinta moneda. `None` cuando no se pudo: sin tipo de cambio del día, o sin saber
    en qué moneda estaba el número. Un faltante acá no se rellena con el volumen crudo."""

    paridad: float | None = None
    """`paridad` de la vista, para F-038: el monitor la muestra tal como la publica la fuente.
    `None` cuando la vista trae `NULL` — no se calcula ni se estima acá."""

    @property
    def naturaleza(self) -> str:
        return NATURALEZA_TASA[self.segmento]

    @property
    def sufijo_liquidacion(self) -> str | None:
        """Lo que separa a esta especie de sus hermanas: la letra que `raiz_emision` le cortó.

        `None` cuando el ticker ya es la raíz. Es un hecho del ticker, no una interpretación: acá
        no se dice qué moneda significa cada letra, porque establecer que la D es MEP y la C es
        Cable —y que los separa el canje— es de F-012, que es donde vive el tipo de cambio.
        """
        return self.ticker[len(self.raiz) :] or None

    def como_dict(self) -> dict[str, object]:
        """La especie como viaja por el API, con su clave de emisión siempre explícita.

        La clave va en **las dos vistas**, colapsada y viva: quien mira la vista viva tiene que
        poder ver que MR46O y MR46D son el mismo bono sin volver a cortar el ticker por su cuenta.
        """
        return {
            "ticker": self.ticker,
            "emision": self.raiz,
            "sufijo_liquidacion": self.sufijo_liquidacion,
            "clase_activo": self.clase_activo,
            "segmento": self.segmento,
            "naturaleza": self.naturaleza,
            "naturaleza_nombre": NOMBRE_NATURALEZA[self.naturaleza],
            "rendimiento": self.rendimiento,
            "duracion": self.duracion,
            "vencimiento": self.vencimiento.isoformat() if self.vencimiento else None,
            "ley": self.ley,
            "moneda_cupon": self.moneda_cupon,
            "emisor": self.emisor,
            "precio": self.precio,
            "moneda_cotizacion": self.moneda_cotizacion,
            "volumen": self.volumen,
            "volumen_usd": self.volumen_usd,
            "paridad": self.paridad,
        }


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
                    segmento, a_numero(fila.get("tir")), a_numero(fila.get("tna"))
                ),
                duracion=a_numero(fila.get("duration")),
                vencimiento=_fecha(fila.get("maturity")),
                ley=_texto(fila.get("law")),
                moneda_cupon=_texto(fila.get("couponCurrency")),
                emisor=_texto(fila.get("underlying")),
                precio=a_numero(fila.get("lastPrice")),
                volumen=a_numero(fila.get("effectiveVolume")),
                moneda_cotizacion=_texto(fila.get("moneda_cotizacion")),
                paridad=a_numero(fila.get("paridad")),
            )
        )

    return Segmentacion(especies=especies, renta_variable=renta_variable, sin_segmento=sin_segmento)


def a_numero(valor: object) -> float | None:
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


def _texto(valor: object) -> str | None:
    """Un texto de la fuente, o `None` si no hay ninguno.

    Lo único que se hace es recortar espacios y tratar la cadena vacía como faltante. **No se
    normaliza el contenido**: traducir un código de la fuente a una categoría "equivalente" es
    exactamente el error que una vez inventó una ley que no existe. Lo que la fuente dice, se
    guarda; lo que no dice, queda vacío.

    Un `NaN` de pandas llega acá como `float` y sale como `None`, igual que en `numero`: es su
    forma de decir que la celda estaba vacía, no un valor.
    """
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None


def _fecha(valor: object) -> date | None:
    """El vencimiento como fecha, o `None`.

    Acepta lo que devuelven las dos fuentes que alimentan esto: un `date` de asyncpg y un
    `Timestamp` de pandas —que es un `datetime` y por eso entra por la misma puerta— más la cadena
    ISO, que es la única forma de texto que se interpreta. **Un `10/03/2030` no se parsea**: sin
    saber si el 10 es el día o el mes habría que elegir, y elegir sería inventar una fecha de
    vencimiento, que es de las peores cosas que se pueden inventar sobre un bono.

    `NaT` de pandas es un `datetime` y no se puede distinguir por tipo: se lo detecta por ser el
    único valor que no es igual a sí mismo.
    """
    if valor is None or valor != valor:  # `None`, `NaN` o `NaT`
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return date.fromisoformat(valor[:10])
        except ValueError:
            return None
    return None
