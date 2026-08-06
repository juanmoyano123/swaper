"""Catálogo declarativo de las secciones de datos del informe diario de IAMC.

Es el archivo que se edita el día que IAMC cambie el layout: un título de página que no está acá
no se parsea, se aborta (`parser.InformeInvalido`). Eso no es un descuido — es la decisión central
de esta feature. La spec dice que "ley y moneda de pago se leen del título de la sección, no de
una columna inferida", y la razón está en CLAUDE.md, regla 1: una vez se tradujo un código de la
fuente como "Ley Inglesa", una categoría que no existe. Parsear "lo conocido" e ignorar una
sección nueva produciría un universo silenciosamente incompleto, con atributos posiblemente mal
heredados de la sección anterior — el mismo tipo de error, con otro disfraz.

Los headers de cada sección están en su forma **completa, sin truncar**: son la referencia contra
la que se valida lo que el PDF trae, que a veces sí llega truncado o partido por el ancho de
celda (`app.ingesta.iamc.parser._headers_compatibles` tolera eso).
"""

from dataclasses import dataclass
from enum import StrEnum

from app.ingesta.iamc.normalizacion import MAPA_LEY


class OrigenDato(StrEnum):
    """De dónde sale un atributo que no es una columna más: título de la sección, una columna
    explícita de la fila, o directamente no declarado en ningún lado."""

    TITULO = "titulo"
    COLUMNA = "columna"
    NINGUNO = "ninguno"


@dataclass(frozen=True, slots=True)
class CampoSeccion:
    header: str
    """Nombre del header tal como IAMC lo declara (con saltos de línea internos), en su forma
    completa — no la truncada que a veces aparece en el PDF."""

    campo: str
    """Clave canónica en `FilaInforme`."""


@dataclass(frozen=True, slots=True)
class Seccion:
    titulo: str
    campos: tuple[CampoSeccion, ...]
    """Orden posicional exacto, tal como las columnas aparecen en el PDF de izquierda a derecha."""

    origen_ley: OrigenDato
    ley_fija: str | None = None
    """Sólo cuando `origen_ley` es TITULO."""

    origen_moneda_pago: OrigenDato = OrigenDato.TITULO
    moneda_pago_fija: str | None = None

    moneda_monto_emitido: str | None = None
    """`None` cuando la moneda del monto emitido sale de una columna de la propia fila (cupón
    cero, que declara `Moneda Emision` explícitamente) en vez de ser fija por sección."""

    estructura_cupon_fija: str | None = None
    """La sección de tasa fija en pesos no trae columna `Estructura Cupon`: el título la declara
    literalmente ("TASA FIJA"), igual que declara la ley."""

    @property
    def n_campos(self) -> int:
        return len(self.campos)


_CAMPOS_DEUDA_USD = (
    CampoSeccion("Ticker", "ticker"),
    CampoSeccion("Emisor", "emisor"),
    CampoSeccion("Monto\nEmitido\nUSD", "monto_emitido"),
    CampoSeccion("Fecha\nEmision", "fecha_emision"),
    CampoSeccion("Fecha\nVencimiento", "fecha_vencimiento"),
    CampoSeccion("Estructura\nCupon", "estructura_cupon"),
    CampoSeccion("Frecuencia", "frecuencia_cupon"),
    CampoSeccion("Proximo\nCupon", "proximo_cupon"),
    CampoSeccion("Tasa\nCupon\nVigente", "tasa_cupon_vigente"),
    CampoSeccion("CY", "current_yield"),
    CampoSeccion("Accr.\nInt.", "interes_corrido"),
    CampoSeccion("VR", "valor_residual"),
    CampoSeccion("Cuotas\nCapital", "cuotas_capital"),
    CampoSeccion("Frecuencia\nPago", "frecuencia_pago_capital"),
    CampoSeccion("Proximo\nPago\nCapital", "proximo_pago_capital"),
    CampoSeccion("Cierre\nARS", "cierre_ars"),
    CampoSeccion("Paridad\n%", "paridad_pct"),
    CampoSeccion("VT", "valor_tecnico"),
    CampoSeccion("YTM", "tir"),
    CampoSeccion("DM", "duracion_modificada"),
    CampoSeccion("CX", "convexidad"),
    CampoSeccion("WAL", "vida_promedio"),
    CampoSeccion("ADTV 20\nRuedas\nARS", "volumen_promedio_20r_ars"),
)  # 23 columnas — verificado contra las páginas 1-2 y 5-13 de la muestra real.

