"""Barrido de emisores contra la ficha técnica de BYMA — 28/08/2026.

De las 4.761 filas de `instrumentos`, 742 tienen emisor. Las dos fuentes que lo traían se apagaron
—el CSV curado de F-009 no tiene origen vivo, la ingesta de IAMC se eliminó el 26/08/2026— y un
instrumento cuyo emisor no se conoce no se puede analizar. La ficha técnica lo publica por especie
(`app/externos/byma_ficha.py`), un POST por símbolo.

Incremental, igual que `app/renta_variable/clasificacion.py`: hasta `limite` especies por corrida,
persistidas **una por una**, retomando donde quedó. Un corte a mitad de tanda no pierde lo que ya
se trajo, y `ficha_consultada_en` es lo que hace que los pendientes bajen aunque la fuente no tenga
nada que decir de esa especie.

## La precedencia: curado > ficha BYMA > Bolsar > vacío declarado

Y se implementa **por exclusión, no por orden de escritura**, que es la parte contraintuitiva.

En lectura, `_resolver_emisor` de `app/universo/segmentacion.py` hace que **la vista gane y el
curado sólo rellene**: si `instrumentos.underlying` tiene algo, eso es lo que se muestra. Entonces
escribir el emisor de la ficha en una especie que el curado ya cubre no la "completaría": la
**pisaría** en pantalla, invirtiendo la precedencia declarada. Por eso `pendientes_de_ficha()`
excluye con un LEFT JOIN contra `condiciones_emision` lo que el curado ya tiene, y por eso cada
campo se decide por separado (`falta_emisor`, `falta_ley`): una especie puede entrar a la tanda
porque le falta la ley y aun así tener el emisor cubierto por el curado.

Con la ley el daño sería peor todavía. `_resolver_ley` **vacía** el dato cuando las dos fuentes se
contradicen —es el eje de riesgo que decide en qué tribunal se cobra—, así que escribir una ley
donde el curado ya declara otra no dejaría dos opiniones: dejaría la celda en blanco.

## La ley: tabla de equivalencias literal, y por qué le falta una entrada

`LEY_POR_VALOR_DE_FICHA` mapea los valores **exactos** que la ficha declara al vocabulario cerrado
del CHECK de la columna. Todo valor que no esté en la tabla queda en `None` y **se cuenta**; nunca
se mapea por parecido. El antecedente está en `CLAUDE.md`: traducir un código de la fuente a "Ley
Inglesa" —una categoría que no existe— costó una reversión.

Medido el 28/08/2026 sobre las 915 fichas de renta fija que la fuente publica, `ley` toma tres
valores: `''` (724), `'Nacional'` (155) y `'Extranjera'` (36).

**`'Nacional'` se mapea a `'Ley Argentina'`.** En un campo llamado `ley` de la ficha que publica el
mercado argentino, "nacional" designa una única legislación, y el vocabulario cerrado tiene un solo
miembro para ella. No queda ambigüedad que resolver. Corroborado además contra el dato curado: 42
especies tienen las dos declaraciones y las 42 coinciden, sin una sola contradicción. El campo
`paisLey` viene vacío en los 155 casos, así que nada apunta a otra jurisdicción.

**`'Extranjera'` NO se mapea, y no es prudencia: mapearlo escribiría un dato falso.** "Extranjera"
nombra un conjunto —todo lo que no es la ley local—, y el vocabulario cerrado sólo tiene `'Ley
N.Y.'`. Elegir ese miembro sería decidir por la fuente. El campo `paisLey`, que es el único que
podría desambiguar, lo confirma: en los 36 casos toma **19 grafías distintas de texto libre**, y
entre ellas hay al menos ocho que no son ley de Nueva York —`'Inglaterra'` (BDC36) y siete de ley
mixta, `'ESTADO N.YORK (USA) Y LEY ARGENTINA'`, `'EST. N. YORK USA  Y LEY OBLIG. ARGENTINA'`,
`'LEY ARGENTINA Y LEY N.Y. (USA)'`—. Es el 22 % de los casos: la traducción por parecido habría
etiquetado un bono de ley inglesa como Ley N.Y. `paisLey` tampoco sirve como fuente propia
—diecinueve grafías para tres jurisdicciones no son un vocabulario—, así que estas 36 especies
quedan con la ley vacía, contadas en `ley_fuera_de_vocabulario`, y su ley sigue esperando una
fuente que la declare.

## Renta variable: la ficha declara al banco depositario, y eso es lo que se escribe

Para un CEDEAR, el campo `emisor` de la ficha trae **quién emitió el certificado**, no la empresa
subyacente: medido el 28/08/2026 sobre 116 fichas de CEDEAR, `'BANCO COMAFI S.A.'` en 107 y
`'Caja de Valores S.A.'` en 9. La empresa viene en `denominacion` (`'APPLE INC.'`), así que las dos
columnas juntas dicen la verdad completa.

Se escribe tal cual y no se descarta, porque descartarlo sería decidir que el campo `emisor` de la
fuente "no aplica" a esta clase, que es justo la interpretación que la regla 11 prohíbe. Pero
conviene saber cómo se va a ver: los ~1.280 CEDEARs del universo van a mostrar dos emisores
distintos entre todos. **No afecta ningún cálculo** — `app/concentracion/riesgo.py` agrupa por el
prefijo del ticker y nunca por este campo (ver su docstring: el nombre del emisor es sólo para
mostrar)—. Para las acciones no hay ambigüedad: el emisor de la acción es la empresa
(`A3 → 'A3 MERCADOS S.A.'`).

## Herencia por raíz

Emisor y ley son atributos de **la emisión**, no de la especie de liquidación: AL30, AL30D y AL30C
son el mismo bono. Una especie sin ficha hereda de una hermana con ficha de la misma
`raiz_emision()`. La raíz sale siempre de esa función y nunca se reconstruye a mano — el
antecedente de los 121 tickers inventados está documentado en `app/ingesta/raiz.py`.

Se hereda sólo cuando las hermanas que declaran **coinciden entre sí**. Medido el 28/08/2026 no hay
una sola raíz con dos emisores distintos, así que la guarda no descarta nada hoy; existe para que
el día que la fuente se contradiga el resultado sea una celda vacía y no la primera hermana que el
orden haya puesto adelante.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from app.externos.bolsar import emisor_bolsar
from app.externos.byma_ficha import FichaEspecie, traer_fichas
from app.ingesta.consolidacion.clasificacion import subtipo_de
from app.ingesta.http import crear_cliente
from app.ingesta.raiz import raiz_emision

logger = structlog.get_logger()

FUENTE = "BYMA ficha técnica"

# Cuántas especies procesa una corrida. La fuente no limita por cuota —28/08/2026: 915 fichas
# seguidas con concurrencia 10 sin un solo 429—, así que lo que acota es cuánto puede tardar un
# solo POST del endpoint, no lo que la fuente tolera.
LIMITE_POR_CORRIDA = 500

# Pausa entre pedidos a Bolsar. Es scraping de un sitio que no publica límite de ritmo y el
# fallback corre sobre pocas especies: se va despacio a propósito.
PAUSA_BOLSAR_SEGUNDOS = 0.5

# Sufijo de las especies por las que Bolsar responde. Medido el 28/08/2026 sobre 99 tickers: 50 de
# 50 de las `O`, 0 de 49 de las `C`/`D`. Pedirle por las otras es gastar un pedido para nada.
SUFIJO_CON_PAGINA_EN_BOLSAR = "O"

# Los valores **exactos** de `ley` que la ficha declara y su equivalente en el vocabulario cerrado
# del CHECK de `instrumentos.law`. Falta `'Extranjera'` a propósito: el docstring del módulo tiene
# la medición que lo justifica. No agregar entradas sin medir antes contra la fuente.
LEY_POR_VALOR_DE_FICHA: dict[str, str] = {
    "Nacional": "Ley Argentina",
}


@dataclass(frozen=True, slots=True)
class ResumenBarrido:
    """Lo que la corrida trajo, abierto por origen para poder auditar de dónde salió cada dato."""

    pendientes: int
    procesados: int
    """Especies que la fuente contestó. Las que fallaron no cuentan: no se les preguntó de verdad
    y no quedan marcadas como consultadas."""
    con_emisor: int
    con_ley: int
    ley_fuera_de_vocabulario: int
    """La ficha declaró una ley que la tabla de equivalencias no cubre: queda vacía y contada,
    nunca traducida por parecido."""
    heredados_por_raiz: int
    via_bolsar: int
    sin_dato: int
    """Se preguntó y no vino ni emisor ni ley. Queda declarado con `ficha_consultada_en`."""

    def como_dict(self) -> dict[str, object]:
        return {
            "pendientes": self.pendientes,
            "procesados": self.procesados,
            "con_emisor": self.con_emisor,
            "con_ley": self.con_ley,
            "ley_fuera_de_vocabulario": self.ley_fuera_de_vocabulario,
            "heredados_por_raiz": self.heredados_por_raiz,
            "via_bolsar": self.via_bolsar,
            "sin_dato": self.sin_dato,
        }


SQL_PENDIENTES = """
    SELECT
        i.ticker,
        i.tipo_tasa,
        i.law,
        (i.underlying IS NULL AND ce.underlying IS NULL) AS falta_emisor,
        (i.law IS NULL AND ce.ley IS NULL)               AS falta_ley
    FROM public.instrumentos i
    LEFT JOIN public.condiciones_emision ce ON ce.ticker = i.ticker
    WHERE i.ficha_consultada_en IS NULL
      AND ((i.underlying IS NULL AND ce.underlying IS NULL)
        OR (i.law IS NULL AND ce.ley IS NULL))
    ORDER BY i.ticker
