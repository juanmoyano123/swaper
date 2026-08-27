"""Escribe lo que `armado.py` resolvió. Acá no se decide nada: sólo SQL.

Es el primer escritor del backend, así que fija tres convenciones que las features siguientes
heredan:

**Un `capturado_en` por corrida, no por fila.** `precios` y `puntas` son series temporales con PK
`(ticker, capturado_en)`, y la vista `resumen` arma cada fila del universo tomando la fila de
precios más reciente de cada ticker. Si cada INSERT llevara su propio `now()`, dos especies de la
misma corrida quedarían en instantes distintos por milisegundos: la vista seguiría funcionando,
pero `max(capturado_en)` —lo que `health.py` reporta como "dato de las HH:MM"— dejaría de nombrar
una corrida y pasaría a nombrar la última fila que se escribió.

**`instrumentos` se actualiza sin pisar con nulos.** El `DO UPDATE` usa
`COALESCE(EXCLUDED.col, instrumentos.col)`, así que una corrida que no trae la ley ni la moneda de
pago las deja como estaban en vez de vaciarlas. Es lo que F-008 necesita para correr refrescos
intradiarios que sólo tocan BYMA sin degradar el universo en cada pasada, y desde que se eliminó
IAMC (26/08/2026) es lo único que sostiene esos atributos: ninguna corrida vuelve a escribirlos, y
el COALESCE es lo que hace que la eliminación borre código sin borrar dato.

**Cada bloque tiene su transacción.** Si el cronograma falla a mitad de escritura, los precios y
las puntas de esa corrida quedan igual. Una sola transacción para todo convertiría cualquier
problema puntual en "no se guardó nada", que es peor que guardar una parte y decir cuál falta.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

from app.ingesta.alertas import Alerta, Severidad
from app.ingesta.consolidacion.armado import COLUMNAS_CASHFLOW, Consolidacion

logger = structlog.get_logger()

CODIGO_ESCRITURA_FALLIDA = "escritura_fallida"
CODIGO_PODA_FALLIDA = "poda_snapshots_fallida"

COLUMNAS_INSTRUMENTOS: tuple[str, ...] = (
    "ticker",
    "clase_activo",
    "tipo_tasa",
    "subtipo",
    "underlying",
    "sector",
    "maturity",
    "law",
    "coupon_currency",
    "lamina",
    "calificacion",
    "revisar",
    "duplicado",
    "archivo_origen",
    "estructura_cupon",
    "moneda_cotizacion",
    "plazo_liquidacion",
)

# Las que el upsert NO protege con COALESCE. `ticker` es la clave; `revisar` y `duplicado` son
# NOT NULL y se recalculan enteras en cada corrida, así que conservar el valor viejo dejaría
# marcada para siempre una emisión que ya dejó de estar en conflicto.
SIN_COALESCE = frozenset({"ticker", "revisar", "duplicado"})

COLUMNAS_PRECIOS: tuple[str, ...] = (
    "ticker",
    "capturado_en",
    "last_price",
    "tir",
    "tna",
    "duration",
    "paridad",
    "convexidad",
    "residual_value",
    "effective_volume",
    "fuente",
    "fecha_metricas",
    "cierre_anterior",
    "precio_apertura",
    "precio_maximo",
    "precio_minimo",
    "vwap",
    "valor_tecnico",
)

# El cronograma que ya está persistido. Desde que se dio de baja Docta (12/08/2026) ninguna fuente
# publica cronogramas, así que esta lectura dejó de ser el respaldo y pasó a ser el camino único:
# el flujo contractual de toda corrida sale de acá. Son las nueve columnas de `COLUMNAS_CASHFLOW`
# porque de acá salen tanto la clasificación por submarket como las métricas propias de F-051:
# leer sólo `ticker` y `type` alcanzaba para clasificar, pero dejaría sin flujo al descuento y las
# métricas se vaciarían en cada corrida.
SQL_CRONOGRAMA_PERSISTIDO = """
SELECT ticker, type, issue_date, payment_date, capital, interest_rate,
       interest_amount, residual_value, cash_flow
  FROM public.cashflow
 ORDER BY ticker, payment_date