_SECCION_LEY_NY = Seccion(
    titulo="DEUDA CORPORATIVA EN USD - LEY NY",
    campos=_CAMPOS_DEUDA_USD,
    origen_ley=OrigenDato.TITULO,
    ley_fija=MAPA_LEY["NY"],
    origen_moneda_pago=OrigenDato.TITULO,
    moneda_pago_fija="USD",
    moneda_monto_emitido="USD",
)

_SECCION_LEY_ARG = Seccion(
    titulo="DEUDA CORPORATIVA EN USD - LEY ARG",
    campos=_CAMPOS_DEUDA_USD,
    origen_ley=OrigenDato.TITULO,
    ley_fija=MAPA_LEY["ARG"],
    origen_moneda_pago=OrigenDato.TITULO,
    moneda_pago_fija="USD",
    moneda_monto_emitido="USD",
)

_SECCION_TASA_FIJA = Seccion(
    titulo="BONOS EN USD - PAGADEROS EN PESOS - TASA FIJA - LEY ARG",
    campos=(
        CampoSeccion("Ticker", "ticker"),
        CampoSeccion("Emisor", "emisor"),
        CampoSeccion("Monto\nEmitido\nUSD", "monto_emitido"),
        CampoSeccion("Fecha\nEmision", "fecha_emision"),
        CampoSeccion("Fecha\nVencimiento", "fecha_vencimiento"),
        CampoSeccion("Frecuencia", "frecuencia_cupon"),
        CampoSeccion("Proximo\nCupon", "proximo_cupon"),
        CampoSeccion("Tasa\nCupon\nVigente", "tasa_cupon_vigente"),
        CampoSeccion("CY", "current_yield"),
        CampoSeccion("Accr.\nInt.", "interes_corrido"),
        CampoSeccion("VR", "valor_residual"),
        CampoSeccion("Cuotas\nCapital", "cuotas_capital"),
        CampoSeccion("Frecuencia\nPago", "frecuencia_pago_capital"),
        CampoSeccion("Proximo\nPago\nCapital", "proximo_pago_capital"),
        CampoSeccion("Cierre\nARS", "cierre_ars"),
        CampoSeccion("Paridad\n%", "paridad_pct"),
        CampoSeccion("VT", "valor_tecnico"),
        CampoSeccion("YTM", "tir"),
        CampoSeccion("DM", "duracion_modificada"),
        CampoSeccion("CX", "convexidad"),
        CampoSeccion("WAL", "vida_promedio"),
        CampoSeccion("ADTV 20\nRuedas\nARS", "volumen_promedio_20r_ars"),
    ),  # 22 columnas: sin "Estructura Cupon" — todos los bonos de esta sección son tasa fija,
    # y el título ya lo declara literalmente.
    origen_ley=OrigenDato.TITULO,
    ley_fija=MAPA_LEY["ARG"],
    origen_moneda_pago=OrigenDato.TITULO,
    moneda_pago_fija="ARS",
    moneda_monto_emitido="USD",
    estructura_cupon_fija="Tasa Fija",
)

