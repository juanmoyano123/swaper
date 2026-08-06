"""Qué es cada especie: clase de activo y tipo de tasa, siempre desde algo que una fuente declaró.

Las dos columnas que definen si un instrumento llega al armador —`clase_activo` y `tipo_tasa`— no
las publica ninguna fuente con ese nombre. Se derivan de dos declaraciones distintas y por eso hay
dos caminos:

**El endpoint de BYMA declara la clase para tres de los cuatro grupos.** `negociable-obligations`
son ONs, `cedears` son CEDEARs, `general-equity` y `leading-equity` son acciones. No hay
interpretación: la fuente separó las especies en esos endpoints.

**`public-bonds` mezcla soberanos y subsoberanos y BYMA no los distingue.** Verificado el
06/08/2026 contra la fuente: `securitySubType` vale 'B' en las 1106 filas y `market` vale 'BYMA' en
todas, así que ninguno de los dos sirve para separar un bono del Tesoro de uno de la Provincia de
Buenos Aires. Lo que sí lo declara es el `type` del cronograma de Docta —el submarket de la
emisión, una de las nueve columnas contractuales que el consolidador ya persiste—, cruzado por raíz
de ticker. Ese mismo `type` es la única fuente de `tipo_tasa` para toda la renta fija.

Una especie de `public-bonds` sin cronograma no entra al universo. No es una pérdida: `clase_activo`
es NOT NULL y elegirle una clase sería inventar el dato que la separa. El motor viejo hacía lo
mismo (descartaba las filas de clase nula) y el consolidado histórico tampoco las tenía; lo que se
descarta acá son las especies X/Y/Z que BYMA publica y el producto nunca consideró. Sus puntas se
guardan igual, porque `puntas` no tiene FK justamente para no perder ese dato.
"""

from app.ingesta.alertas import Alerta, Severidad

# Portado literal de tools/consolidar_universo.py:62-85. Verificado el 06/08/2026 contra el feed:
# las 6150 filas del cronograma traen 19 valores distintos de `type` y los 19 están acá; ninguna
# raíz declara dos tipos distintos. Si algún día aparece uno nuevo, la fila se alerta y se descarta
# en vez de mapearse por parecido.
SUBMARKET_MAP: dict[str, tuple[str, str | None]] = {
    "HARD_DOLLAR": ("bono_soberano", "hard-dollar"),
    "FIXED_RATE": ("bono_soberano", "tasa-fija"),
    "CER": ("bono_soberano", "cer"),
    "DOLLAR_LINKED": ("bono_soberano", "dollar-linked"),
    "BADLAR": ("bono_soberano", "badlar"),
    "TAMAR": ("bono_soberano", "tamar"),
    "BOPREAL": ("bono_soberano", "bopreal"),
    "ON": ("on_corporativo", "hard-dollar"),
    "ON_FIXED_RATE": ("on_corporativo", "tasa-fija"),
    "ON_CER": ("on_corporativo", "cer"),
    "ON_UVA": ("on_corporativo", "cer"),  # UVA y CER son el mismo casillero con otro nombre
    "ON_BADLAR": ("on_corporativo", "badlar"),
    "ON_TAMAR": ("on_corporativo", "tamar"),
    "ON_DOLLAR_LINKED": ("on_corporativo", "dollar-linked"),
    "SUB_SOBERANO": ("bono_subsoberano", "hard-dollar"),
    "SUB_SOBERANO_FIXED_RATE": ("bono_subsoberano", "tasa-fija"),
    "SUB_SOBERANO_CER": ("bono_subsoberano", "cer"),
    "SUB_SOBERANO_BADLAR": ("bono_subsoberano", "badlar"),
    "SUB_SOBERANO_TAMAR": ("bono_subsoberano", "tamar"),
    "SUB_SOBERANO_DOLLAR_LINKED": ("bono_subsoberano", "dollar-linked"),
    "STOCK": ("accion", None),
    "CEDEAR": ("cedear", None),
}

