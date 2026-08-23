"""Resolver un ticker declarado contra el universo, y no hacer nada más que eso — F-029.

Esta feature existe por un error concreto: derivar 121 tickers inexistentes cortando strings, que
hubo que revertir. Así que lo que define al módulo no es lo que hace sino lo que **no** hace.

**No hay acá ninguna función que reciba un ticker y devuelva otro.** Ni fuzzy matching, ni distancia
de edición, ni "el más parecido", ni manipulación de sufijos. Si el asesor escribió `RUCEX` y en el
universo está `RUCEO`, `RUCEX` queda no reconocido. Verificado contra la base: `RUCEX` existe como
ON pero sin tipo de tasa reconocido, así que ni siquiera hace falta inventarlo para que quede
afuera — y si no existiera, tampoco se inventaría.

Lo único que se toca del ticker declarado es el espacio de más y la caja: `  al30 ` busca `AL30`.
Eso no es derivar un ticker de otro, es leer el mismo ticker escrito a mano; el declarado viaja
igual, entero, al lado del resuelto, para que cualquier diferencia se vea.

**La posición que no resuelve no se descarta.** Queda en la cartera, con su monto, marcada y con el
motivo. Descartarla en silencio haría que la cartera parezca más chica y más resuelta de lo que es.

## El porcentaje sin resolver y las posiciones sin monto

`PosicionCruda` (F-028) trae `nominal` y `monto` como casilleros independientes, y **cualquiera de
los dos puede venir vacío**: un resumen de cuenta puede declarar sólo la tenencia nominal. Una
posición sin monto no tiene valuación declarada, y valorizarla requiere un precio que —si el ticker
no resolvió— directamente no existe.

La decisión, y su porqué:

- **El porcentaje se calcula sólo sobre las posiciones que declaran monto.** Es la única base que
  existe sin inventar nada.
- **Una posición sin monto no cuenta como cero.** Meterla en el denominador con monto cero no
  cambiaría el denominador pero sí el mensaje: haría creer que se la tuvo en cuenta. Meterla como
  cero en el numerador cuando además no resolvió sería peor todavía — diría que la parte no
  resuelta de la cartera es más chica de lo que se sabe. Un faltante no es un cero.
- **La respuesta declara sobre qué base se calculó.** `posiciones_con_monto` y
  `posiciones_sin_monto` viajan siempre, y cuando hay alguna sin monto sale una alerta que lo
  dice con el número. Un porcentaje sin su base se lee como si fuera de toda la cartera.
- **Sin ninguna posición con monto, el porcentaje es `None`, no cero.** No poder calcularlo es un
  estado distinto de que dé cero, y la cantidad de posiciones sin resolver —que no depende del
  monto— sigue siendo exacta igual.

**Lo que queda declarado y sin resolver: la moneda de esos montos.** `PosicionCruda` trae un número
y no dice en qué moneda está — F-028 lee lo que el resumen de cuenta escribió y el resumen no
declara la moneda columna por columna. Sumarlos asume que están todos en la misma unidad, y por la
regla 3 del proyecto eso no se puede dar por sentado. Se calcula igual porque es lo que la feature
pide y porque numerador y denominador salen de la misma columna, pero **el número sólo significa
algo si el resumen vino en una sola moneda**. Resolverlo de verdad es valorizar cada posición a su
precio, que es F-030: recién ahí hay una moneda por especie con la que normalizar.

## El plazo de liquidación no sale del sufijo del ticker

El sufijo O / D / C es la **moneda de liquidación** (pesos, MEP, cable): es lo que `raiz_emision`
corta para agrupar las especies del mismo bono, y no dice nada del plazo. El plazo es otro eje y es
un dato leído: `settlementType` de BYMA, que F-004 guarda en `instrumentos.plazo_liquidacion` tal
cual viene, `"1"` o `"2"`.

**Y se sigue sin traducir acá.** Ninguna fuente del proyecto publica qué plazo es cada código —el
único lugar que lo menciona dice "contado inmediato o 24 horas" sin decir cuál es cuál— así que
mapearlo a "48hs" sería exactamente el error que una vez inventó una ley que no existe. Viaja el
código, y cuando no está, viaja vacío y se alerta.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum

from app.ingesta.alertas import Alerta, Severidad
from app.universo.segmentacion import EspecieUniverso

# Cuántos tickers se nombran en el cuerpo de una alerta. La lista entera va en el detalle: si son
# veinte, el mensaje se vuelve ilegible y el que audita necesita la lista completa igual.
MUESTRA_ALERTA = 8

# Las clases del universo que no son renta fija. Están acá y no importadas de `segmentacion` porque
# allá son la lista de lo que sale *antes* de segmentar; acá son lo que explica por qué un ticker
# conocido no está entre las especies comparables. Es el mismo hecho leído desde el otro lado.
CLASES_RENTA_VARIABLE = ("accion", "cedear")

CODIGO_POSICIONES_NO_RESUELTAS = "posiciones_no_resueltas"
CODIGO_POSICIONES_SIN_MONTO = "posiciones_sin_monto"
CODIGO_SIN_BASE_PARA_EL_PORCENTAJE = "sin_base_para_el_porcentaje"
CODIGO_PLAZO_NO_DISPONIBLE = "plazo_de_liquidacion_no_disponible"
CODIGO_POSICION_CON_DATO_NO_SANO = "posicion_con_dato_no_sano"


class MotivoNoResuelta(StrEnum):
    """Por qué un ticker declarado no quedó vinculado a una especie.

    Los cuatro motivos son hechos leídos de la base, no interpretaciones. En particular, distinguir
    "no existe" de "existe pero no es comparable" importa: contestarle a un asesor que GGAL no está
    en el universo es falso —está— y lo mandaría a buscar un error de tipeo que no cometió. Lo mismo
    con un FCI: pegado en un resumen de cuenta, un código CAFCI no es un ticker con typo, es otra
    clase de instrumento (F-046).
    """

    NO_ESTA_EN_EL_UNIVERSO = "no_esta_en_el_universo"
    """No aparece en `instrumentos` ni matchea un `codigo_cafci` de `public.fci`. Ni se aproxima al
    más parecido ni se deriva de otro."""

    RENTA_VARIABLE = "renta_variable"
    """Es una acción o un CEDEAR: no tiene TIR, ni duración, ni cronograma de cupones."""

    SIN_TIPO_DE_TASA = "sin_tipo_de_tasa"
    """Es renta fija conocida pero su tipo de tasa no se reconoce, así que no se sabe con quién es
    comparable. Es el mismo `sin_segmento` del universo, visto desde una posición."""

    ES_FCI = "es_fci"
    """El texto pegado matchea, **exacto y nunca por nombre**, un `codigo_cafci` de `public.fci`
    (F-046). No es un ticker del universo de renta fija — es un fondo, y viaja con su ficha resuelta
    en `PosicionResuelta.fondo_fci`."""


DESC_MOTIVO: dict[MotivoNoResuelta, str] = {
    MotivoNoResuelta.NO_ESTA_EN_EL_UNIVERSO: "No está en el universo",
    MotivoNoResuelta.RENTA_VARIABLE: "Renta variable: no es un instrumento de renta fija",
    MotivoNoResuelta.SIN_TIPO_DE_TASA: "Sin tipo de tasa reconocido: no se sabe con quién comparar",
    MotivoNoResuelta.ES_FCI: "Es un fondo común de inversión (FCI), no un instrumento de renta fija",
}


@dataclass(frozen=True, slots=True)
class FilaInstrumento:
    """Lo que se sabe de un ticker por estar en `instrumentos`, aunque no sea comparable."""

    ticker: str
    clase_activo: str | None
    plazo_liquidacion: str | None
    """`settlementType` de BYMA, `"1"` o `"2"`, sin traducir. `None` si la fuente no lo trajo."""


@dataclass(frozen=True, slots=True)
class PosicionDeclarada:
    """Una posición tal como la leyó F-028, antes de resolver el ticker.

    Espeja `PosicionCruda` del frontend salvo `valida` y `motivo`, que son el veredicto de F-028
    sobre el formato de la fila y no entran acá: la resolución no depende de ellos y devolverlos
    haría parecer que este servicio los revisó. Una fila que F-028 marcó inválida llega igual, con
    el casillero que no se pudo leer en `None`, y cae sola en el conteo de posiciones sin monto.
    """

    id: str
    fila: int
    ticker_declarado: str
    nominal: float | None = None
    monto: float | None = None


@dataclass(frozen=True, slots=True)
class FondoFciResuelto:
    """La ficha mínima de un FCI matcheado por `codigo_cafci` exacto — F-046.

    Sale de `app.fci.fondos.FondoFci`, no de acá: `resolucion.py` no lee `public.fci` ni interpreta
    sus columnas, sólo recibe el resultado ya interpretado y lo adjunta a la posición.
    """

    codigo_cafci: str
    fondo: str
    vcp: float | None
    """Por cada mil cuotapartes, tal como CAFCI lo publica — no se divide acá."""
    fecha_vcp: str | None
    moneda: str

    def como_dict(self) -> dict[str, object]:
        return {
            "codigo_cafci": self.codigo_cafci,
            "fondo": self.fondo,
            "vcp": self.vcp,
            "fecha_vcp": self.fecha_vcp,
            "moneda": self.moneda,
        }


@dataclass(frozen=True, slots=True)
class PosicionResuelta:
    """Una posición con su ticker ya buscado. Resuelta o no, sigue adentro de la cartera."""

    declarada: PosicionDeclarada
    especie: EspecieUniverso | None = None
    plazo_liquidacion: str | None = None
    """El plazo de la cotización guardada. `None` es "no se sabe", nunca un plazo por defecto."""

    dato_sano: bool | None = None
    """El veredicto de la sanidad de F-010 sobre esta especie. `None` cuando no resolvió: no se
    puede opinar sobre el dato de un instrumento que no se encontró."""

    motivo: MotivoNoResuelta | None = None
    """Por qué no resolvió. `None` cuando resolvió."""

    clase_activo: str | None = None
    """La clase que declara `instrumentos`. Viaja incluso cuando no resolvió, porque es lo que
    explica el motivo: una acción no es un ticker inexistente."""

    fondo_fci: FondoFciResuelto | None = None
    """La ficha del fondo cuando `motivo is ES_FCI`. `None` en cualquier otro caso — nunca se
    completa por analogía (regla 1)."""

    @property
    def resuelta(self) -> bool:
        return self.especie is not None

    def como_dict(self) -> dict[str, object]:
        """La posición como viaja por el API: lo declarado y lo resuelto, siempre lado a lado.

        El ticker declarado no se pisa con el resuelto en ningún caso. Son dos campos y no uno
        justamente para que se pueda ver que lo que se encontró es lo que se pidió.
        """
        especie = self.especie
        return {
            "id": self.declarada.id,
            "fila": self.declarada.fila,
            "ticker_declarado": self.declarada.ticker_declarado,
            "nominal": self.declarada.nominal,
            "monto": self.declarada.monto,
            "resuelta": self.resuelta,
            "ticker": especie.ticker if especie else None,
            "emision": especie.raiz if especie else None,
            # No se llama `moneda_liquidacion`: lo que viaja es la letra del ticker ("D", "C", "O"),
            # y decirle moneda a una letra es el paso previo a que alguien la muestre como si lo
            # fuera. La moneda declarada va en el campo de al lado (regla 11, 08/08/2026).
            "sufijo_liquidacion": especie.sufijo_liquidacion if especie else None,
            "moneda_cotizacion": especie.moneda_cotizacion if especie else None,
            "plazo_liquidacion": self.plazo_liquidacion,
            "clase_activo": self.clase_activo,
            "segmento": especie.segmento if especie else None,
            "naturaleza": especie.naturaleza if especie else None,
            "dato_sano": self.dato_sano,
            "motivo": self.motivo.value if self.motivo else None,
            "motivo_descripcion": DESC_MOTIVO[self.motivo] if self.motivo else None,
            "fondo_fci": self.fondo_fci.como_dict() if self.fondo_fci else None,
        }


@dataclass(frozen=True, slots=True)
class Cobertura:
    """Cuánto de la cartera quedó sin resolver, en posiciones y en monto, con su base declarada."""

    posiciones: int = 0
    resueltas: int = 0
    no_resueltas: int = 0
    posiciones_con_monto: int = 0
    """Las que entran al cálculo del porcentaje: son las únicas que declaran un monto."""

    posiciones_sin_monto: int = 0
    """Las que quedan afuera de la base. No cuentan como cero: no se sabe cuánto valen."""

    posiciones_sin_monto_no_resueltas: int = 0
    """De las que quedaron afuera de la base, cuántas además no resolvieron. Es el número que dice
    cuánto puede estar subestimando el porcentaje: son las que no se pueden ni valorizar."""

    monto_declarado: float = 0.0
    """La base del porcentaje: la suma de los montos que las posiciones declararon."""

    monto_no_resuelto: float = 0.0

    porcentaje_no_resuelto: float | None = None
    """En puntos porcentuales (18,2 es 18,2 %), sobre `monto_declarado`. `None` cuando no hay base:
    ninguna posición declaró monto, o los declarados suman cero. No calcularlo no es cero."""

    @property
    def hay_posiciones_fuera_de_la_base(self) -> bool:
        return self.posiciones_sin_monto > 0

    def como_dict(self) -> dict[str, object]:
        return {
            "posiciones": self.posiciones,
            "resueltas": self.resueltas,
            "no_resueltas": self.no_resueltas,
            "posiciones_con_monto": self.posiciones_con_monto,
            "posiciones_sin_monto": self.posiciones_sin_monto,
            "posiciones_sin_monto_no_resueltas": self.posiciones_sin_monto_no_resueltas,
            "monto_declarado": self.monto_declarado,
            "monto_no_resuelto": self.monto_no_resuelto,
            "porcentaje_no_resuelto": self.porcentaje_no_resuelto,
        }


@dataclass(frozen=True, slots=True)
class CarteraResuelta:
    """La cartera después de resolver: las posiciones, el diagnóstico y lo que hay que saber."""

    posiciones: list[PosicionResuelta] = field(default_factory=list)
    cobertura: Cobertura = field(default_factory=Cobertura)

    @property
    def no_resueltas(self) -> list[PosicionResuelta]:
        return [p for p in self.posiciones if not p.resuelta]

    @property
    def sin_plazo(self) -> list[PosicionResuelta]:
        """Resueltas cuyo plazo de liquidación no se pudo leer. Vacío no es un plazo por defecto."""
        return [p for p in self.posiciones if p.resuelta and p.plazo_liquidacion is None]

    @property
    def con_dato_no_sano(self) -> list[PosicionResuelta]:
        return [p for p in self.posiciones if p.dato_sano is False]

    @property
    def alertas(self) -> list[Alerta]:
        """Qué tiene que saber el asesor antes de mirar cualquier número de esta cartera."""
        alertas: list[Alerta] = []
        if self.no_resueltas:
            alertas.append(_alerta_no_resueltas(self.no_resueltas, self.cobertura))
        if self.cobertura.porcentaje_no_resuelto is None and self.cobertura.posiciones:
            alertas.append(_alerta_sin_base(self.cobertura))
        elif self.cobertura.hay_posiciones_fuera_de_la_base:
            alertas.append(_alerta_sin_monto(self.cobertura))
        if self.sin_plazo:
            alertas.append(_alerta_sin_plazo(self.sin_plazo))
        if self.con_dato_no_sano:
            alertas.append(_alerta_dato_no_sano(self.con_dato_no_sano))
        return alertas

    def como_dict(self) -> dict[str, object]:
        return {
            "posiciones": [p.como_dict() for p in self.posiciones],
            "cobertura": self.cobertura.como_dict(),
            "alertas": [a.como_dict() for a in self.alertas],
        }


def clave_de_busqueda(ticker: str) -> str:
    """Con qué se busca un ticker escrito a mano: sin espacios de más y en mayúsculas.

    **Es lo único que se le hace al ticker declarado, y no lo cambia por otro.** `  al30 ` y `AL30`
    son el mismo ticker escrito distinto; `RUCEX` y `RUCEO` no. La diferencia entre normalizar la
    escritura y derivar una especie de otra es exactamente la línea que esta feature no cruza.

    Verificado contra la base: las 2.894 filas de `instrumentos` tienen el ticker en mayúsculas, así
    que esta clave no puede fusionar dos tickers distintos del universo en uno solo.
    """
    return ticker.strip().upper()


def indexar_instrumentos(filas: Sequence[Mapping[str, object]]) -> dict[str, FilaInstrumento]:
    """El índice de lo que existe, por clave de búsqueda. La lectura de `instrumentos`, sin más."""
    indice: dict[str, FilaInstrumento] = {}
    for fila in filas:
        ticker = str(fila["ticker"])
        indice[clave_de_busqueda(ticker)] = FilaInstrumento(
            ticker=ticker,
            clase_activo=_texto(fila.get("clase_activo")),
            plazo_liquidacion=_texto(fila.get("plazo_liquidacion")),
        )
    return indice


def resolver(
    posiciones: Sequence[PosicionDeclarada],
    especies: Sequence[EspecieUniverso],
    instrumentos: Mapping[str, FilaInstrumento] | None = None,
    descartados: Collection[str] = frozenset(),
    fondos_fci: Mapping[str, FondoFciResuelto] | None = None,
) -> CarteraResuelta:
    """Busca cada ticker declarado entre las especies vivas y arma el diagnóstico de cobertura.

    `especies` es la vista **viva** del universo —todas las especies, sin colapsar— y no la
    colapsada: la cartera de un cliente tiene la especie que compró, y colapsarla contra el
    representante de su emisión diría que tiene un instrumento que no tiene. Además el optimizador
    (F-032) necesita ver las tres especies para poder proponer rotar entre ellas.

    `instrumentos` es lo que existe en la base aunque no sea comparable, y sirve para dos cosas: el
    plazo de liquidación de las que resolvieron, y el motivo de las que no. Sin él, todo lo no
    resuelto se reportaría como "no está en el universo", que sobre una acción es falso.

    `fondos_fci` es el lookup **exacto** por `codigo_cafci` (F-046): sólo se consulta cuando el
    ticker declarado no matcheó ninguna especie, y sólo por el código tal cual está escrito — nunca
    por nombre, nunca fuzzy (regla 1 del proyecto).
    """
    por_ticker = {clave_de_busqueda(e.ticker): e for e in especies}
    conocidos = instrumentos or {}
    fondos = fondos_fci or {}

    resueltas = [_resolver_una(p, por_ticker, conocidos, descartados, fondos) for p in posiciones]
    return CarteraResuelta(posiciones=resueltas, cobertura=_medir_cobertura(resueltas))


def _resolver_una(
    posicion: PosicionDeclarada,
    por_ticker: Mapping[str, EspecieUniverso],
    conocidos: Mapping[str, FilaInstrumento],
    descartados: Collection[str],
    fondos_fci: Mapping[str, FondoFciResuelto],
) -> PosicionResuelta:
    """Una sola búsqueda exacta. No hay un segundo intento con el ticker modificado."""
    clave = clave_de_busqueda(posicion.ticker_declarado)
    conocido = conocidos.get(clave)
    especie = por_ticker.get(clave)

    if especie is None:
        # El lookup de FCI se prueba antes de resignarse a "no está en el universo": un
        # `codigo_cafci` pegado en un resumen de cuenta no es un typo, es otra clase de instrumento.
        # Comparación por el texto tal cual, sólo despojado de espacios — nunca por nombre.
        fondo = fondos_fci.get(posicion.ticker_declarado.strip())
        if fondo is not None:
            return PosicionResuelta(declarada=posicion, motivo=MotivoNoResuelta.ES_FCI, fondo_fci=fondo)
        return PosicionResuelta(
            declarada=posicion,
            motivo=_motivo_de(conocido),
            clase_activo=conocido.clase_activo if conocido else None,
        )

    return PosicionResuelta(
        declarada=posicion,
        especie=especie,
        plazo_liquidacion=conocido.plazo_liquidacion if conocido else None,
        dato_sano=especie.ticker not in descartados,
        clase_activo=conocido.clase_activo if conocido else especie.clase_activo,
    )


def _motivo_de(conocido: FilaInstrumento | None) -> MotivoNoResuelta:
    """Por qué este ticker no llegó al universo comparable, según lo que la base dice de él."""
    if conocido is None:
        return MotivoNoResuelta.NO_ESTA_EN_EL_UNIVERSO
    if conocido.clase_activo in CLASES_RENTA_VARIABLE:
        return MotivoNoResuelta.RENTA_VARIABLE
    return MotivoNoResuelta.SIN_TIPO_DE_TASA


def _medir_cobertura(posiciones: Sequence[PosicionResuelta]) -> Cobertura:
    """Los conteos y el porcentaje, con las posiciones sin monto contadas aparte y no como cero.

    El conteo de posiciones no resueltas es exacto siempre: no depende de que haya monto declarado.
    El que depende de la base es el porcentaje, y por eso es el único que puede quedar en `None`.
    """
    con_monto = [p for p in posiciones if p.declarada.monto is not None]
    sin_monto = [p for p in posiciones if p.declarada.monto is None]
    no_resueltas = [p for p in posiciones if not p.resuelta]

    base = sum(p.declarada.monto or 0.0 for p in con_monto)
    no_resuelto = sum(p.declarada.monto or 0.0 for p in con_monto if not p.resuelta)

    return Cobertura(
        posiciones=len(posiciones),
        resueltas=len(posiciones) - len(no_resueltas),
        no_resueltas=len(no_resueltas),
        posiciones_con_monto=len(con_monto),
        posiciones_sin_monto=len(sin_monto),
        posiciones_sin_monto_no_resueltas=sum(1 for p in sin_monto if not p.resuelta),
        monto_declarado=base,
        monto_no_resuelto=no_resuelto,
        porcentaje_no_resuelto=(no_resuelto / base * 100) if base else None,
    )


def _tickers(posiciones: Sequence[PosicionResuelta]) -> list[str]:
    return [p.declarada.ticker_declarado for p in posiciones]


def _alerta_no_resueltas(posiciones: Sequence[PosicionResuelta], cobertura: Cobertura) -> Alerta:
    """Los tickers que no se reconocieron, con nombre y apellido y sin reemplazo propuesto.

    El mensaje nombra el porcentaje sólo si se pudo calcular. Decir "0 %" cuando lo que pasa es que
    ninguna posición declaró monto sería tapar el faltante con un número tranquilizador.
    """
    tickers = _tickers(posiciones)
    porcentaje = cobertura.porcentaje_no_resuelto
    cuanto = (
        f"El monto declarado de las que no resolvieron es {_pct(porcentaje)} del monto declarado "
        "de la cartera."
        if porcentaje is not None
        else "Cuánto pesan en plata no se puede calcular: ninguna posición declaró monto."
    )
    return Alerta(
        codigo=CODIGO_POSICIONES_NO_RESUELTAS,
        mensaje=(
            f"{len(posiciones)} de {cobertura.posiciones} posiciones no se reconocieron en el "
            f"universo ({', '.join(tickers[:MUESTRA_ALERTA])}). {cuanto} Quedan en la cartera con "
            "su monto: no se las reemplaza por el ticker más parecido."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Verificar el ticker con el resumen de cuenta. Si es correcto, el instrumento no está "
            "en el universo de hoy y hay que cargarlo a mano en la ingesta."
        ),
        detalle={
            "cantidad": len(posiciones),
            "tickers": tickers,
            "por_motivo": {
                motivo.value: [
                    p.declarada.ticker_declarado for p in posiciones if p.motivo is motivo
                ]
                for motivo in MotivoNoResuelta
                if any(p.motivo is motivo for p in posiciones)
            },
            "porcentaje_no_resuelto": porcentaje,
        },
    )


def _alerta_sin_monto(cobertura: Cobertura) -> Alerta:
    """El porcentaje se calculó sobre una parte de la cartera, y hay que decir sobre cuál.

    Un porcentaje sin su base se lee como si fuera de toda la cartera. Estas posiciones declaran
    nominales pero no monto, y valorizarlas requiere un precio que —si además no resolvieron— no
    existe: por eso quedan afuera del cálculo en vez de entrar como cero.
    """
    afuera = cobertura.posiciones_sin_monto
    sin_resolver = cobertura.posiciones_sin_monto_no_resueltas
    fuera_de_la_base = (
        "la otra posición no declara monto y no se la cuenta como cero"
        if afuera == 1
        else f"las otras {afuera} posiciones no declaran monto y no se las cuenta como cero"
    )
    tampoco = ""
    if sin_resolver == 1:
        cual = "Esa posición" if afuera == 1 else "Una de ellas"
        tampoco = f" {cual} además no resolvió, así que no hay precio con el que valorizarla."
    elif sin_resolver > 1:
        tampoco = (
            f" {sin_resolver} de ellas además no resolvieron, así que no hay precio con el que "
            "valorizarlas."
        )

    return Alerta(
        codigo=CODIGO_POSICIONES_SIN_MONTO,
        mensaje=(
            f"El porcentaje sin resolver se calculó sobre {cobertura.posiciones_con_monto} de "
            f"{cobertura.posiciones} posiciones: {fuera_de_la_base}.{tampoco}"
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Cargar el monto de esas posiciones, o valorizarlas con el precio del universo una vez "
            "que el ticker resuelva."
        ),
        detalle={
            "posiciones_con_monto": cobertura.posiciones_con_monto,
            "posiciones_sin_monto": cobertura.posiciones_sin_monto,
            "posiciones_sin_monto_no_resueltas": cobertura.posiciones_sin_monto_no_resueltas,
            "monto_declarado": cobertura.monto_declarado,
        },
    )


def _alerta_sin_base(cobertura: Cobertura) -> Alerta:
    """Ninguna posición declaró monto: el porcentaje no existe, y no es cero.

    La cantidad de posiciones sin resolver sigue siendo exacta —no depende del monto— y es lo que
    hay que mirar mientras tanto.
    """
    return Alerta(
        codigo=CODIGO_SIN_BASE_PARA_EL_PORCENTAJE,
        mensaje=(
            f"Ninguna de las {cobertura.posiciones} posiciones declara monto, así que no hay base "
            f"sobre la cual calcular el porcentaje sin resolver. Lo que sí es exacto es la "
            f"cantidad: {cobertura.no_resueltas} sin resolver."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida="Cargar los montos de la cartera para poder medir la cobertura en plata.",
        detalle={
            "posiciones": cobertura.posiciones,
            "no_resueltas": cobertura.no_resueltas,
        },
    )


def _alerta_sin_plazo(posiciones: Sequence[PosicionResuelta]) -> Alerta:
    """Resolvió el instrumento pero no se sabe en qué plazo está la cotización guardada.

    Se deja vacío y se nombra. Poner el plazo estándar sería inventar el dato de una posición
    concreta a partir de lo que suele pasar, que es la regla 1 al revés.
    """
    tickers = _tickers(posiciones)
    return Alerta(
        codigo=CODIGO_PLAZO_NO_DISPONIBLE,
        mensaje=(
            f"{len(posiciones)} posiciones resolvieron pero su plazo de liquidación no está en la "
            f"base ({', '.join(tickers[:MUESTRA_ALERTA])}): queda vacío y no se completa con el "
            "plazo estándar."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Revisar si la última corrida de ingesta de BYMA trajo `settlementType` para esas "
            "especies."
        ),
        detalle={"cantidad": len(posiciones), "tickers": tickers},
    )


def _alerta_dato_no_sano(posiciones: Sequence[PosicionResuelta]) -> Alerta:
    """La posición resolvió, pero la especie es una de las que la sanidad de F-010 descartó.

    Se resuelve igual —el asesor tiene ese bono en la cartera, no desaparece porque su precio esté
    mal escalado en la fuente— y se avisa, porque cualquier número que se calcule sobre ella va a
    heredar el error.
    """
    tickers = _tickers(posiciones)
    return Alerta(
        codigo=CODIGO_POSICION_CON_DATO_NO_SANO,
        mensaje=(
            f"{len(posiciones)} posiciones resolvieron contra una especie cuyo dato de mercado la "
            f"sanidad descartó ({', '.join(tickers[:MUESTRA_ALERTA])}): la posición existe, pero "
            "su rendimiento publicado no se puede usar."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida="Consultar el detalle del descarte en /universo/sanidad/descartes.",
        detalle={"cantidad": len(posiciones), "tickers": tickers},
    )


def _pct(valor: float) -> str:
    """Un porcentaje escrito como se lee en Argentina: coma decimal.

    El mensaje de una alerta lo lee una persona, y `23.7 %` en un texto en castellano se lee mal.
    Es reemplazo de carácter y no `locale`: cambiar el locale del proceso afectaría a todo lo que
    formatee números en el backend, que es demasiado para una coma.
    """
    return f"{valor:.1f}".replace(".", ",") + " %"


def _texto(valor: object) -> str | None:
    """Un texto de la base, o `None`. Igual que en `segmentacion`: no se traduce el contenido."""
    if not isinstance(valor, str):
        return None
    limpio = valor.strip()
    return limpio or None
