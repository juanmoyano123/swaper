"""Endpoints del job programado de ingesta (F-008).

El scheduler corre solo cuando `ingesta_habilitada=True`, así que estos endpoints también sirven
para disparar una corrida a mano en desarrollo o para forzar un refresh puntual en producción —el
mismo criterio que ya usa `POST /api/v1/consolidar` para la corrida matinal completa.

**La dependencia de auth va en el router y no endpoint por endpoint** (Tanda 3, 26/08/2026). Estos
endpoints estuvieron abiertos a internet hasta esa fecha, y el modo de arreglarlo importa: si cada
decorador tuviera que acordarse de pedirla, el próximo job que se agregue nacería abierto y nadie
lo notaría hasta que alguien lo encontrara. Puesta acá, un endpoint nuevo llega protegido sin que
su autor tenga que enterarse de que esto existe.

`GET /corridas` también queda detrás de la puerta. No rompe ninguna pantalla: el cliente HTTP del
frontend (`frontend/src/lib/api/client.ts`) adjunta el JWT de la sesión en todos los requests.

**`GET /cron/*` son la puerta del disparador automático (Tanda 4, 26/08/2026)** y conviven con los
`POST /corridas/*` en vez de reemplazarlos: son la misma corrida con dos guardas encima —horario y
no-solapamiento— que sólo tienen sentido cuando quien dispara es una máquina. Un asesor que aprieta
el botón sabe qué hora es y quiere que corra igual; un cron que llega tarde un feriado, no.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends

from app.api.deps import cron_o_asesor, get_db
from app.core.config import Settings, get_settings
from app.externos.sec import ClienteSec
from app.ingesta.byma.cedears import traer_lista
from app.instrumentos.emisores import LIMITE_POR_CORRIDA as LIMITE_EMISORES
from app.instrumentos.emisores import completar_emisores
from app.jobs.corridas import correr_fci, corrida_matinal, lock_de_ingesta, refresh_intra_rueda
from app.jobs.horarios import en_ventana_de_rueda, es_dia_habil, zona
from app.jobs.registro import listar_corridas
from app.renta_variable.agrupamiento import agrupar
from app.renta_variable.clasificacion import (
    LIMITE_POR_CORRIDA as LIMITE_CLASIFICACION,
)
from app.renta_variable.clasificacion import (
    DatosDeBymaPorPapel,
    clasificar_renta_variable,
    reclasificar_etfs,
)
from app.renta_variable.geografia_etf import sembrar_geografia_etfs
from app.renta_variable.lectura import leer_renta_variable
from app.renta_variable.paises import sembrar_paises

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(cron_o_asesor)])

LIMITE_MAXIMO = 100
LIMITE_POR_DEFECTO = 20


@router.get(
    "/corridas",
    summary="Historial de corridas del job de ingesta",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def corridas(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_POR_DEFECTO,
) -> list[dict[str, object]]:
    """Las corridas más recientes primero, con hora, duración, filas por fuente y alertas.

    Es lo que F-013 va a consumir para la barra de estado del dato. `limite` tiene tope para que
    nadie pida el historial entero por accidente.
    """
    return await listar_corridas(conn, limite=min(limite, LIMITE_MAXIMO))


@router.post(
    "/corridas/matinal",
    summary="Dispara a mano la corrida matinal completa (BYMA + data912 + consolidación)",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_matinal(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    return await corrida_matinal(conn, settings)


@router.post(
    "/corridas/refresh",
    summary="Dispara a mano un refresh intra-rueda (sólo precios y puntas de BYMA)",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_refresh(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    return await refresh_intra_rueda(conn, settings)


MOTIVO_LOCK_TOMADO = "corrida en curso"

RESPUESTAS_CRON = {
    200: {
        "description": (
            "La corrida se ejecutó y devuelve su registro, o se omitió y devuelve "
            '`{"omitida": true, "motivo": "..."}`'
        )
    },
    401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
    503: {"description": "La base de datos no está disponible, o no se pueden validar sesiones"},
}


def _omitida(motivo: str) -> dict[str, object]:
    """La respuesta de una corrida que no se ejecutó. **200 y no 4xx, a propósito.**

    El disparador es un cron externo best-effort: GitHub Actions no garantiza el minuto y puede
    llegar tarde, y además dispara los feriados bursátiles, que no se modelan (ver el docstring de
    `app.jobs.horarios`). Con un 4xx el workflow se pondría en rojo cada feriado y cada tick
    corrido — y un log que está en rojo por diseño enseña a no mirarlo, con lo cual el día que
    falle de verdad la alerta ya no alerta a nadie. Omitir es el resultado esperado de una
    condición normal, así que se informa, no se falla.

    El contrato lo consume `.github/workflows/ingesta.yml`, que busca `"omitida": true` en el
    cuerpo y lo registra como `::notice::`.
    """
    return {"omitida": True, "motivo": motivo}


async def _corrida_del_cron(
    conn: asyncpg.Connection,
    settings: Settings,
    corrida: Callable[..., Awaitable[dict[str, object]]],
    *,
    habilitada: bool,
    motivo_fuera_de_horario: str,
) -> dict[str, object]:
    """Las dos guardas comunes a los disparos automáticos: horario y no-solapamiento.

    Orden deliberado: primero el horario, que no toca la base, y sólo después el lock. Al revés,
    cada tick de un sábado tomaría y soltaría un lock para nada.
    """
    if not habilitada:
        return _omitida(motivo_fuera_de_horario)

    async with lock_de_ingesta(conn) as tomado:
        if not tomado:
            return _omitida(MOTIVO_LOCK_TOMADO)
        return await corrida(conn, settings)


@router.get(
    "/cron/matinal",
    summary="Corrida matinal completa, disparada por el cron externo",
    responses=RESPUESTAS_CRON,
)
async def cron_matinal(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Mismo trabajo que `POST /jobs/corridas/matinal`, con las guardas que necesita un disparador
    automático. Delega en `corrida_matinal` sin modificarla.

    **Por qué GET y no POST.** Los disparadores de cron disponibles sólo hacen GET: GitHub Actions
    le pega con `curl` (ver `.github/workflows/ingesta.yml`) y Vercel Cron —el reemplazo si el
    proyecto pasa a Pro— sólo emite GET, sin forma de configurar el método. El POST equivalente
    sigue existiendo para el disparo manual desde el frontend; éste es la puerta del cron.

    **Guarda de día hábil, no de ventana de rueda —y la diferencia es a propósito.** La matinal es
    un disparo único por día y su valor es traer el universo del día; si el cron llega con horas de
    atraso, correrla igual es mejor que dejar la jornada entera sin universo nuevo, porque los
    precios de cierre siguen siendo los de hoy. Lo que nunca tiene sentido es correrla un fin de
    semana: el antecedente está en el docstring de `app.jobs.horarios` —una corrida disparada un
    sábado escribió 466 filas sin un solo precio ni una sola TIR, y dejó el indicador de frescura
    declarando el sábado sobre datos del miércoles—. El refresh sí lleva la ventana completa,
    porque un refresh fuera de rueda no aporta ningún precio que no tenga ya la matinal.
    """
    hoy = datetime.now(UTC).astimezone(zona(settings)).date()
    return await _corrida_del_cron(
        conn,
        settings,
        corrida_matinal,
        habilitada=es_dia_habil(hoy),
        motivo_fuera_de_horario=f"{hoy.isoformat()} no es día hábil: no hay rueda que ingerir",
    )


