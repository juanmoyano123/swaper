"""Qué estrategia respalda el armado de un ETF y sobre qué geografía, leídas de su nombre oficial.

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


# --- La geografía que el nombre declara -----------------------------------------------------------
#
# Mismo criterio que la estrategia y por la misma razón: el nombre oficial que publica BYMA **ya
# dice** dónde invierte el fondo, y leerlo no es interpretarlo. `iShares MSCI JAPAN ETF` nombra
# Japón; `ISHARES CHINA LARGE-CAP ETF` nombra China. Lo que sale de acá es ese token y nada más.
#
# **No se traduce.** `EAFE` se devuelve `EAFE`, no "Europa, Australasia y Lejano Oriente": esa
# expansión es correcta pero no está en el nombre, y la regla 11 pide mostrar lo que la fuente
# declara tal como lo declara. Lo mismo con `ACWI`. Que después convivan en la misma pantalla un
# `Brazil` de nombre de ETF y una "América Latina y el Caribe" de país curado es a propósito: son
# dos vocabularios distintos y unificarlos sería traducir.
#
# **El vocabulario es cerrado y sale de la regla `geografico` de arriba**, extendido sólo con lo que
# se midió en la base (28/08/2026): los nueve fondos con geografía en el nombre son ACWI, EFA
# (EAFE), EWJ (Japan), EWY (South Korea), FXI (China), IEMG (Emerging Markets), IEUR (Europe), ILF
# (Latin America) y VEA (Developed Markets). Cerrado y no "cualquier topónimo" por un caso concreto:
# `United States Oil Fund` (USO) nombra un país en su **razón social** y compra futuros de WTI, así
# que un detector de topónimos le pondría "United States" como geografía de exposición. No está en
# la lista y por eso no lo hace.

# Cuánto texto de la izquierda alcanza para saber si un token viene negado (`ex China`, `ex-Japan`).
# Es fijo porque `re` no admite lookbehind de ancho variable.
_NEGACION = re.compile(r"\bex[\s-]$", re.I)

# (patrón, forma canónica). **El orden importa**, como en `_REGLAS`: lo específico antes que lo
# general, para que `South Korea` gane sobre `Korea` y `Emerging Markets` sobre `Emerging`.
#
# La forma canónica es la caja, no una traducción: los nombres llegan en mayúsculas (`ISHARES CHINA
# LARGE-CAP ETF`) y en mixta (`iShares MSCI JAPAN ETF`), y sin normalizar la caja el mismo país
# aparecería dos veces en un filtro. Lo único que se decide acá es cómo se escribe `China`.
_REGIONES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bACWI\b", re.I), "ACWI"),
    (re.compile(r"\bEAFE\b", re.I), "EAFE"),
    (re.compile(r"\bsouth\s+korea\b", re.I), "South Korea"),
    (re.compile(r"\bkorea\b", re.I), "Korea"),
    (re.compile(r"\bjapan\b", re.I), "Japan"),
    (re.compile(r"\bchina\b", re.I), "China"),
    (re.compile(r"\bbrazil\b", re.I), "Brazil"),
    (re.compile(r"\blatin\s+america\b", re.I), "Latin America"),
    (re.compile(r"\beurope\b", re.I), "Europe"),
    (re.compile(r"\bemerging\s+markets\b", re.I), "Emerging Markets"),
    (re.compile(r"\bemerging\b", re.I), "Emerging"),
    (re.compile(r"\bdeveloped\s+markets\b", re.I), "Developed Markets"),
    (re.compile(r"\bdeveloped\b", re.I), "Developed"),
    (re.compile(r"\bworld\b", re.I), "World"),
    # `Global` sí, `Global X` no: es la marca del emisor (Global X Funds), no una declaración de
    # alcance. Medido el 28/08/2026 — sin el lookahead, `Global X Copper Miners ETF` y `Global X
    # Uranium ETF` salían con geografía "Global" cuando lo único global de esos nombres es quién los
    # emite. Misma familia de error que `United States Oil Fund`, y por eso el vocabulario es
    # cerrado.
    (re.compile(r"\bglobal\b(?!\s+X\b)", re.I), "Global"),
)


def region_declarada(nombre: str | None) -> str | None:
    """La geografía que el nombre oficial del fondo declara, tal como aparece. `None` si el papel
    no es un fondo o si el nombre no nombra ninguna.

    `None` acá no es "invierte en todos lados": es **no sabemos**, y se muestra como faltante. Un
    fondo sectorial cuyo nombre no dice dónde compra (`The Technology Select Sector SPDR Fund`) cae
    ahí, y completarlo con "Estados Unidos" porque el SPDR sectorial sigue al S&P 500 sería inferir.

    Se compara **por palabra entera**, con el mismo cuidado que `es_fondo`: `NETFLIX` contiene
    `ETF`, y por la misma familia de bug `PetroChina` contiene `China`. Los `\\b` del patrón hacen
    ese trabajo, y el guardia de `es_fondo` hace el resto — una empresa no llega hasta acá.

    Un token negado no cuenta. `MSCI Emerging Markets ex China` nombra China para **excluirla**:
    devolver `China` sería decir exactamente lo contrario de lo que el nombre dice. Se saltea y
    sigue buscando, con lo cual ese nombre devuelve `Emerging Markets`, que es lo correcto.
    """
    if not es_fondo(nombre):
        return None
    texto = nombre or ""
    for patron, canonica in _REGIONES:
        for encontrado in patron.finditer(texto):
            if _NEGACION.search(texto[: encontrado.start()]):
                continue
            return canonica
    return None
