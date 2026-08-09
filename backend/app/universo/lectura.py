"""De dónde sale el universo: la vista `resumen`. Acá no se decide nada, sólo SQL.

Misma partición que en la consolidación —`persistencia.py` escribe lo que `armado.py` resolvió—:
esto lee, y toda la lógica que decide algo vive en `segmentacion.py` y `sanidad.py`, que se prueban
sin levantar Postgres.

**Se lee la vista y no las tablas** porque `resumen` ya resuelve lo único que acá sería fácil hacer
mal: quedarse con la fila de precios más reciente de cada ticker, entera y del mismo instante. Un
JOIN propio contra `precios` mezclaría métricas de capturas distintas en la misma fila.

Las columnas se piden por nombre y no con `SELECT *`. Hoy son doce: las cuatro que la sanidad
necesita, la clase de activo —que es lo que saca a la renta variable antes de segmentar—, las cinco
que F-011 agregó para decidir qué especie representa a una emisión (`duration` para el chequeo de
sanidad del colapso, y `maturity`, `law`, `couponCurrency` y `underlying` para medir completitud de
datos) y las dos de F-012: `lastPrice` y `effectiveVolume`. El precio es la punta del cociente del
que sale el tipo de cambio implícito y el volumen es lo que ese tipo de cambio permite comparar
entre especies de distinta moneda. Agregar una columna de la vista es agregarla a `COLUMNAS` y al
`EspecieUniverso`; nada más de este módulo cambia.

## La moneda de cotización no está en la vista, y por eso hay un JOIN

F-012 necesita saber en qué moneda está el volumen de cada especie, y eso es
`instrumentos.moneda_cotizacion` — el `denominationCcy` que declara BYMA. **No está en la vista**:
F-007 la agregó a la tabla pero dejó el contrato de 21 columnas de `resumen` intacto a propósito,
para que el motor Python siguiera leyendo lo mismo. Meterla ahí sería tocar el esquema.

Así que se trae con un `LEFT JOIN` contra `instrumentos`, que es seguro por una razón concreta:
`instrumentos` tiene una fila por ticker y no es una serie temporal, así que unirla no reintroduce
el problema que la vista existe para resolver —mezclar métricas de capturas distintas en la misma
fila—, que sí aparecería si se unieran `precios` o `puntas`. Es `LEFT` y no `INNER` porque una
especie sin fila en `instrumentos` tiene que seguir apareciendo en el universo con la moneda vacía:
perderla del listado sería peor que no saber su moneda, y qué hacer con el faltante lo decide
`cambio.py`.

Los identificadores van entrecomillados porque `couponCurrency` viene en camelCase de la fuente
original y sin comillas PostgreSQL lo plegaría a minúsculas y no encontraría la columna. Se
entrecomillan todos y no sólo ése: una regla que aplica a veces es una regla que alguien va a
olvidar cuando agregue la siguiente columna.

## La lámina y el sector vienen de la tabla curada, no del universo

Base común de la tanda 8b (08/08/2026), para F-024 (redondeo por lámina) y F-017 (filtro por
sector). Los dos campos existen en `instrumentos`, pero ahí no sirven:

- **`instrumentos.lamina` está en `NULL` para todo el universo.** `armado.py` la escribe así a
  propósito —ninguna fuente de F-007 la publica— y nada la propaga después. La única fuente viva es
  `condiciones_emision`, el CSV curado que cargó F-009: 823 tickers, 568 con lámina. Leerla de
  `instrumentos` devolvería vacío siempre y haría creer que el dato no existe.
- **`instrumentos.sector` sólo distingue Soberano de Subsoberano**, que es lo que `SECTOR_POR_CLASE`
  deduce de la clase de activo. El sector de una ON —energía, banca, agro— está en la tabla curada.
  Por eso se lee con `COALESCE(ce.sector, i.sector)`: gana el curado, y el derivado de la clase
  queda de respaldo para los soberanos, que en la tabla curada no están.

El JOIN es `LEFT` por lo mismo que el de `instrumentos`: una especie sin condiciones curadas tiene
que seguir en el universo con los dos campos vacíos. Que falten es un dato —F-024 lo cuenta y lo
declara en pantalla— y perder la fila sería peor que no saber su lámina.

## La ley y el emisor también estaban en la tabla curada, y no llegaban

Agregado el 08/08/2026, después de ver el monitor mostrando `s/d` en la ley de AE38C mientras
`condiciones_emision` decía "Ley Argentina" con su origen y su fecha. La vista `resumen` lee esos
dos campos de `instrumentos`, donde IAMC sólo los cargó para las especies que publica: 592 de 1.477
con ley y 720 con emisor. Con el curado suben a **772 y 859**.

Las dos columnas viajan crudas y en paralelo a las de la vista porque las fuentes se comportan
distinto y hay que poder distinguirlo (`segmentacion.py` resuelve y `servicio.py` alerta):

- **La ley se contradice de frente en 4 emisiones** —PLC4, PN38, RC1C e YM39, doce especies contando
  sus hermanas—: una fuente dice Argentina y la otra N.Y. sobre el mismo papel. No hay forma de
  saber cuál tiene razón sin ir al prospecto, así que **queda vacía** y se alerta. Es la regla 11:
  elegir ganador sería inventar el dato más caro del universo, porque la ley es un eje del riesgo.
- **El emisor no se contradice, se escribe distinto**: 261 casos como `BANCO BBVA ARGENTINA S.A.`
  contra `Banco Bbva Argentina S.A`, o `BANCO PATAGONIA S.A.` contra `Banco Patagonia`. Son el mismo
  emisor con otra tipografía, y normalizar para compararlos —sacar puntos, decidir si `S.A.` y
  `S.A.U.` son lo mismo— sería exactamente la inferencia que la regla prohíbe. Así que el curado
  **sólo rellena huecos y nunca pisa**: donde la vista tiene emisor, gana la vista y no pasa nada.
  La divergencia de escritura se cuenta en una alerta informativa para que se vea que existe.

**La moneda de pago quedó afuera a propósito.** El curado dice `MEP` y `CCL` donde la vista dice
`USD`: no se contradicen, describen la misma cosa con distinto grano. Meter los cuatro valores en un
campo mezclaría dos vocabularios, y además `moneda_cupon` no se muestra en ninguna pantalla — la
ficha lee la moneda de pago de `/instrumentos/{ticker}/condiciones`, directo de la tabla curada y
con su origen.

**`calificacion` sí se suma acá, para F-031 (tanda 12).** `instrumentos.calificacion` está en
`NULL` para todo el universo —mismo caso que la lámina—: `armado.py` la escribe así porque ninguna
fuente de F-007 la publica. La única fuente viva es `condiciones_emision`, el CSV curado de F-009:
823 tickers, 359 con calificación (39 %). Viaja como texto libre, tal cual la declara la fuente
—`'AA(arg)'`, `'AAA (FIX)'`—: no hay escala canónica entre calificadoras y ordenarlas sería la
inferencia que la regla 11 prohíbe. El eje de crédito del vector de riesgo (F-031) es la pantalla
que faltaba.

**La lámina viaja como `float`.** En la base es `numeric`, y asyncpg devuelve eso como `Decimal`:
si llega así al contrato de la API, sale serializado como string y el frontend lo recibe como texto
donde espera un número. Ya pasó una vez con este mismo campo (commit `67ac5af`), y el mismo
`Decimal` hizo que una medición de F-051 diera cero durante media hora. El cast está en el SQL.
"""