@router.get(
    "/cron/refresh",
    summary="Refresh intra-rueda, disparado por el cron externo",
    responses=RESPUESTAS_CRON,
)
async def cron_refresh(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Mismo trabajo que `POST /jobs/corridas/refresh`, con las guardas del disparador automático.
    Delega en `refresh_intra_rueda` sin modificarla. Ver `cron_matinal` para por qué GET.

    Acá la guarda es la ventana de rueda entera —día hábil **y** horario—: un refresh existe para
    traer precios que se están moviendo, y con el mercado cerrado no hay ninguno que la matinal no
    tenga ya. El cron de GitHub cubre de 11:00 a 17:00 ART, pero sus disparos se corren, así que el
    tick de las 17:00 puede llegar a las 17:06 con la rueda cerrada. Ese caso se omite, no falla.
    """
    return await _corrida_del_cron(
        conn,
        settings,
        refresh_intra_rueda,
        habilitada=en_ventana_de_rueda(datetime.now(UTC), settings),
        motivo_fuera_de_horario=(
            f"fuera de la ventana de rueda "
            f"({settings.ingesta_rueda_desde} a {settings.ingesta_rueda_hasta} "
            f"{settings.ingesta_zona_horaria}, días hábiles)"
        ),
    )


@router.post(
    "/fci",
    summary="Dispara a mano la ingesta de la planilla diaria de CAFCI (F-057)",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_fci(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """No pasa por la corrida matinal completa: sólo la planilla de CAFCI, wipe-and-replace sobre
    `public.fci`. Con `CAFCI_HABILITADO=false` (el default) registra una corrida sin filas —el
    flag apagado se ve en el resultado, no se disimula."""
    return await correr_fci(conn, settings)


@router.post(
    "/clasificar-renta-variable",
    summary=(
        "Clasifica acciones y CEDEARs contra la SEC: actividad, eslabón de la cadena productiva "
        "y estrategia si es un fondo"
    ),
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_clasificacion_renta_variable(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_CLASIFICACION,
) -> dict[str, object]:
    """Incremental: procesa hasta `limite` papeles por corrida y retoma después.

    Se clasifica **por papel y no por especie** — `AAPL` una vez, y `AAPLC`/`AAPLD` heredan su
    clasificación—, así que primero se arma el mapa de especie a papel con el mismo agrupamiento
    que usa el universo.

    La lista de CEDEARs de BYMA es opcional y aporta nombre y ratio: si no se pudo bajar, la
    clasificación sigue con lo que da la SEC y lo que falte queda declarado.
    """
    filas = await leer_renta_variable(conn)
    tickers = {str(f["ticker"]) for f in filas}
    grupos = agrupar(tickers)
    por_papel = {t: g.emision for t, g in grupos.items() if not g.no_identificado}

    lista = await traer_lista()
    datos_byma = {
        codigo: DatosDeBymaPorPapel(nombre=c.nombre, ratio=c.ratio, mercado=c.mercado)
        for codigo, c in lista.cedears.items()
    }

    resumen = await clasificar_renta_variable(
        conn,
        ClienteSec(),
        por_papel=por_papel,
        datos_byma=datos_byma,
        limite=limite,
    )
    return resumen.como_dict()


@router.post(
    "/completar-emisores",
    summary=(
        "Completa emisor, ley y denominación de los instrumentos que los tienen vacíos, "
        "desde la ficha técnica de BYMA"
    ),
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_completar_emisores(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    limite: int = LIMITE_EMISORES,
) -> dict[str, object]:
    """Incremental: hasta `limite` especies por corrida, retomando donde quedó.

    La matinal ya encadena una tanda chica todos los días (`LIMITE_EMISORES_EN_MATINAL`); esto es
    para acelerar el barrido a mano sin esperar a que el goteo diario termine.

    `limite` va topeado: son ~4.000 pendientes y un POST por especie, así que pedir el universo
    entero en una sola llamada la haría durar más de lo que cualquier proxy tolera.
    """
    resumen = await completar_emisores(conn, limite=min(limite, LIMITE_EMISORES))
    return resumen.como_dict()


@router.post(
    "/reclasificar-etfs",
    summary=(
        "Re-deriva la estrategia y la geografía de los fondos desde el nombre ya persistido, "
        "sin tocar la SEC"
    ),
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_reclasificacion_etfs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
) -> dict[str, object]:
    """El backfill de `region_etf` (F-078) y de cualquier cambio futuro en el vocabulario de
    `app/renta_variable/etfs.py`.

    **No le pega a ninguna fuente externa**, y por eso no lleva `limite` ni ventana de horario: es
    un parser corriendo sobre el `nombre_largo` que ya está en `perfil_renta_variable`. Puro,
    idempotente y liviano — un SELECT y un UPDATE por lote, en una sola transacción.

    Es la alternativa a `POST /jobs/clasificar-renta-variable` para este trabajo: aquél tardaría
    diecisiete corridas de 100 papeles barriendo la SEC para no cambiar nada de lo que la SEC
    aporta.
    """
    resumen = await reclasificar_etfs(conn)
    return resumen.como_dict()


@router.post(
    "/sembrar-paises-cedears",
    summary="Carga el curado de países de CEDEARs desde data/paises_cedears.csv",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_siembra_paises(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Idempotente, sin red y sin reloj: sembrar dos veces seguidas deja la misma tabla.

    Mientras el curado no esté validado el archivo no existe, y entonces esto devuelve cero
    cargados con la alerta `paises_cedears_no_encontrado` arriba — que es el estado correcto, no un
    fallo: el país de cada CEDEAR queda declarado faltante hasta la primera tanda validada.

    `descartados` cuenta lo que el artefacto trae y no se carga (país fuera del vocabulario, papel
    repetido, fila sin fuente o sin fecha) con el detalle papel por papel; `sin_pais` cuenta lo que
    **sí** se carga con el país vacío a propósito: los ETFs, cuyo eje geográfico es `region_etf`, y
    los papeles que se investigaron sin poder resolverse.
    """
    resumen = await sembrar_paises(conn, settings)
    return resumen.como_dict()


@router.post(
    "/sembrar-geografia-etfs",
    summary="Carga el curado de geografía de ETFs desde data/etfs_geografia.csv",
    responses={
        401: {"description": "Falta el token de cron o la sesión de asesor, o no son válidos"},
        503: {
            "description": ("La base de datos no está disponible, o no se pueden validar sesiones")
        },
    },
)
async def disparar_siembra_geografia_etfs(
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Idempotente, sin red y sin reloj: sembrar dos veces seguidas deja la misma tabla (F-079, D3).

    Mientras el curado no esté validado el archivo no existe, y entonces esto devuelve cero
    cargados — que es el estado correcto, no un fallo: cada ETF geográfico sigue mostrándose con el
    token crudo de su nombre (`region_etf`) hasta la primera tanda validada.
    """
    cargados = await sembrar_geografia_etfs(conn, settings)
    return {"cargados": cargados}
