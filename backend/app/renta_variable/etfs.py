"""Qué estrategia respalda el armado de un ETF, leída de su nombre oficial.

## Por qué del nombre y no de otra fuente

La SEC, que sirve para las empresas, **no sirve para los ETFs**: de los 25 que lista BYMA sólo dos
tienen CIK, `SPY` y `QQQ` traen el campo SIC vacío, y `GLD` trae `6221 Commodity Contracts Brokers
& Dealers`, que describe la figura legal del vehículo y no dice nada de qué compra el fondo
(verificado el 13/08/2026).

Lo que sí hay es el nombre que publica BYMA en su tabla oficial de CEDEARs, y ese nombre **ya
declara la estrategia**: `iShares S&P 500 Value ETF` dice emisor, índice y sesgo. Clasificar por lo
que el nombre dice no es interpretar: es leer.

## Hasta dónde llega, y dónde se detiene

Alcanza para decir **qué idea arma el portafolio** —un índice amplio, un factor, una región, un
sector, un activo físico—, que es lo que el asesor necesita para no meter dos fondos que hacen lo
mismo. **No alcanza** para el método de ponderación ni para las reglas de rebalanceo: eso vive en
el prospecto de cada emisor y no se infiere del nombre.

Un nombre que no encaja en ninguna categoría **no se fuerza a la más parecida**: cae en
`SIN_CLASIFICAR` y se muestra el nombre oficial tal cual, que ya es informativo por sí solo.

## El detector, que no es `'ETF' in nombre`

`NETFLIX` contiene `ETF`. La primera versión de esto clasificó a Netflix como fondo por buscar la
sigla como substring — por eso se compara **por palabra**, contra el nombre partido en tokens.
"""

import re
from dataclasses import dataclass

SIN_CLASIFICAR = "sin_clasificar"

# Palabras que marcan que el papel es un fondo y no una empresa. Se comparan como palabra entera.
MARCAS_DE_FONDO: frozenset[str] = frozenset({"ETF", "TRUST", "TR", "FUND"})


@dataclass(frozen=True, slots=True)
class EstrategiaEtf:
    """Qué idea arma el portafolio de este fondo."""

    clave: str
    """Identificador estable, para filtrar y agrupar."""
    etiqueta: str
    """Cómo se lee en pantalla."""
    porque: str
    """Qué parte del nombre lo determinó. Va a la vista: un fondo clasificado sin decir por qué es
    una caja negra, y acá la evidencia es corta y cabe."""


# Cada regla es (patrón sobre el nombre, estrategia). **El orden importa**: se evalúan de la más
# específica a la más general, porque los nombres se acumulan — `iShares S&P 500 Value ETF` nombra
# un índice amplio *y* un factor, y lo que lo distingue de `IVV` es el factor.
_REGLAS: tuple[tuple[re.Pattern[str], EstrategiaEtf], ...] = (
    (
        re.compile(r"\b(equal|eql)\s*(weight|wght)\b", re.I),
        EstrategiaEtf(
            "equiponderado",
            "Equiponderado",
            "el nombre dice equal weight: todas las posiciones pesan igual, sin importar el tamaño",
        ),
    ),
    (
        re.compile(r"\b(value|growth|quality|momentum|dividend)\b", re.I),
        EstrategiaEtf(
            "factor",
            "Por factor",
            "el nombre declara un factor (value, growth, quality, dividend): filtra por métricas "
            "fundamentales dentro de un índice",
        ),
    ),
    (
        re.compile(r"\bESG\b", re.I),
        EstrategiaEtf("esg", "ESG", "el nombre declara criterio ESG en la selección"),
    ),
    (
        re.compile(r"\b(bitcoin|ethereum|eth|btc)\b", re.I),
        EstrategiaEtf("cripto", "Cripto", "el nombre nombra un activo digital"),
    ),
    (
        re.compile(
            r"\b(gold|silver|oro|plata)\b.*\b(trust|tr)\b|\b(trust|tr)\b.*\b(gold|silver)\b",
            re.I,
        ),
        EstrategiaEtf(
            "activo_fisico",
            "Activo físico",
            "es un trust sobre el metal: tiene el activo, no acciones de empresas",
        ),
    ),
    (
        re.compile(
            r"\b(select\s+sector|miners?|mining|semiconductor|biotechnology|uranium|copper|"
            r"energy|metals|materials|utilities|industrial|financial|health\s*care|real\s+estate|"
            r"consumer\s+(staples|discretionary)|communication\s+services|cybersecurity|"
            r"clean\s+energy|technology|oil)\b",
            re.I,
        ),
        EstrategiaEtf(
            "sectorial",
            "Sectorial",
            "el nombre nombra un sector o industria: concentra en una sola actividad",
        ),
    ),
    (
        re.compile(
            r"\b(japan|china|korea|europe|brazil|latin\s+america|emerging|EAFE|developed|"
            r"world|ACWI|global)\b",
            re.I,
        ),
        EstrategiaEtf(
            "geografico",
            "Geográfico",
            "el nombre nombra un país, una región o el mundo: la exposición es geográfica",
        ),
    ),
    (
        re.compile(r"\b(S&P\s*500|nasdaq|dow|russell|mid-?cap|small-?cap|total\s+market)\b", re.I),
        EstrategiaEtf(
            "indice_amplio",
            "Índice amplio",
            "el nombre nombra un índice general: replica el mercado, ponderado por capitalización",
        ),
    ),
)


def es_fondo(nombre: str | None) -> bool:
    """Si el nombre declara que el papel es un fondo y no una empresa.

    Compara por palabra entera: `NETFLIX` contiene `ETF` como substring y no es un fondo.
    """
    if not nombre:
        return False
    palabras = {p.upper() for p in re.findall(r"[A-Za-z&]+", nombre)}
    return bool(palabras & MARCAS_DE_FONDO)


def estrategia_de(nombre: str | None) -> EstrategiaEtf | None:
    """Qué idea arma el portafolio de este fondo. `None` si el papel no es un fondo.

    Un fondo cuyo nombre no encaja en ninguna regla devuelve `SIN_CLASIFICAR` — que es distinto de
    `None`: uno dice "es un fondo y no sabemos su estrategia", el otro "no es un fondo".
    """
    if not es_fondo(nombre):
        return None
    for patron, estrategia in _REGLAS:
        if patron.search(nombre or ""):
            return estrategia
    return EstrategiaEtf(
        SIN_CLASIFICAR,
        "Fondo, sin clasificar",
        "el nombre no declara una estrategia reconocible; se muestra el nombre oficial tal cual",
    )