_SECCION_CUPON_CERO = Seccion(
    titulo="BONOS EN USD - PAGADEROS EN PESOS - CUPÓN CERO",
    campos=(
        CampoSeccion("Ticker", "ticker"),
        CampoSeccion("Emisor", "emisor"),
        CampoSeccion("Ley", "ley"),
        CampoSeccion("Moneda\nEmision", "moneda_emision"),
        CampoSeccion("Monto\nEmitido", "monto_emitido"),
        CampoSeccion("Moneda\nPago", "moneda_pago"),
        CampoSeccion("Fecha\nEmision", "fecha_emision"),
        CampoSeccion("Fecha\nVencimiento", "fecha_vencimiento"),
        CampoSeccion("VR", "valor_residual"),
        CampoSeccion("Cuotas\nCapital", "cuotas_capital"),
        CampoSeccion("Estructura\nCupon", "estructura_cupon"),
        CampoSeccion("Frecuencia\nPago", "frecuencia_pago_capital"),
        CampoSeccion("Proximo\nPago\nCapital", "proximo_pago_capital"),
        CampoSeccion("Cierre\nARS", "cierre_ars"),
        CampoSeccion("Paridad\n%", "paridad_pct"),
        CampoSeccion("VT", "valor_tecnico"),
        CampoSeccion("YTM", "tir"),
        CampoSeccion("DM", "duracion_modificada"),
        CampoSeccion("CX", "convexidad"),
        CampoSeccion("WAL", "vida_promedio"),
        CampoSeccion("ADTV 20\nRuedas\nARS", "volumen_promedio_20r_ars"),
    ),  # 21 columnas: la única sección que trae Ley y Moneda Pago como columnas explícitas por
    # fila, en vez de declararlas en el título.
    origen_ley=OrigenDato.COLUMNA,
    origen_moneda_pago=OrigenDato.COLUMNA,
    moneda_pago_fija="ARS",  # lo que el título declara — para poder detectar la discrepancia.
    moneda_monto_emitido=None,  # sale de la columna "Moneda Emision" de cada fila.
)

_SECCION_PESOS = Seccion(
    titulo="DEUDA CORPORATIVA - EMITIDA Y PAGADERA EN PESOS",
    campos=(
        CampoSeccion("Ticker", "ticker"),
        CampoSeccion("Emisor", "emisor"),
        CampoSeccion("Monto\nEmitido\nARS", "monto_emitido"),
        CampoSeccion("Fecha\nEmision", "fecha_emision"),
        CampoSeccion("Fecha\nVencimiento", "fecha_vencimiento"),
        CampoSeccion("Estructura\nCupon", "estructura_cupon"),
        CampoSeccion("Indice", "indice_cupon"),
        CampoSeccion("Frecuencia\nCupón", "frecuencia_cupon"),
        CampoSeccion("Proximo\nCupon", "proximo_cupon"),
        CampoSeccion("Tasa\nCupon\nVigente", "tasa_cupon_vigente"),
        CampoSeccion("CY", "current_yield"),
        CampoSeccion("Accr.\nInt.", "interes_corrido"),
        CampoSeccion("VR", "valor_residual"),
        CampoSeccion("Cuotas\nCapital", "cuotas_capital"),
        CampoSeccion("Frecuencia\nPago\nCapital", "frecuencia_pago_capital"),
        CampoSeccion("Proximo\nPago\nCapital", "proximo_pago_capital"),
        CampoSeccion("Cierre\nARS", "cierre_ars"),
        CampoSeccion("Paridad\n%", "paridad_pct"),
        CampoSeccion("VT", "valor_tecnico"),
        CampoSeccion("YTM", "tir"),
        CampoSeccion("DM", "duracion_modificada"),
        CampoSeccion("CX", "convexidad"),
        CampoSeccion("ADTV 20\nRuedas\nARS", "volumen_promedio_20r_ars"),
    ),  # 23 columnas, sin WAL: esta sección no publica vida promedio.
    origen_ley=OrigenDato.NINGUNO,  # no está declarada en ningún lado del PDF — verificado.
    origen_moneda_pago=OrigenDato.TITULO,
    moneda_pago_fija="ARS",
    moneda_monto_emitido="ARS",
)

GRAFICO_PREFIJOS = ("SENSIBILIDAD ", "CURVA ")
"""Títulos de página que son gráficos de Power BI, no tablas: se saltean sin abortar. Saltear no
es ignorar — están en este catálogo tanto como las secciones de datos, y una página con un título
que no matchea ninguna de las dos listas sigue abortando."""

SECCIONES: dict[str, Seccion] = {
    seccion.titulo: seccion
    for seccion in (
        _SECCION_LEY_NY,
        _SECCION_LEY_ARG,
        _SECCION_TASA_FIJA,
        _SECCION_CUPON_CERO,
        _SECCION_PESOS,
    )
}
