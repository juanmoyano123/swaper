"""Las dos corridas que orquesta el job de F-008, cada una envolviendo lo que F-004 a F-007 ya
dejaron listo y dejando su registro auditable en `corridas_ingesta`.

**La matinal** es `consolidar()` de F-007 tal cual: BYMA y data912 ya corren ahí en el orden
correcto, con la asimetría entre fuentes ya resuelta. Acá sólo se cronometra y se registra.

**El refresh intra-rueda** arma su propio `Consolidacion` a partir de `armar_consolidacion()`, con
el cronograma leído de `cashflow` y no pedido a ninguna fuente —es la única forma de que
`public-bonds` (soberanos y subsoberanos, que sólo se clasifican por el `type` del cronograma) no
queden afuera de cada refresco—. Desde F-051 se lee el cronograma **entero** y no sólo su `type`,
porque de él salen las métricas propias: cada refresco vuelve a calcular TIR, duración y paridad
contra el precio que acaba de traer, que es lo que hace que el monitor muestre rendimientos vivos
y no los de la matinal. Sólo se persisten precios y puntas: `filas_instrumentos` se vacía antes de
llamar a `persistir()` y `filas_cashflow` queda en `None`, que es el contrato ya existente de F-007
para "no tocar esta tabla".

Ninguna de las dos corridas se aborta por una fuente caída: es la propiedad que ya tienen
`consolidar()` y `ingerir_rueda()`, y acá se hereda sin agregar un solo `try` nuevo alrededor de
las fuentes.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import structlog

from app.core.config import Settings
from app.ingesta.alertas import Alerta, Severidad, fuente_caida
from app.ingesta.byma import ingerir_rueda
from app.ingesta.cafci import ingerir_cafci
from app.ingesta.consolidacion import armar_consolidacion, consolidar
from app.ingesta.consolidacion.persistencia import leer_cronograma, persistir
from app.ingesta.snapshot import Snapshot
from app.jobs.registro import EstadoCorrida, TipoCorrida, registrar_corrida
from app.jobs.universo import filtrar_precios_al_universo, leer_tickers_existentes

logger = structlog.get_logger()

CODIGO_TICKER_FUERA_DE_UNIVERSO = "ticker_fuera_de_universo"

# Clave del advisory lock que serializa las corridas de ingesta. El número es `8` —F-008, la
# feature del job programado— y no un valor al azar: el espacio de claves de `pg_advisory_lock` es
# global a la base y compartido por cualquier otro código que use el mecanismo, así que la clave
# tiene que poder rastrearse hasta quién la reservó. Si alguna vez hace falta una segunda, la
# convención es el número de la feature que la pide.
CLAVE_LOCK_INGESTA = 8


def _ticker_fuera_de_universo(tickers: list[str]) -> Alerta:
    """Un precio de un ticker que `instrumentos` todavía no conoce. No se inventa el instrumento
    acá —eso decide la corrida matinal—, así que el precio se descarta de esta pasada y se declara.
    """
    return Alerta(
        codigo=CODIGO_TICKER_FUERA_DE_UNIVERSO,
        mensaje=(
            f"{len(tickers)} especies con precio nuevo de BYMA todavía no están en el universo "
            f"({', '.join(tickers[:5])}). Su precio no se guardó en este refresh; van a entrar en "
            f"la próxima corrida matinal."
        ),
        severidad=Severidad.ADVERTENCIA,
        accion_requerida=None,
        detalle={"total": len(tickers), "muestra": tickers[:20]},
    )


@asynccontextmanager
async def lock_de_ingesta(conn: Any) -> AsyncIterator[bool]:
    """Toma el lock que serializa las corridas de ingesta. Rinde `True` si lo consiguió.

    **Qué protege.** Hasta el 26/08/2026 nada impedía dos corridas simultáneas —el cron
    disparando mientras un asesor aprieta el botón, o un tick que llega antes de que termine el
    anterior—. Verificado sobre el código: no se corrompe nada (`registrar_corrida` sólo inserta y
    `persistir` upsertea), pero las dos pasadas intercalan sus `capturado_en` y dejan dos filas en
    `corridas_ingesta` para un solo evento. El resultado es que el indicador de frescura publica el
    `capturado_en` de la corrida que terminó última, que no tiene por qué ser la que trajo el
    precio más nuevo.

    **Por qué un advisory lock y no una tabla de estado.** Una fila "corrida en curso" hay que
    borrarla, y el caso que importa es justamente aquel en el que nadie la borra: el proceso que la
    escribió murió a mitad de camino —una función serverless que se pasó de `maxDuration`, un
    deploy en el medio—. A partir de ahí la tabla dice "en curso" para siempre y la ingesta queda
    trabada hasta que alguien lo note a mano. El advisory lock es de sesión: cuando la conexión se
    cierra, Postgres lo suelta solo, sin depender de que nuestro código llegue al `finally`. El
    `finally` de acá es para el caso normal, donde la conexión vuelve al pool y sigue viva.

    Va sobre la conexión ya adquirida y no sobre una nueva a propósito: el lock pertenece a la
    sesión que lo pidió, así que tomarlo en otra conexión no protegería el trabajo que se hace en
    ésta.
    """
    # `::bigint` explícito: `pg_try_advisory_lock` está sobrecargada —una versión toma un bigint y
    # otra dos int—, y dejar que el tipo del parámetro lo infiera el driver hace que cuál de las
    # dos se resuelve dependa de él y no de este código.
    sql = "SELECT pg_try_advisory_lock($1::bigint)"
    tomado = bool(await conn.fetchval(sql, CLAVE_LOCK_INGESTA))
    try:
        yield tomado
    finally:
        if tomado:
            await conn.fetchval("SELECT pg_advisory_unlock($1::bigint)", CLAVE_LOCK_INGESTA)


async def _ingerir_fci_sin_lanzar(
    conn: Any,
    settings: Settings,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Snapshot:
    """La planilla de CAFCI (F-057), en su propio try/except: no pasa por el consolidador —no es
    una especie negociable, ver la ficha de F-057— y una excepción no vista (p. ej. la escritura a
    `fci` fallando a mitad de transacción) no puede tirar abajo la corrida matinal entera, que ya
    trajo BYMA y data912 para cuando esto corre.
    """
    try:
        return await ingerir_cafci(conn, settings, dormir=dormir)
    except Exception as exc:
        logger.warning("cafci_ingesta_fallo_inesperado", error=str(exc))
        snapshot = Snapshot(fuente="CAFCI")
        snapshot.registrar_tramo("planilla", 0)
        snapshot.alertar(fuente_caida("CAFCI", f"{type(exc).__name__}: {exc}"))
        return snapshot


def _estado_de(snapshots: Iterable[Snapshot]) -> str:
    """`completa` si nada falló, `parcial` si algo llegó igual, `fallida` si no llegó nada."""
    snapshots = list(snapshots)
    if not snapshots:
        return EstadoCorrida.FALLIDA
    if all(s.completo for s in snapshots):
        return EstadoCorrida.COMPLETA
    if any(s.total_filas > 0 for s in snapshots):
        return EstadoCorrida.PARCIAL
    return EstadoCorrida.FALLIDA


async def corrida_matinal(
    conn: Any,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, object]:
    """BYMA + data912 + consolidación, en ese orden — el orden ya lo fija `consolidar()`.

    CAFCI corre al final, fuera de `consolidar()`: no es una fuente que se consolide contra el
    universo de renta fija/variable, es un universo propio (F-057). Sólo se pide acá y no en cada
    refresh de 20 minutos — `pb_get` siempre devuelve el mismo archivo del último día hábil, así que
    pedirla más seguido bajaría el mismo archivo sin dato nuevo.
    """
    inicio = datetime.now(UTC)
    resultado = await consolidar(conn, settings, dormir=dormir)
    snapshot_fci = await _ingerir_fci_sin_lanzar(conn, settings, dormir)
    fin = datetime.now(UTC)

    todos_los_snapshots = {**resultado.snapshots, "cafci": snapshot_fci}
    alertas = [
        *(a for s in todos_los_snapshots.values() for a in s.alertas),
        *resultado.consolidacion.alertas,
        *resultado.escritura.alertas,
    ]
    filas_por_fuente = {nombre: snap.total_filas for nombre, snap in todos_los_snapshots.items()}
    estado = _estado_de(todos_los_snapshots.values())

    corrida = await registrar_corrida(
        conn,
        tipo=TipoCorrida.MATINAL,
        iniciado_en=inicio,
        finalizado_en=fin,
        filas_por_fuente=filas_por_fuente,
        alertas=[a.como_dict() for a in alertas],
        estado=estado,
    )
    logger.info(
        "corrida_matinal_registrada",
        id=corrida["id"],
        estado=estado,
        duracion_ms=corrida["duracion_ms"],
        filas_por_fuente=filas_por_fuente,
    )
    return corrida


async def refresh_intra_rueda(
    conn: Any,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, object]:
    """Sólo precios y puntas desde BYMA. No toca `instrumentos` ni la tabla `cashflow`."""
    inicio = datetime.now(UTC)
    rueda = await ingerir_rueda(settings=settings, dormir=dormir)

    # El cronograma entero, no sólo `ticker` y `type`: de él salen la clasificación por submarket
    # **y** las métricas propias de F-051. Con las dos columnas que este refresh leía antes, cada
    # pasada intradiaria dejaría la fila de precios sin TIR y la vista —que toma una sola fila por
    # ticker— publicaría el universo sin rendimiento hasta la matinal siguiente.
    cronograma = await leer_cronograma(conn)
    consolidacion = armar_consolidacion(
        especies_por_endpoint=rueda.especies_por_endpoint,
        cronograma_persistido=cronograma,
        hoy=inicio.date(),
    )

    tickers_existentes = await leer_tickers_existentes(conn)
    precios_en_universo, fuera_de_universo = filtrar_precios_al_universo(
        consolidacion.filas_precios, tickers_existentes
    )
    alertas_consolidacion = list(consolidacion.alertas)
    if fuera_de_universo:
        alertas_consolidacion.append(_ticker_fuera_de_universo(fuera_de_universo))

    # `filas_instrumentos=[]` y `filas_cashflow=None`: el refresh no toca ninguna de las dos
    # tablas. `persistir()` es la misma función que usa la matinal, sin modificarla — una lista de
    # instrumentos vacía es un no-op en su primer bloque, y `None` en cashflow es el contrato ya
    # existente de F-007 para "conservar lo que hay".
    consolidacion_refresco = replace(
        consolidacion,
        filas_instrumentos=[],
        filas_precios=precios_en_universo,
        filas_cashflow=None,
        alertas=alertas_consolidacion,
    )

    capturado_en = datetime.now(UTC)
    escritura = await persistir(
        conn,
        consolidacion_refresco,
        capturado_en,
        serie_historica=settings.serie_historica_habilitada,
    )
    fin = datetime.now(UTC)

    alertas = [*rueda.snapshot.alertas, *alertas_consolidacion, *escritura.alertas]
    filas_por_fuente = {"byma": rueda.snapshot.total_filas}
    estado = _estado_de([rueda.snapshot])

    corrida = await registrar_corrida(
        conn,
        tipo=TipoCorrida.REFRESH,
        iniciado_en=inicio,
        finalizado_en=fin,
        filas_por_fuente=filas_por_fuente,
        alertas=[a.como_dict() for a in alertas],
        estado=estado,
    )
    logger.info(
        "refresh_registrado",
        id=corrida["id"],
        estado=estado,
        duracion_ms=corrida["duracion_ms"],
        precios=escritura.filas_por_tabla.get("precios", 0),
        puntas=escritura.filas_por_tabla.get("puntas", 0),
    )
    return corrida


async def correr_fci(
    conn: Any,
    settings: Settings,
    *,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> dict[str, object]:
    """Sólo la planilla de CAFCI (F-057), disparable a mano (`POST /jobs/fci`) sin esperar a la
    corrida matinal completa — mismo criterio que `disparar_clasificacion_renta_variable`.

    Con `cafci_habilitado=False` esto igual registra una corrida: `snapshot.total_filas == 0` sin
    alertas de error, así que `_estado_de` la marca `fallida` (0 filas). Es correcto: el asesor que
    dispara el job a mano tiene que ver que el flag está apagado, no una corrida "completa" vacía.
    """
    inicio = datetime.now(UTC)
    snapshot = await _ingerir_fci_sin_lanzar(conn, settings, dormir)
    fin = datetime.now(UTC)

    estado = _estado_de([snapshot])
    corrida = await registrar_corrida(
        conn,
        tipo=TipoCorrida.FCI,
        iniciado_en=inicio,
        finalizado_en=fin,
        filas_por_fuente={"cafci": snapshot.total_filas},
        alertas=[a.como_dict() for a in snapshot.alertas],
        estado=estado,
    )
    logger.info(
        "corrida_fci_registrada",
        id=corrida["id"],
        estado=estado,
        duracion_ms=corrida["duracion_ms"],
        filas=snapshot.total_filas,
    )
    return corrida