from typing import Any

VISTA_UNIVERSO = "public.resumen"
TABLA_INSTRUMENTOS = "public.instrumentos"
TABLA_CONDICIONES = "public.condiciones_emision"

# Las columnas del universo que consume este paquete. `tir` y `tna` viajan las dos porque cuál de
# las dos mide a una especie lo decide su segmento, y el segmento se calcula después de leer.
COLUMNAS: tuple[str, ...] = (
    "ticker",
    "clase_activo",
    "tipo_tasa",
    "tir",
    "tna",
    # F-011: `duration` decide si un grupo de especies es de verdad la misma emisión, y las cuatro
    # que siguen deciden cuál de ellas la representa.
    "duration",
    "maturity",
    "law",
    "couponCurrency",
    "underlying",
    # F-012: las dos puntas de la comparación de liquidez. El precio deriva el tipo de cambio y el
    # volumen es lo que ese tipo de cambio hace comparable.
    "lastPrice",
    "effectiveVolume",
    # F-038: el monitor la muestra.
    "paridad",
    # Experimento data912: de dónde salió el precio de esta fila. La vista la expone desde
    # `20260808120000_data912_fuente_resumen.sql`; antes de esa migración `resumen` la descartaba.
    "fuente",
)

# Lo que la vista no tiene y hay que ir a buscar a la tabla. Ver el porqué en el docstring.
COLUMNAS_INSTRUMENTOS: tuple[str, ...] = ("moneda_cotizacion",)

# Las de la tabla curada de F-009, con su expresión completa: la lámina castea a float y el sector
# cae al derivado de la clase cuando el curado no lo tiene. El porqué está en el docstring.
#
# `ley` y `emisor` viajan **crudas de las dos fuentes** y no resueltas en SQL: quién gana lo decide
# `segmentacion.py`, que además puede nombrar los casos en conflicto para la alerta. Un `COALESCE`
# acá dejaría la contradicción invisible.
COLUMNAS_CURADAS: tuple[tuple[str, str], ...] = (
    ("lamina", "ce.lamina::float8"),
    ("sector", "COALESCE(ce.sector, i.sector)"),
    ("ley_curada", "ce.ley"),
    ("emisor_curado", "ce.underlying"),
    ("calificacion", "ce.calificacion"),
)

_SELECT = ", ".join(
    [f'u."{columna}"' for columna in COLUMNAS]
    + [f'i."{columna}"' for columna in COLUMNAS_INSTRUMENTOS]
    + [f'{expresion} AS "{columna}"' for columna, expresion in COLUMNAS_CURADAS]
)

SQL_UNIVERSO = (
    f"SELECT {_SELECT} FROM {VISTA_UNIVERSO} u "
    f"LEFT JOIN {TABLA_INSTRUMENTOS} i ON i.ticker = u.ticker "
    f"LEFT JOIN {TABLA_CONDICIONES} ce ON ce.ticker = u.ticker "
    "ORDER BY u.ticker"
)


async def leer_universo(conn: Any) -> list[dict[str, Any]]:
    """El universo completo, tal como está en la base, sin filtrar ni derivar nada.

    Se trae entero y no paginado: son ~2.900 filas y las dos capas de sanidad son globales — la
    coherencia entre especies necesita ver todas las hermanas de una emisión a la vez, así que un
    universo traído de a pedazos daría un veredicto distinto por página.
    """
    filas = await conn.fetch(SQL_UNIVERSO)
    return [dict(fila) for fila in filas]
