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
`COALESCE(EXCLUDED.col, instrumentos.col)`, así que una corrida en la que IAMC no estuvo disponible
deja la ley y la moneda de pago como estaban en vez de vaciarlas. Es lo que F-008 necesita para
correr refrescos intradiarios que sólo tocan BYMA sin degradar el universo en cada pasada.

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
from app.ingesta.consolidacion.armado import Consolidacion

logger = structlog.get_logger()

CODIGO_ESCRITURA_FALLIDA = "escritura_fallida"

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
)

# Por ticker, las métricas del informe más reciente que se haya llegado a guardar. Lo consulta la
# corrida antes de armar, para que una pasada sin informe conserve lo que ya se sabía en vez de
# publicar un universo sin TIR: la vista `resumen` lee una sola fila de precios por ticker, así que
# lo que no esté en la fila nueva desaparece del universo aunque siga en la tabla.
SQL_METRICAS_PREVIAS = """
SELECT DISTINCT ON (ticker)
       ticker, tir, duration, paridad, convexidad, residual_value, fecha_metricas
  FROM public.precios
 WHERE fecha_metricas IS NOT NULL
 ORDER BY ticker, fecha_metricas DESC, capturado_en DESC
"""


async def leer_metricas_previas(conn: Any) -> dict[str, dict[str, object]]:
    """Las últimas métricas de IAMC conocidas, por ticker. Vacío si la tabla todavía no tiene."""
    filas = await conn.fetch(SQL_METRICAS_PREVIAS)
    return {fila["ticker"]: dict(fila) for fila in filas}


COLUMNAS_PUNTAS: tuple[str, ...] = (
    "ticker",
    "capturado_en",
    "px_bid",
    "px_ask",
    "operaciones",
    "fuente",
)

COLUMNAS_CASHFLOW: tuple[str, ...] = (
    "ticker",
    "type",
    "issue_date",
    "payment_date",
    "capital",
    "interest_rate",
    "interest_amount",
    "residual_value",
    "cash_flow",
)

# Los ~5.700 upserts de una corrida entran cómodos en el command_timeout de 30 s del pool, pero
# se trocean igual: un lote gigante mantiene una sola sentencia abierta el tiempo entero y
# cualquier hipo de red la pierde completa.
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


async def persistir(conn: Any, consolidacion: Consolidacion, capturado_en: datetime) -> Escritura:
    """Escribe las cuatro tablas en tres bloques independientes y declara qué quedó afuera.

    `conn` es una conexión de asyncpg (o cualquier cosa con `transaction()` y `executemany()`), y
    llega por parámetro en vez de sacarse de `app.state` para que F-008 pueda invocar esto desde un
    job, fuera del ciclo HTTP.
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

    logger.info(
        "consolidacion_persistida",
        capturado_en=capturado_en.isoformat(),
        **filas_por_tabla,
        fallos=len(alertas),
    )
    return Escritura(filas_por_tabla=filas_por_tabla, alertas=alertas)