"""


async def leer_cronograma(conn: Any) -> list[dict[str, object]]:
    """El cashflow persistido, en la forma que espera `indexar_cronograma`."""
    filas = await conn.fetch(SQL_CRONOGRAMA_PERSISTIDO)
    return [dict(fila) for fila in filas]


# Experimento data912: la moneda de cotización que BYMA ya declaró alguna vez, para los tickers
# que en esta corrida sólo trae data912 (que no declara moneda). No es un dato nuevo, es un
# atributo estable de la especie, así que leerlo de acá no inventa nada (regla 1).
SQL_MONEDAS = """
SELECT ticker, moneda_cotizacion
  FROM public.instrumentos
 WHERE moneda_cotizacion IS NOT NULL
"""


async def leer_monedas(conn: Any) -> dict[str, str]:
    """Última moneda de cotización conocida, por ticker. Vacío si `instrumentos` está vacía."""
    filas = await conn.fetch(SQL_MONEDAS)
    return {fila["ticker"]: fila["moneda_cotizacion"] for fila in filas}


COLUMNAS_PUNTAS: tuple[str, ...] = (
    "ticker",
    "capturado_en",
    "px_bid",
    "px_ask",
    "operaciones",
    "fuente",
)

# Los ~13.600 upserts de una corrida (4.389 instrumentos + 4.389 precios + 4.855 puntas, medido el
# 27/08/2026, cuando el cliente empezó a pedirle a BYMA el panel completo) entran en el
# command_timeout de 30 s del pool porque se trocean: un lote gigante mantiene una sola sentencia
# abierta el tiempo entero y cualquier hipo de red la pierde completa.
TAMANO_LOTE = 1000


@dataclass(frozen=True, slots=True)
class Escritura:
    """Cuántas filas quedaron en cada tabla y qué falló. Nunca lanza: los fallos son datos."""

    filas_por_tabla: dict[str, int] = field(default_factory=dict)
    alertas: list[Alerta] = field(default_factory=list)


def _marcadores(columnas: Sequence[str], desde: int = 1) -> str:
    return ", ".join(f"${i}" for i in range(desde, desde + len(columnas)))


def sql_instrumentos() -> str:
    asignaciones = ", ".join(
        f"{col} = COALESCE(EXCLUDED.{col}, public.instrumentos.{col})"
        for col in COLUMNAS_INSTRUMENTOS
        if col not in SIN_COALESCE
    )
    directas = ", ".join(
        f"{col} = EXCLUDED.{col}"
        for col in COLUMNAS_INSTRUMENTOS
        if col in SIN_COALESCE - {"ticker"}
    )
    return (
        f"INSERT INTO public.instrumentos ({', '.join(COLUMNAS_INSTRUMENTOS)}) "
        f"VALUES ({_marcadores(COLUMNAS_INSTRUMENTOS)}) "
        f"ON CONFLICT (ticker) DO UPDATE SET {asignaciones}, {directas}, actualizado_en = now()"
    )


def sql_precios() -> str:
    return (
        f"INSERT INTO public.precios ({', '.join(COLUMNAS_PRECIOS)}) "
        f"VALUES ({_marcadores(COLUMNAS_PRECIOS)})"
    )


def sql_puntas() -> str:
    return (
        f"INSERT INTO public.puntas ({', '.join(COLUMNAS_PUNTAS)}) "
        f"VALUES ({_marcadores(COLUMNAS_PUNTAS)})"
    )


def sql_poda(tabla: str) -> str:
    """Borra de `tabla` todo lo anterior a la fila más reciente **de cada ticker**.

    La correlación `q.ticker = p.ticker` es la feature entera, no un detalle de estilo. La versión
    ingenua —comparar contra el `max(capturado_en)` de la tabla, sin correlacionar— parece
    equivalente y rompe el producto: BYMA sólo publica lo que operó, así que una especie que no
    cotizó en la última corrida tiene su fila más nueva días atrás. Medido el 10/08/2026 sobre la
    base real: de 3.176 tickers, **291 estaban en esa situación y 28 de ellos con precio**. Ese
    DELETE los dejaría sin ninguna fila, y como `resumen` los toma con LEFT JOIN LATERAL, saldrían
    publicados con precio, TIR, paridad y volumen en NULL. Hay un test que fija la correlación.
    """
    return (
        f"DELETE FROM public.{tabla} p "
        f"WHERE p.capturado_en < ("
        f"SELECT max(q.capturado_en) FROM public.{tabla} q WHERE q.ticker = p.ticker)"
    )


def sql_cashflow() -> str:
    asignaciones = ", ".join(
        f"{col} = EXCLUDED.{col}"
        for col in COLUMNAS_CASHFLOW
        if col not in ("ticker", "payment_date")
    )
    return (
        f"INSERT INTO public.cashflow ({', '.join(COLUMNAS_CASHFLOW)}) "
        f"VALUES ({_marcadores(COLUMNAS_CASHFLOW)}) "
        f"ON CONFLICT (ticker, payment_date) DO UPDATE SET {asignaciones}"
    )


def _tuplas(
    filas: Sequence[dict[str, object]], columnas: Sequence[str], **fijos: object
) -> list[tuple[Any, ...]]:
    """Dicts → tuplas en el orden de columnas declarado. `fijos` inyecta lo mismo en cada fila."""
    return [tuple(fijos.get(col, fila.get(col)) for col in columnas) for fila in filas]


def poda_fallida(motivo: str) -> Alerta:
    """La poda falló pero lo escrito quedó bien: la corrida sirve, la tabla creció de más."""
    return Alerta(
        codigo=CODIGO_PODA_FALLIDA,
        mensaje=f"No se pudieron borrar los snapshots anteriores: {motivo}.",
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=(
            "Los precios de esta corrida se guardaron bien; lo único que quedó fue la tanda "
            "anterior sin borrar. Se limpia sola en la próxima corrida."
        ),
        detalle={"motivo": motivo},
    )


def escritura_fallida(tabla: str, motivo: str) -> Alerta:
    return Alerta(
        codigo=CODIGO_ESCRITURA_FALLIDA,
        mensaje=f"No se pudo escribir {tabla}: {motivo}.",
        severidad=Severidad.ERROR,
        accion_requerida=(
            f"Revisar el error y volver a correr la consolidación; {tabla} quedó como estaba."
        ),
        detalle={"tabla": tabla, "motivo": motivo},
    )


async def _escribir_lotes(conn: Any, sql: str, tuplas: Sequence[tuple[Any, ...]]) -> None:
    for inicio in range(0, len(tuplas), TAMANO_LOTE):
        await conn.executemany(sql, tuplas[inicio : inicio + TAMANO_LOTE])


async def persistir(
    conn: Any,
    consolidacion: Consolidacion,
    capturado_en: datetime,
    *,
    serie_historica: bool = False,
) -> Escritura:
    """Escribe las cuatro tablas en bloques independientes y declara qué quedó afuera.

    `conn` es una conexión de asyncpg (o cualquier cosa con `transaction()` y `executemany()`), y
    llega por parámetro en vez de sacarse de `app.state` para que F-008 pueda invocar esto desde un
    job, fuera del ciclo HTTP.

    `serie_historica` llega por parámetro y no de `get_settings()` por el mismo motivo: esta función
    no lee configuración global, así que un test controla el modo sin tocar el entorno. En `False`
    —el default— se poda al final y queda una fila por ticker; en `True` se acumula un snapshot por
    corrida, que es como funcionó hasta el 10/08/2026.
    """
    filas_por_tabla: dict[str, int] = {}
    alertas: list[Alerta] = []

    # Bloque 1: instrumentos y precios van juntos porque `precios` tiene FK a `instrumentos`.
    # Escribir un precio de una especie que no llegó a insertarse violaría la FK.
    try:
        async with conn.transaction():
            await _escribir_lotes(
                conn,
                sql_instrumentos(),
                _tuplas(consolidacion.filas_instrumentos, COLUMNAS_INSTRUMENTOS),
            )
            await _escribir_lotes(
                conn,
                sql_precios(),
                _tuplas(consolidacion.filas_precios, COLUMNAS_PRECIOS, capturado_en=capturado_en),
            )
        filas_por_tabla["instrumentos"] = len(consolidacion.filas_instrumentos)
        filas_por_tabla["precios"] = len(consolidacion.filas_precios)
    except Exception as exc:
        filas_por_tabla["instrumentos"] = 0
        filas_por_tabla["precios"] = 0
        alertas.append(escritura_fallida("instrumentos y precios", f"{type(exc).__name__}: {exc}"))

    # Bloque 2: puntas. Incluye las especies que no entraron a `instrumentos` —la tabla no tiene
    # FK justamente para eso—, así que no depende de que el bloque anterior haya salido bien.
    try:
        async with conn.transaction():
            await _escribir_lotes(
                conn,
                sql_puntas(),
                _tuplas(consolidacion.filas_puntas, COLUMNAS_PUNTAS, capturado_en=capturado_en),
            )
        filas_por_tabla["puntas"] = len(consolidacion.filas_puntas)
    except Exception as exc:
        filas_por_tabla["puntas"] = 0
        alertas.append(escritura_fallida("puntas", f"{type(exc).__name__}: {exc}"))

    # Bloque 3: cronograma. `None` es el contrato de F-006 —la corrida no trajo uno usable— y
    # significa conservar el que ya está, no borrarlo ni reescribirlo con nada.
    if consolidacion.filas_cashflow is None:
        filas_por_tabla["cashflow"] = 0
    else:
        try:
            async with conn.transaction():
                await _escribir_lotes(
                    conn,
                    sql_cashflow(),
                    _tuplas(consolidacion.filas_cashflow, COLUMNAS_CASHFLOW),
                )
            filas_por_tabla["cashflow"] = len(consolidacion.filas_cashflow)
        except Exception as exc:
            filas_por_tabla["cashflow"] = 0
            alertas.append(escritura_fallida("cashflow", f"{type(exc).__name__}: {exc}"))

    # Bloque 4: poda. Va último y en su propia transacción — podar antes de escribir dejaría a la
    # base sin foto si la corrida fallara a mitad de camino, y compartir transacción con los bloques
    # de arriba haría que un problema borrando tire abajo una escritura que salió bien.
    podadas: dict[str, int] = {}
    if not serie_historica:
        try:
            async with conn.transaction():
                for tabla in ("precios", "puntas"):
                    resultado = await conn.execute(sql_poda(tabla))
                    podadas[tabla] = _filas_borradas(resultado)
        except Exception as exc:
            podadas = {}
            alertas.append(poda_fallida(f"{type(exc).__name__}: {exc}"))

    logger.info(
        "consolidacion_persistida",
        capturado_en=capturado_en.isoformat(),
        **filas_por_tabla,
        serie_historica=serie_historica,
        podadas=podadas,
        fallos=len(alertas),
    )
    return Escritura(filas_por_tabla=filas_por_tabla, alertas=alertas)


def _filas_borradas(resultado: Any) -> int:
    """asyncpg devuelve el command tag (`"DELETE 128"`); los fakes de los tests devuelven `None`."""
    if not isinstance(resultado, str):
        return 0
    partes = resultado.split()
    return int(partes[-1]) if partes and partes[-1].isdigit() else 0
