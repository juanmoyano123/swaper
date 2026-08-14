"""El parser de XBRL de `companyfacts` — puro, sin red, testeable con fixtures.

Separado de `sec_ficha.py` (la I/O) a propósito: acá no hay `httpx`, sólo funciones sobre el JSON
que la SEC ya entregó. Ver el docstring de `sec_ficha.py` para el porqué de todo el módulo.

## Dos taxonomías, y por qué no se puede asumir una

Verificado en vivo el 13-14/08/2026: los filers domésticos (ej. MELI) publican bajo `us-gaap`,
vigente y con trimestral. Los foreign private issuers sudamericanos (ABEV, VALE, YPF, BBD, ITUB,
PBR) tienen sus conceptos `us-gaap` **muertos desde 2010-2012** — a partir de ahí reportan bajo
`ifrs-full`, y sólo con `fp: FY` (nunca trimestral consistente). La taxonomía vigente se decide
**una vez por empresa**, con un concepto representativo (`Assets`), no concepto por concepto: el
research confirmó que el cambio es de la empresa entera, no de un campo suelto.

## La ambigüedad trimestre vs. acumulado

Cada filing de un concepto de **flujo** (`NetIncomeLoss`, `Revenues`, `OperatingIncomeLoss` — los
que tienen `start`+`end`) mezcla en el mismo array el valor del trimestre discreto y el acumulado
año-a-la-fecha. La regla, confirmada con datos reales de Apple: cuando existe `frame` (ej.
`CY2026Q2`), es el período discreto limpio; si no existe, se clasifica por duración (~90 días
trimestre, ~365 días año) y se descarta cualquier otra duración. **Nunca se usa el `fp` del filing
como proxy**: `fp` es el período fiscal del filing entero, no necesariamente la duración real del
dato dentro de él.

Los conceptos de **instante** (`Assets`, `StockholdersEquity`, `CashAndCashEquivalentsAtCarrying
Value`, `AssetsCurrent`/`LiabilitiesCurrent` — sólo `end`, sin `start`) no tienen esta ambigüedad:
cada entrada es una foto a una fecha.

## El anclaje al mismo ejercicio

Todos los ratios de una ficha se calculan sobre el **mismo ejercicio fiscal** — el último para el
que existen `NetIncomeLoss` y `StockholdersEquity` anuales, los dos conceptos núcleo. Nunca "el
valor más reciente de cada concepto por separado": eso podría mezclar el resultado de FY2025 en un
ratio con el patrimonio de FY2024 en otro, si un concepto se publicó antes que el otro en el
mismo companyfacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

# Antes de esta fecha, los foreign private issuers todavía reportaban bajo us-gaap: es el punto de
# corte medido en el research (ABEV, VALE, YPF, BBD, ITUB, PBR migraron entre 2010 y 2012). Un
# `Assets` en us-gaap con `fin` posterior a esta fecha es señal de filer doméstico vigente.
FECHA_CORTE_TAXONOMIA = "2015-01-01"

# Tolerancia de duración para clasificar un hecho de flujo sin `frame`. Un año de transición fiscal
# (cambio de cierre de ejercicio) puede caer fuera de estos rangos a propósito: se descarta en vez
# de forzarlo a trimestre o año, que sería inventar qué período representa.
DIAS_TRIMESTRE = (80, 100)
DIAS_ANIO = (355, 375)

_FRAME_ANUAL = re.compile(r"^CY\d{4}$")
_FRAME_TRIMESTRAL = re.compile(r"^CY\d{4}Q[1-4]$")

# Concepto lógico → nombres del campo XBRL, por taxonomía, en orden de preferencia. Confirmado
# concepto por concepto contra companyfacts reales (13-14/08/2026). Un concepto ausente en una
# empresa dada (ej. `operating_income` en bancos FPI) se declara ausente, nunca se sustituye.
CONCEPTOS: dict[str, dict[str, tuple[str, ...]]] = {
    "assets": {"us-gaap": ("Assets",), "ifrs-full": ("Assets",)},
    "liabilities": {"us-gaap": ("Liabilities",), "ifrs-full": ("Liabilities",)},
    "equity": {
        "us-gaap": ("StockholdersEquity",),
        "ifrs-full": ("Equity", "EquityAttributableToOwnersOfParent"),
    },
    "revenue": {
        "us-gaap": ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        "ifrs-full": ("Revenue",),
    },
    "net_income": {
        "us-gaap": ("NetIncomeLoss",),
        "ifrs-full": ("ProfitLoss", "ProfitLossAttributableToOwnersOfParent"),
    },
    "operating_income": {
        "us-gaap": ("OperatingIncomeLoss",),
        "ifrs-full": ("ProfitLossFromOperatingActivities",),
    },
    "eps_diluted": {
        "us-gaap": ("EarningsPerShareDiluted",),
        "ifrs-full": ("DilutedEarningsLossPerShare",),
    },
    "cash": {
        "us-gaap": ("CashAndCashEquivalentsAtCarryingValue",),
        "ifrs-full": ("CashAndCashEquivalents",),
    },
    "long_term_debt": {
        "us-gaap": ("LongTermDebt", "LongTermDebtNoncurrent"),
        "ifrs-full": ("LongtermBorrowings",),
    },
    "current_assets": {"us-gaap": ("AssetsCurrent",), "ifrs-full": ("CurrentAssets",)},
    "current_liabilities": {
        "us-gaap": ("LiabilitiesCurrent",),
        "ifrs-full": ("CurrentLiabilities",),
    },
}


@dataclass(frozen=True, slots=True)
class HechoXbrl:
    """Un valor publicado, con todo lo que hace falta para no inventar nada al usarlo."""

    valor: float
    unidad: str
    """La unidad tal como la declara la fuente: `USD`, `BRL`, `shares`. Nunca se asume."""
    fin: str
    """ISO. Para un concepto de instante, la fecha de la foto; para uno de flujo, el fin del
    período."""
    inicio: str | None
    """`None` en los conceptos de instante."""
    frame: str | None
    """`CY2025` o `CY2025Q2` cuando la fuente lo declara — el período discreto limpio."""
    taxonomia: str
    concepto: str
    """El nombre real del campo XBRL usado (ej. `NetIncomeLoss`), para auditoría."""


def hechos_de(companyfacts: dict, taxonomia: str, concepto: str) -> list[HechoXbrl]:
    """Todos los hechos publicados de un concepto en una taxonomía, sin filtrar por período — el
    llamador decide qué período usar. Una entrada sin `end` o sin `val` numérico se descarta: no
    es un hecho utilizable."""
    bloque = companyfacts.get("facts", {}).get(taxonomia, {}).get(concepto)
    if not isinstance(bloque, dict):
        return []
    hechos: list[HechoXbrl] = []
    for unidad, entradas in bloque.get("units", {}).items():
        if not isinstance(entradas, list):
            continue
        for entrada in entradas:
            fin = entrada.get("end")
            valor = entrada.get("val")
            if not isinstance(fin, str) or not isinstance(valor, (int, float)):
                continue
            inicio = entrada.get("start")
            hechos.append(
                HechoXbrl(
                    valor=float(valor),
                    unidad=str(unidad),
                    fin=fin,
                    inicio=inicio if isinstance(inicio, str) else None,
                    frame=entrada.get("frame") if isinstance(entrada.get("frame"), str) else None,
                    taxonomia=taxonomia,
                    concepto=concepto,
                )
            )
    return hechos


def taxonomia_vigente(companyfacts: dict) -> str:
    """`us-gaap` si tiene `Assets` con datos posteriores a `FECHA_CORTE_TAXONOMIA`; si no,
    `ifrs-full`. Se decide una vez por empresa, no concepto por concepto (ver docstring del
    módulo)."""
    hechos = hechos_de(companyfacts, "us-gaap", "Assets")
    if hechos and max(h.fin for h in hechos) >= FECHA_CORTE_TAXONOMIA:
        return "us-gaap"
    return "ifrs-full"


def hechos_del_concepto(companyfacts: dict, clave: str, taxonomia: str) -> list[HechoXbrl]:
    """Los hechos de un concepto lógico (`"net_income"`) en la taxonomía dada, probando cada
    nombre de campo de la lista de preferencia hasta encontrar uno con datos. Lista vacía si la
    empresa no publica ninguno — se declara ausente río arriba, nunca se sustituye."""
    for nombre in CONCEPTOS.get(clave, {}).get(taxonomia, ()):
        hechos = hechos_de(companyfacts, taxonomia, nombre)
        if hechos:
            return hechos
    return []


def _duracion_dias(inicio: str, fin: str) -> int | None:
    try:
        return (date.fromisoformat(fin) - date.fromisoformat(inicio)).days
    except ValueError:
        return None


def periodos_limpios(hechos: list[HechoXbrl]) -> tuple[list[HechoXbrl], list[HechoXbrl]]:
    """Para un concepto de flujo: separa `(anuales, trimestrales)`, cada lista con sólo períodos
    discretos limpios. Un hecho sin `start`, con `frame` de otra forma, o con una duración que no
    cae en ninguno de los dos rangos (un año de transición fiscal, por ejemplo) no entra en
    ninguna de las dos listas — se descarta en vez de forzarlo."""
    anuales: list[HechoXbrl] = []
    trimestrales: list[HechoXbrl] = []
    for hecho in hechos:
        if hecho.inicio is None:
            continue
        if hecho.frame is not None:
            if _FRAME_ANUAL.fullmatch(hecho.frame):
                anuales.append(hecho)
            elif _FRAME_TRIMESTRAL.fullmatch(hecho.frame):
                trimestrales.append(hecho)
            continue
        dias = _duracion_dias(hecho.inicio, hecho.fin)
        if dias is None:
            continue
        if DIAS_ANIO[0] <= dias <= DIAS_ANIO[1]:
            anuales.append(hecho)
        elif DIAS_TRIMESTRE[0] <= dias <= DIAS_TRIMESTRE[1]:
            trimestrales.append(hecho)
    return anuales, trimestrales


@dataclass(frozen=True, slots=True)
class DatosEjercicio:
    """Los hechos núcleo de un CEDEAR, todos anclados al mismo ejercicio fiscal — o `None` cuando
    el concepto no está publicado para ese ejercicio puntual, nunca sustituido por el de otro."""

    taxonomia: str
    periodo: str
    """El `fin` del ejercicio ancla, ISO. Ningún ratio usa una fecha distinta a ésta."""
    solo_anual: bool
    """`True` cuando ni `net_income` ni `revenue` tienen un solo período trimestral limpio —
    derivado de los datos, no del tipo de formulario."""
    assets: HechoXbrl | None
    liabilities: HechoXbrl | None
    equity: HechoXbrl | None
    revenue: HechoXbrl | None
    revenue_anio_anterior: HechoXbrl | None
    net_income: HechoXbrl | None
    operating_income: HechoXbrl | None
    eps_diluted: HechoXbrl | None
    cash: HechoXbrl | None
    long_term_debt: HechoXbrl | None
    current_assets: HechoXbrl | None
    current_liabilities: HechoXbrl | None


def _en_fecha(hechos: list[HechoXbrl], fin: str) -> HechoXbrl | None:
    return next((h for h in hechos if h.fin == fin), None)


def datos_del_ejercicio(companyfacts: dict) -> DatosEjercicio | None:
    """Resuelve la taxonomía vigente, ancla al último ejercicio fiscal con `net_income` Y `equity`
    (los dos conceptos núcleo), y devuelve los hechos de todo lo demás en esa misma fecha.

    `None` si no hay ni un ejercicio con los dos conceptos núcleo — no hay ancla posible, y
    devolver datos parciales sin un ejercicio común sería mezclar períodos (regla del módulo).
    """
    taxonomia = taxonomia_vigente(companyfacts)

    hechos_ni = hechos_del_concepto(companyfacts, "net_income", taxonomia)
    ni_anuales, ni_trimestrales = periodos_limpios(hechos_ni)
    if not ni_anuales:
        return None

    hechos_eq = hechos_del_concepto(companyfacts, "equity", taxonomia)

    # El ejercicio ancla: el FY más reciente de net_income para el que equity también tiene una
    # foto en esa misma fecha. Se recorre del más nuevo al más viejo -- el primer match es el
    # último ejercicio completo, que es lo que la ficha quiere mostrar.
    ancla: str | None = None
    for hecho in sorted(ni_anuales, key=lambda h: h.fin, reverse=True):
        if _en_fecha(hechos_eq, hecho.fin) is not None:
            ancla = hecho.fin
            break
    if ancla is None:
        return None

    hechos_rev = hechos_del_concepto(companyfacts, "revenue", taxonomia)
    rev_anuales, rev_trimestrales = periodos_limpios(hechos_rev)
    hechos_oi = hechos_del_concepto(companyfacts, "operating_income", taxonomia)
    oi_anuales, _oi_trimestrales = periodos_limpios(hechos_oi)
    hechos_eps = hechos_del_concepto(companyfacts, "eps_diluted", taxonomia)
    eps_anuales, _eps_trimestrales = periodos_limpios(hechos_eps)

    revenue_ancla = _en_fecha(rev_anuales, ancla)
    revenue_anterior = next(
        (h for h in sorted(rev_anuales, key=lambda h: h.fin, reverse=True) if h.fin < ancla), None
    )

    def _instante(clave: str) -> HechoXbrl | None:
        return _en_fecha(hechos_del_concepto(companyfacts, clave, taxonomia), ancla)

    return DatosEjercicio(
        taxonomia=taxonomia,
        periodo=ancla,
        solo_anual=not ni_trimestrales and not rev_trimestrales,
        assets=_instante("assets"),
        liabilities=_instante("liabilities"),
        equity=_en_fecha(hechos_eq, ancla),
        revenue=revenue_ancla,
        revenue_anio_anterior=revenue_anterior,
        net_income=_en_fecha(ni_anuales, ancla),
        operating_income=_en_fecha(oi_anuales, ancla),
        eps_diluted=_en_fecha(eps_anuales, ancla),
        cash=_instante("cash"),
        long_term_debt=_instante("long_term_debt"),
        current_assets=_instante("current_assets"),
        current_liabilities=_instante("current_liabilities"),
    )