# Los endpoints que declaran la clase por sí solos. `public-bonds` no está: es el que necesita el
# cronograma. Acciones y CEDEARs entran con tipo_tasa None a propósito —no tienen tasa—, y ese None
# es lo que hace que `asignar_segmento()` los deje afuera del armador y del swaper.
CLASE_POR_ENDPOINT: dict[str, str] = {
    "negociable-obligations": "on_corporativo",
    "cedears": "cedear",
    "general-equity": "accion",
    "leading-equity": "accion",
}

ENDPOINT_SIN_CLASE_PROPIA = "public-bonds"

CODIGO_CLASE_SIN_MAPEO = "clase_sin_mapeo"
CODIGO_CLASE_DISCREPANTE = "clase_discrepante"

SECTOR_POR_CLASE = {"bono_soberano": "Soberano", "bono_subsoberano": "Subsoberano"}
EMISOR_SOBERANO = "Gobierno Argentino"


def clasificar(endpoint: str, tipo_cronograma: str | None) -> tuple[str, str | None] | None:
    """Clase de activo y tipo de tasa de una especie, o `None` si no se puede saber sin inventar.

    `tipo_cronograma` es el `type` que el cashflow de Docta declara para la raíz de esta especie.
    Para los endpoints que ya declaran la clase sólo aporta el tipo de tasa; para `public-bonds` es
    la única forma de saber si el emisor es el Tesoro o una provincia.
    """
    del_cronograma = SUBMARKET_MAP.get(tipo_cronograma) if tipo_cronograma else None

    if endpoint == ENDPOINT_SIN_CLASE_PROPIA:
        return del_cronograma

    clase = CLASE_POR_ENDPOINT.get(endpoint)
    if clase is None:
        return None
    # El endpoint manda sobre el cronograma: es la fuente declarada de "especies". El cronograma
    # sólo completa el tipo de tasa, y sólo si acuerda con la clase que el endpoint declaró.
    tipo_tasa = del_cronograma[1] if del_cronograma and del_cronograma[0] == clase else None
    return clase, tipo_tasa


def hay_discrepancia(endpoint: str, tipo_cronograma: str | None) -> bool:
    """El endpoint dice una clase y el cronograma otra. Se declara; el endpoint gana igual."""
    if endpoint == ENDPOINT_SIN_CLASE_PROPIA or not tipo_cronograma:
        return False
    del_cronograma = SUBMARKET_MAP.get(tipo_cronograma)
    return bool(del_cronograma) and del_cronograma[0] != CLASE_POR_ENDPOINT.get(endpoint)


def subtipo_de(tipo_tasa: str | None, law: str | None) -> str | None:
    """Global o bonar: la misma derivación del motor viejo, sobre hard-dollar y por ley.

    Devuelve `None` mientras no haya ley, que en F-007 es casi siempre: la ley llega por IAMC, que
    cubre 242 emisiones. F-009 va a sembrar el resto desde el CSV curado y tiene que re-derivar
    esta columna cuando lo haga.
    """
    if tipo_tasa != "hard-dollar" or not law:
        return None
    if "N.Y" in law:
        return "global"
    if "Argentina" in law:
        return "bonar"
    return None


def clase_sin_mapeo(tipos: dict[str, int], especies: int) -> Alerta:
    """Especies de `public-bonds` que no entran al universo por no tener cronograma conocido."""
    detalle_tipos = ", ".join(f"{t or 'sin cronograma'}: {n}" for t, n in sorted(tipos.items()))
    return Alerta(
        codigo=CODIGO_CLASE_SIN_MAPEO,
        mensaje=(
            f"{especies} especies de public-bonds quedaron fuera del universo por no poder "
            f"determinar su clase de activo ({detalle_tipos}). Sus puntas se guardaron igual."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"especies": especies, "tipos": tipos},
    )


def clase_discrepante(casos: list[tuple[str, str]]) -> Alerta:
    """El endpoint y el cronograma no coinciden. Gana el endpoint y la contradicción se declara."""
    muestra = ", ".join(f"{ticker} ({tipo})" for ticker, tipo in casos[:5])
    return Alerta(
        codigo=CODIGO_CLASE_DISCREPANTE,
        mensaje=(
            f"{len(casos)} especies cuyo endpoint de BYMA y cuyo cronograma de Docta declaran "
            f"clases distintas ({muestra}). Se conservó la del endpoint."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"total": len(casos), "muestra": [list(c) for c in casos[:20]]},
    )