"""

# `COALESCE` en cada columna: el barrido **rellena y nunca pisa**. Es la segunda mitad de la
# precedencia —la primera es el LEFT JOIN de `SQL_PENDIENTES`, que deja afuera lo que el curado
# cubre—, y las dos hacen falta: entre que se leyeron los pendientes y que se escribe la tanda,
# otra corrida pudo haber escrito la misma fila.
SQL_GUARDAR = """
    UPDATE public.instrumentos SET
        underlying          = COALESCE(underlying, $2),
        law                 = COALESCE(law, $3),
        denominacion        = COALESCE(denominacion, $4),
        subtipo             = COALESCE(subtipo, $5),
        ficha_consultada_en = $6
    WHERE ticker = $1
"""


async def pendientes_de_ficha(conn: Any) -> list[dict[str, Any]]:
    """Las especies a las que todavía no se les preguntó y a las que les falta emisor o ley.

    Devuelve `ticker`, `tipo_tasa`, `law` y qué falta de verdad (`falta_emisor`, `falta_ley`), con
    "falta" medido sobre el dato **efectivo**: si el curado lo cubre, no falta, aunque la columna
    de `instrumentos` esté vacía. Esa distinción es la que sostiene la precedencia (ver el
    docstring del módulo).
    """
    filas = await conn.fetch(SQL_PENDIENTES)
    return [dict(fila) for fila in filas]


async def completar_emisores(
    conn: Any,
    *,
    limite: int = LIMITE_POR_CORRIDA,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
    cliente_bolsar: httpx.AsyncClient | None = None,
) -> ResumenBarrido:
    """Trae la ficha de hasta `limite` especies pendientes y escribe lo que la fuente declare."""
    pendientes = await pendientes_de_ficha(conn)
    tanda = pendientes[:limite]
    if not tanda:
        return ResumenBarrido(0, 0, 0, 0, 0, 0, 0, 0)

    fichas = await traer_fichas([str(fila["ticker"]) for fila in tanda], dormir=dormir)
    por_raiz = _declarado_por_raiz(fichas)

    momento = ahora()
    con_emisor = con_ley = fuera_de_vocabulario = heredados = via_bolsar = sin_dato = 0
    procesados = 0
    cliente = cliente_bolsar

    try:
        for fila in tanda:
            ticker = str(fila["ticker"])
            if ticker not in fichas:
                # La fuente no contestó por ésta. No se la marca como consultada: volver a
                # preguntar es correcto, y marcarla convertiría un corte de red en un faltante
                # definitivo.
                continue
            procesados += 1

            ficha = fichas[ticker]
            emisor = ficha.emisor if ficha else None
            ley_cruda = ficha.ley_cruda if ficha else None

            heredado = False
            if emisor is None or ley_cruda is None:
                de_hermanas = por_raiz.get(raiz_emision(ticker))
                if de_hermanas is not None:
                    if emisor is None and de_hermanas.emisor is not None:
                        emisor, heredado = de_hermanas.emisor, True
                    if ley_cruda is None and de_hermanas.ley_cruda is not None:
                        ley_cruda, heredado = de_hermanas.ley_cruda, True
            if heredado:
                heredados += 1

            ley = LEY_POR_VALOR_DE_FICHA.get(ley_cruda) if ley_cruda else None
            if ley_cruda is not None and ley is None:
                fuera_de_vocabulario += 1
                logger.info("ficha_ley_fuera_de_vocabulario", ticker=ticker, ley=ley_cruda)

            if emisor is None and ticker.endswith(SUFIJO_CON_PAGINA_EN_BOLSAR):
                if cliente is None:
                    cliente = crear_cliente()
                emisor = await emisor_bolsar(cliente, ticker)
                if emisor is not None:
                    via_bolsar += 1
                await dormir(PAUSA_BOLSAR_SEGUNDOS)

            # Cada campo se ofrece sólo si de verdad falta: lo que el curado ya cubre no se toca,
            # ni siquiera para escribir el mismo valor (ver el docstring del módulo).
            emisor_a_escribir = emisor if fila["falta_emisor"] else None
            ley_a_escribir = ley if fila["falta_ley"] else None

            if emisor_a_escribir is not None:
                con_emisor += 1
            if ley_a_escribir is not None:
                con_ley += 1
            if emisor_a_escribir is None and ley_a_escribir is None:
                sin_dato += 1

            await _guardar(
                conn,
                ticker,
                emisor=emisor_a_escribir,
                ley=ley_a_escribir,
                denominacion=ficha.denominacion if ficha else None,
                # El subtipo se deriva **sólo de la ley que esta corrida escribe**. Si la ley vino
                # del curado, quien la re-deriva es F-009, que es su dueño; hacerlo también acá
                # sería tener dos lugares escribiendo la misma columna desde el mismo dato.
                subtipo=subtipo_de(_texto(fila["tipo_tasa"]), ley_a_escribir),
                consultada_en=momento,
            )
    finally:
        if cliente is not None and cliente_bolsar is None:
            await cliente.aclose()

    return ResumenBarrido(
        pendientes=len(pendientes),
        procesados=procesados,
        con_emisor=con_emisor,
        con_ley=con_ley,
        ley_fuera_de_vocabulario=fuera_de_vocabulario,
        heredados_por_raiz=heredados,
        via_bolsar=via_bolsar,
        sin_dato=sin_dato,
    )


@dataclass(frozen=True, slots=True)
class _DeclaradoPorRaiz:
    """Lo que las hermanas de una emisión declaran, cuando declaran todas lo mismo."""

    emisor: str | None
    ley_cruda: str | None


def _declarado_por_raiz(
    fichas: dict[str, FichaEspecie | None],
) -> dict[str, _DeclaradoPorRaiz]:
    """Emisor y ley por raíz de emisión, y `None` en el campo donde las hermanas no coincidan.

    La raíz sale de `raiz_emision()` y de ningún otro lado: cortar el ticker con una regla propia
    es lo que produjo 121 tickers inexistentes (ver `app/ingesta/raiz.py`).
    """
    emisores: dict[str, set[str]] = {}
    leyes: dict[str, set[str]] = {}
    for ticker, ficha in fichas.items():
        if ficha is None:
            continue
        raiz = raiz_emision(ticker)
        if ficha.emisor is not None:
            emisores.setdefault(raiz, set()).add(ficha.emisor)
        if ficha.ley_cruda is not None:
            leyes.setdefault(raiz, set()).add(ficha.ley_cruda)

    def unico(valores: set[str] | None) -> str | None:
        return next(iter(valores)) if valores is not None and len(valores) == 1 else None

    return {
        raiz: _DeclaradoPorRaiz(emisor=unico(emisores.get(raiz)), ley_cruda=unico(leyes.get(raiz)))
        for raiz in emisores.keys() | leyes.keys()
    }


async def _guardar(
    conn: Any,
    ticker: str,
    *,
    emisor: str | None,
    ley: str | None,
    denominacion: str | None,
    subtipo: str | None,
    consultada_en: datetime,
) -> None:
    """Una especie, una escritura. De a una y no en lote a propósito: un corte a mitad de tanda
    conserva todo lo anterior, que es lo que hace que el job sea reanudable de verdad."""
    await conn.execute(SQL_GUARDAR, ticker, emisor, ley, denominacion, subtipo, consultada_en)


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    limpio = str(valor).strip()
    return limpio or None
