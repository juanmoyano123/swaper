"""Qué especies de renta variable son el mismo papel — CEDEARs en pesos, MEP y cable.

## Por qué esto no existía, y por qué existe ahora

`especies.py` documenta la decisión original: *"tampoco se deduce del sufijo del ticker: esa regla
es de especies de liquidación de renta fija y aplicarla a una acción sería completar por
analogía"*. Era la decisión correcta **con la evidencia de entonces**: nadie había verificado que
la C y la D significaran en un CEDEAR lo mismo que en un bono.

Ahora hay dos evidencias independientes, y por eso deja de ser una analogía:

1. **El dueño del producto lo declaró** (13/08/2026): `AAPLC` y `AAPLD` son el mismo CEDEAR de
   Apple cotizando en cable y en MEP.
2. **El precio lo demuestra.** Si son el mismo papel, el cociente entre el precio en pesos y el
   precio en dólares **tiene** que dar el tipo de cambio del mercado, y no puede dar otra cosa.
   Medido el 13/08/2026 con el implícito del universo en 1.527: `AAPL/AAPLD` = 1.522 (el MEP) y
   `AAPL/AAPLC` = 1.585 (cable, 3,9 % arriba por el canje). Lo mismo para `B`/`B.D`/`B.C`.

Ese segundo punto es el que hace que esto sea verificable y no una regla de strings: `verificar()`
contrasta cada grupo contra el tipo de cambio que F-012 deriva del propio universo, exactamente
como `universo/emisiones.py` contrasta las duraciones de un grupo de bonos antes de colapsarlo. El
criterio es el mismo del proyecto: **la raíz propone, un dato duro confirma, y ante la duda no se
fusiona.**

## Lo que el agrupamiento sí hace, y lo que deja afuera

Agrupa cuando la **única** diferencia entre dos tickers es el sufijo de moneda de liquidación —`C`
de cable, `D` de MEP—, con el punto contado como parte del sufijo: `B.C` y `B.D` son Barrick,
aunque difieran en dos caracteres. Todo lo demás queda separado, y en particular estos tres casos,
que se midieron y se decidieron uno por uno:

- **Los que terminan en `3` son papeles distintos, no variantes.** Lo dice la tabla oficial de
  CEDEARs de BYMA: `ABEV` cotiza sobre el ADR de NASDAQ con ratio 1:3 y `ABEV3` sobre la acción
  de B3 con ratio 1:1. Son la misma empresa y **distinto instrumento**; fusionarlos mezclaría dos
  papeles que no valen lo mismo. Son 7 (`ABEV3`, `VALE3`, `ITUB3`, `BBDC3`, `NAT3`, `RENT3`,
  `BBAS3`).
- **Los que terminan en `B` van a `NO_IDENTIFICADO`.** Se midió qué son y qué no son: se apilan
  *después* del sufijo de moneda y heredan su moneda (`XOM` → `XOMD` → `XOMDB` en USD, `GLD` →
  `GLDC` → `GLDCB` en EXT), así que **no son una moneda**; tienen el mismo plazo de liquidación
  que su base, así que **no son un plazo**; los publica BYMA y no data912; y de los 105 del
  universo **ninguno operó nunca**. Qué significa la letra, BYMA no lo documenta en ninguna parte
  —ni en su reglamento de listado ni en su newsroom— y **no se le inventa un significado**.
- **Un ticker propio que casualmente termina en C o D no es una variante.** `SAND` es Sandstorm
  Gold y `SAN` es Santander: la regla de strings los uniría y el contraste de precio los separa,
  porque el cociente entre dos empresas distintas no da el tipo de cambio. Es el caso que
  `verificar()` existe para atrapar.
"""

from dataclasses import dataclass

# Los sufijos de moneda de liquidación de un CEDEAR. `C` es cable y `D` es MEP — declarado por el
# dueño del producto y confirmado contra el tipo de cambio del universo (ver docstring del módulo).
SUFIJOS_DE_MONEDA: tuple[str, ...] = ("C", "D")

# El punto cuenta como parte del sufijo: BYMA publica `B.C` y `B.D` para Barrick, donde el ticker
# de origen ya trae el punto. Sin esto, esas especies quedan sueltas y el mismo papel se cuenta dos
# veces — que es el bug que este módulo vino a arreglar.
SEPARADOR_OPCIONAL = "."

# Largo mínimo del cuerpo del ticker una vez sacado el sufijo. Con menos que esto no queda ticker:
# es el mismo guardia que `ingesta/raiz.py` pone para no comerse la última letra de un ticker corto
# que termina en C o D por casualidad.
LARGO_MINIMO_CUERPO = 2

