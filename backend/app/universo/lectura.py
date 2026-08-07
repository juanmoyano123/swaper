"""De dónde sale el universo: la vista `resumen`. Acá no se decide nada, sólo SQL.

Misma partición que en la consolidación —`persistencia.py` escribe lo que `armado.py` resolvió—:
esto lee, y toda la lógica que decide algo vive en `segmentacion.py` y `sanidad.py`, que se prueban
sin levantar Postgres.

**Se lee la vista y no las tablas** porque `resumen` ya resuelve lo único que acá sería fácil hacer
mal: quedarse con la fila de precios más reciente de cada ticker, entera y del mismo instante. Un
JOIN propio contra `precios` mezclaría métricas de capturas distintas en la misma fila.

Las columnas se piden por nombre y no con `SELECT *`. Hoy son diez: las cuatro que la sanidad
necesita, la clase de activo —que es lo que saca a la renta variable antes de segmentar— y las cinco
que F-011 agregó para decidir qué especie representa a una emisión: `duration` para el chequeo de
sanidad del colapso, y `maturity`, `law`, `couponCurrency` y `underlying` para medir completitud de
datos. **Falta `lastPrice` y `effectiveVolume`, que son de F-012**: son las dos puntas del cociente
del que sale el tipo de cambio implícito, y hasta que exista ese tipo de cambio el volumen crudo no
se puede comparar entre especies de distinta moneda. Agregar una columna acá es agregarla a
`COLUMNAS` y al `EspecieUniverso`; nada más de este módulo cambia.

Los identificadores van entrecomillados porque `couponCurrency` viene en camelCase de la fuente
original y sin comillas PostgreSQL lo plegaría a minúsculas y no encontraría la columna. Se
entrecomillan todos y no sólo ése: una regla que aplica a veces es una regla que alguien va a
olvidar cuando agregue la siguiente columna.
"""

from typing import Any

VISTA_UNIVERSO = "public.resumen"

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
)

_SELECT = ", ".join(f'"{columna}"' for columna in COLUMNAS)

SQL_UNIVERSO = f"SELECT {_SELECT} FROM {VISTA_UNIVERSO} ORDER BY ticker"


async def leer_universo(conn: Any) -> list[dict[str, Any]]:
    """El universo completo, tal como está en la base, sin filtrar ni derivar nada.

    Se trae entero y no paginado: son ~2.900 filas y las dos capas de sanidad son globales — la
    coherencia entre especies necesita ver todas las hermanas de una emisión a la vez, así que un
    universo traído de a pedazos daría un veredicto distinto por página.
    """
    filas = await conn.fetch(SQL_UNIVERSO)
    return [dict(fila) for fila in filas]