NO_IDENTIFICADO = "n/n"
"""Grupo de las especies que no se pudo identificar: hoy, las que terminan en `B`. No es un cajón
de sastre para lo que da trabajo — es el lugar declarado de lo que la fuente no explica, para que
se vea que existe en vez de esconderlo o de inventarle una categoría."""


@dataclass(frozen=True, slots=True)
class Agrupamiento:
    """A qué papel pertenece una especie, y en qué moneda de liquidación cotiza."""

    emision: str
    """El ticker del papel. Para una especie sin variantes es su propio ticker."""
    sufijo_liquidacion: str | None
    """`'C'` cable, `'D'` MEP, `None` la especie en pesos o sin variante."""
    no_identificado: bool = False
    """`True` cuando la especie cae en `NO_IDENTIFICADO` y no se puede afirmar qué es."""


def _termina_en_b(ticker: str) -> bool:
    """Las que terminan en B, con o sin sufijo de moneda antes: `AAPLB`, `XOMDB`, `GLDCB`."""
    return len(ticker) > LARGO_MINIMO_CUERPO and ticker.endswith("B")


def _partir(ticker: str) -> tuple[str, str | None]:
    """`AAPLD` → `('AAPL', 'D')`; `B.D` → `('B', 'D')`; `AAPL` → `('AAPL', None)`.

    **El punto cambia el guardia, y por eso hay dos ramas.** Sin punto no hay separador: `DD` puede
    ser DuPont o `D` en MEP, y sin nada que lo desambigüe se exige un cuerpo de al menos dos
    caracteres para no comerse la última letra de un ticker corto. Con punto el separador es
    explícito —lo puso la fuente—, así que un cuerpo de una sola letra es legítimo: `B.D` es
    Barrick en MEP, y `B` es un ticker de verdad (está en la tabla oficial de CEDEARs de BYMA).

    No consulta el universo: sólo dice cómo se lee el ticker. Si el cuerpo resultante existe de
    verdad como especie lo decide `agrupar`, y si además es el mismo papel lo confirma `verificar`.
    """
    if not ticker or ticker[-1] not in SUFIJOS_DE_MONEDA:
        return ticker, None

    cuerpo = ticker[:-1]
    if cuerpo.endswith(SEPARADOR_OPCIONAL):
        cuerpo = cuerpo[: -len(SEPARADOR_OPCIONAL)]
        # El punto ya marcó dónde termina el ticker: alcanza con que quede algo.
        return (cuerpo, ticker[-1]) if cuerpo else (ticker, None)

    if len(cuerpo) < LARGO_MINIMO_CUERPO:
        return ticker, None
    return cuerpo, ticker[-1]


def agrupar(tickers: set[str]) -> dict[str, Agrupamiento]:
    """A qué papel pertenece cada especie del universo.

    Una especie sólo se agrupa si el cuerpo que resulta de sacarle el sufijo **existe como especie
    propia** en el mismo universo: sin `AAPL` presente, `AAPLD` no se declara variante de nada.
    Eso es lo que evita partir un ticker que termina en C o D por casualidad, y lo que hace que el
    resultado dependa del universo del día y no de una lista fija.
    """
    resultado: dict[str, Agrupamiento] = {}
    for ticker in tickers:
        if _termina_en_b(ticker):
            resultado[ticker] = Agrupamiento(NO_IDENTIFICADO, None, no_identificado=True)
            continue
        cuerpo, sufijo = _partir(ticker)
        if sufijo is not None and cuerpo in tickers:
            resultado[ticker] = Agrupamiento(cuerpo, sufijo)
        else:
            resultado[ticker] = Agrupamiento(ticker, None)
    return resultado


def hermanas(agrupamiento: dict[str, Agrupamiento], ticker: str) -> list[str]:
    """Las otras especies del mismo papel, ordenadas. Vacío para un papel de una sola especie y
    **siempre vacío** para lo no identificado: no se puede afirmar que dos especies que no sabemos
    qué son sean hermanas entre sí."""
    propio = agrupamiento.get(ticker)
    if propio is None or propio.no_identificado:
        return []
    return sorted(
        t
        for t, a in agrupamiento.items()
        if t != ticker and not a.no_identificado and a.emision == propio.emision
    )


# --- El contraste contra el mercado ---------------------------------------------------------------
#
# Lo de arriba propone; esto confirma. Es el mismo reparto de roles que `universo/emisiones.py`,
# donde la raíz agrupa y la duración decide si el grupo se colapsa o no.

# Cuánto puede separarse el cociente del tipo de cambio antes de que el grupo deje de ser creíble.
# Medido sobre los 209 pares verificables del 13/08/2026: el 95 % cae por debajo del 2 % y ninguno
# pasa del 5 %. Se elige 2 % porque es donde cortan los datos, y porque 5 % ya se come el canje
# MEP/cable (~4 %) — con esa holgura una especie en cable podría pasar por MEP.
TOLERANCIA_TIPO_DE_CAMBIO = 0.02

# Cuánto está el cable por encima del MEP. No es un parámetro a calibrar: es el canje, y acá sólo
# se usa como techo de lo que se acepta como "cable creíble".
CANJE_MAXIMO = 0.12

CODIGO_GRUPO_SIN_CONFIRMAR = "grupo_renta_variable_sin_confirmar"


@dataclass(frozen=True, slots=True)
class Contraste:
    """Qué dijo el mercado sobre un grupo propuesto."""

    ticker: str
    emision: str
    cociente: float
    desvio: float
    """Diferencia relativa contra el tipo de cambio implícito. `0.02` es 2 %."""
    confirmado: bool


def verificar(
    agrupamiento: dict[str, Agrupamiento],
    precios: dict[str, float | None],
    monedas: dict[str, str | None],
    tipo_de_cambio: float | None,
) -> list[Contraste]:
    """Contrasta cada variante contra el tipo de cambio del universo.

    Sólo se puede contrastar lo que tiene las dos puntas con precio: la especie en pesos y la
    variante en otra moneda. Lo que no se puede medir **no se rechaza** —quedaría sin agrupar una
    especie que probablemente sí es hermana, y eso es peor que no decir nada— pero tampoco se
    reporta como confirmado: simplemente no aparece en esta lista, y el llamador sabe que el
    silencio no es una confirmación.

    Un `SAND` contra un `SAN` cae acá: son dos empresas distintas, su cociente no da el tipo de
    cambio, y el grupo se reporta sin confirmar en vez de fusionarse.
    """
    if not tipo_de_cambio:
        return []
    contrastes: list[Contraste] = []
    for ticker, grupo in agrupamiento.items():
        if grupo.sufijo_liquidacion is None or grupo.no_identificado:
            continue
        precio_variante = precios.get(ticker)
        precio_base = precios.get(grupo.emision)
        if not precio_variante or not precio_base or monedas.get(grupo.emision) != "ARS":
            continue
        cociente = precio_base / precio_variante
        desvio = (cociente - tipo_de_cambio) / tipo_de_cambio
        # El MEP cae sobre el implícito; el cable, por encima, hasta el canje. Por debajo del
        # implícito no hay lectura posible: sería un dólar más barato que el MEP.
        confirmado = abs(desvio) <= TOLERANCIA_TIPO_DE_CAMBIO or (
            TOLERANCIA_TIPO_DE_CAMBIO < desvio <= CANJE_MAXIMO
        )
        contrastes.append(Contraste(ticker, grupo.emision, cociente, desvio, confirmado))
    return contrastes


# Hasta dónde un cociente sigue pareciendo un tipo de cambio, aunque no sea el del día. Es el
# umbral que separa dos preguntas distintas: `BBD`/`BB` da 0,9 —Banco Bradesco contra Blackberry,
# eso no es un dólar ni por asomo— mientras que `MPD`/`MP` da 1.477 contra un implícito de 1.527,
# que es un dólar con el precio de una punta corrido. Lo primero se desagrupa; lo segundo se
# conserva y se alerta, porque desagrupar por un precio viejo volvería a partir un papel que sí es
# el mismo.
MARGEN_RECONOCIBLE = 0.20


def aplicar_contraste(
    agrupamiento: dict[str, Agrupamiento], contrastes: list[Contraste]
) -> tuple[dict[str, Agrupamiento], list[str]]:
    """Deshace los grupos que el mercado desmintió. Devuelve el agrupamiento corregido y los
    tickers que quedaron sólo alertados.

    Es el mismo criterio con que `universo/emisiones.py` no colapsa un grupo de bonos cuyas
    duraciones no coinciden: **ante la duda, no se fusiona**. La diferencia es que acá la duda tiene
    dos grados — un cociente que no se parece a ningún tipo de cambio desmiente el grupo, y uno que
    se le parece pero no da exacto sólo lo pone en duda.
    """
    corregido = dict(agrupamiento)
    alertados: list[str] = []
    for contraste in contrastes:
        if contraste.confirmado:
            continue
        if abs(contraste.desvio) > MARGEN_RECONOCIBLE:
            # No es un tipo de cambio: son dos papeles distintos que comparten prefijo.
            corregido[contraste.ticker] = Agrupamiento(contraste.ticker, None)
        else:
            alertados.append(contraste.ticker)
    return corregido, alertados
