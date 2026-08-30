"""Job de clasificación de renta variable contra la SEC — 13/08/2026.

Incremental: procesa hasta `limite` papeles por corrida, persiste uno por uno, y retoma donde
quedó. Un corte a mitad de camino no pierde lo que ya se trajo.

## Se clasifica por papel, no por especie

`AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR de Apple en pesos, cable y MEP. Preguntarle a la SEC
tres veces por Apple sería gastar tres pedidos para escribir tres filas idénticas. Se consulta una
vez por **papel** —lo que el agrupamiento de `agrupamiento.py` habilitó— y la clasificación se
escribe en las tres especies, porque el sector de una empresa no cambia con la moneda en que se
liquida su CEDEAR.

## Qué se puede clasificar y qué no

La SEC cubre **315 de 427 CEDEARs (74 %)** y **21 de 245 acciones argentinas (9 %)**, medido el
13/08/2026: sólo las argentinas con ADR tienen CIK. Las demás quedan sin clasificar y **se declaran
así**; su fuente es la CNV y espera a F-054. No se les completa el sector por parecido con otra
empresa del mismo nombre ni por nada.

Un papel sin CIK **no es un error de la corrida**: es un papel que la SEC no lista, y el resumen lo
cuenta aparte de los que fallaron.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from app.externos.sec import ClienteSec, EntradaSic, LimiteDeLaFuente
from app.externos.sic import division_de
from app.renta_variable.etfs import estrategia_de, region_declarada
from app.renta_variable.perfiles import (
    guardar_clasificacion,
    guardar_reclasificacion,
    nombres_persistidos,
    papeles_pendientes_sec,
)

logger = structlog.get_logger()

FUENTE = "SEC EDGAR"

# Cuántos papeles procesa una corrida. La SEC no limita por cuota sino por ritmo, y el cliente ya
# pausa entre pedidos: lo que acota acá es cuánto puede tardar un solo POST, no cuánto tolera la
# fuente.
LIMITE_POR_CORRIDA = 100


@dataclass(frozen=True, slots=True)
class ResumenClasificacion:
    """Lo que la corrida hizo y lo que no pudo hacer, con los motivos separados."""

    pendientes: int
    procesados: int
    clasificados: int
    sin_cik: int
    """Papeles que la SEC no lista. No es una falla: es un papel que esa fuente no cubre."""
    cortado_por_limite_de_fuente: bool = False
    motivo_corte: str | None = None

    def como_dict(self) -> dict[str, object]:
        return {
            "pendientes": self.pendientes,
            "procesados": self.procesados,
            "clasificados": self.clasificados,
            "sin_cik": self.sin_cik,
            "cortado_por_limite_de_fuente": self.cortado_por_limite_de_fuente,
            "motivo_corte": self.motivo_corte,
        }


@dataclass(frozen=True, slots=True)
class DatosDeBymaPorPapel:
    """Lo que la tabla oficial de CEDEARs aporta y la SEC no: nombre en castellano, ratio y mercado
    del subyacente. Vacío para lo que BYMA no lista — que existe: `XPEV` cotiza desde 2025 y no
    figura en el PDF de junio de 2026."""

    nombre: str | None = None
    ratio: str | None = None
    mercado: str | None = None


async def clasificar_renta_variable(
    conn: Any,
    cliente: ClienteSec,
    *,
    por_papel: dict[str, str],
    datos_byma: dict[str, DatosDeBymaPorPapel] | None = None,
    dormir: Callable[[float], Awaitable[None]] = asyncio.sleep,
    limite: int = LIMITE_POR_CORRIDA,
    ahora: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> ResumenClasificacion:
    """Clasifica hasta `limite` papeles pendientes contra la SEC.

    `por_papel` mapea cada especie a su papel (`{'AAPLD': 'AAPL', ...}`) — sale del agrupamiento y
    es lo que evita consultar tres veces por Apple.

    `datos_byma` es opcional: sin él la clasificación sigue funcionando con lo que da la SEC, y lo
    que falte queda declarado. Es dato que **aporta**, no que decide.
    """
    datos_byma = datos_byma or {}
    pendientes = await papeles_pendientes_sec(conn, fuente=FUENTE)
    a_procesar = pendientes[:limite]
    if not a_procesar:
        return ResumenClasificacion(pendientes=0, procesados=0, clasificados=0, sin_cik=0)

    try:
        mapa_cik = await cliente.mapa_de_tickers()
        catalogo = await cliente.catalogo_sic()
    except LimiteDeLaFuente as exc:
        return ResumenClasificacion(
            pendientes=len(pendientes),
            procesados=0,
            clasificados=0,
            sin_cik=0,
            cortado_por_limite_de_fuente=True,
            motivo_corte=str(exc),
        )

    clasificados = sin_cik = 0
    for indice, ticker in enumerate(a_procesar):
        papel = por_papel.get(ticker, ticker).upper()
        de_byma = datos_byma.get(papel, DatosDeBymaPorPapel())
        # La estrategia sale del nombre de BYMA, y es `None` cuando el papel no es un fondo.
        estrategia = estrategia_de(de_byma.nombre)

        cik = mapa_cik.get(papel)
        if cik is None:
            # Sin CIK no hay SIC, pero se guarda igual: si BYMA declaró el nombre, con eso alcanza
            # para que el asesor reconozca el papel; y si no declaró nada, **la fila queda vacía
            # pero escrita**.
            #
            # Escribirla vacía no es guardar basura: es dejar registrado que a este papel ya se le
            # preguntó a la SEC y no está. Sin eso vuelve a la cola de pendientes en cada corrida y
            # el job no avanza nunca — medido el 13/08/2026: nueve tandas de 100 papeles bajaron
            # los pendientes de 1.539 a 1.536, porque los 99 sin CIK de cada tanda volvían a
            # entrar. `capturado_en` es lo que hace que se reintente recién al vencer.
            await _guardar(conn, ticker, None, catalogo, de_byma, estrategia, ahora())
            if de_byma.nombre or estrategia:
                clasificados += 1
            sin_cik += 1
            continue

        try:
            perfil = await cliente.perfil_de(cik)
        except LimiteDeLaFuente as exc:
            logger.info("clasificacion_sec_cortada_por_429", ticker=ticker, procesados=indice)
            return ResumenClasificacion(
                pendientes=len(pendientes),
                procesados=indice,
                clasificados=clasificados,
                sin_cik=sin_cik,
                cortado_por_limite_de_fuente=True,
                motivo_corte=str(exc),
            )

        if perfil is not None:
            await _guardar(conn, ticker, perfil, catalogo, de_byma, estrategia, ahora())
            clasificados += 1

        if indice < len(a_procesar) - 1:
            await dormir(0)
            await cliente.pausar()

    return ResumenClasificacion(
        pendientes=len(pendientes),
        procesados=len(a_procesar),
        clasificados=clasificados,
        sin_cik=sin_cik,
    )


async def _guardar(
    conn: Any,
    ticker: str,
    perfil: Any,
    catalogo: dict[str, EntradaSic],
    de_byma: DatosDeBymaPorPapel,
    estrategia: Any,
    capturado_en: datetime,
) -> None:
    """Arma la fila y la escribe. Cada campo puede quedar `None` sin que eso invalide el resto: un
    papel del que sólo sabemos el nombre se guarda igual, declarando lo que falta."""
    sic = perfil.sic if perfil else None
    entrada = catalogo.get(sic) if sic else None
    division = division_de(sic)

    await guardar_clasificacion(
        conn,
        ticker,
        # El nombre de BYMA gana sobre el de la SEC: está en castellano y es el que el asesor
        # reconoce ("Ambev S.A." antes que "AMBEV S.A. /FI"). Sin él, el de la SEC sirve igual.
        nombre_largo=de_byma.nombre or (perfil.nombre if perfil else None),
        sic_codigo=sic,
        # El título de la SEC viene en el mismo pedido que el código; el del catálogo es el mismo
        # dato con otra capitalización. Se prefiere el del pedido y el catálogo completa si falta.
        sic_titulo=(perfil.sic_titulo if perfil else None) or (entrada.titulo if entrada else None),
        sic_oficina=entrada.oficina if entrada else None,
        division_cadena=division.eslabon if division else None,
        estrategia_etf=estrategia.clave if estrategia else None,
        # La geografía sale del mismo nombre y por el mismo criterio que la estrategia: leer lo que
        # el nombre dice. `None` cubre dos casos que no hace falta distinguir en la fila —no es un
        # fondo, o es un fondo cuyo nombre no nombra ninguna geografía—: los dos son "sin dato".
        region_etf=region_declarada(de_byma.nombre or (perfil.nombre if perfil else None)),
        ratio_conversion=de_byma.ratio,
        mercado_origen=de_byma.mercado,
        fuente=FUENTE,
        capturado_en=capturado_en,
    )


# --- Reclasificación de fondos, sin tocar la SEC -------------------------------------------------


@dataclass(frozen=True, slots=True)
class ResumenReclasificacion:
    """Cuántos papeles se re-derivaron y cuántos quedaron con cada campo poblado.

    Los tres números se leen juntos: `procesados` es cuántas filas tenían nombre para parsear,
    `con_estrategia` cuántas de esas son fondos, y `con_region` cuántos de esos fondos nombran una
    geografía. La resta —fondos sin geografía— no es un faltante a resolver: un `XLK` sectorial no
    dice dónde compra y no se le inventa.
    """

    procesados: int
    con_estrategia: int
    con_region: int

    def como_dict(self) -> dict[str, object]:
        return {
            "procesados": self.procesados,
            "con_estrategia": self.con_estrategia,
            "con_region": self.con_region,
        }


async def reclasificar_etfs(conn: Any) -> ResumenReclasificacion:
    """Re-deriva `estrategia_etf` y `region_etf` desde el `nombre_largo` ya persistido.

    **No le pregunta nada a la SEC ni a BYMA**, y ese es el punto: las dos columnas no son dato de
    esas fuentes, son el resultado de parsear un nombre que ya está en la base. Cuando el
    vocabulario de `etfs.py` cambia hace falta reescribirlas sobre el universo entero, y el camino
    normal —`POST /jobs/clasificar-renta-variable`— tardaría diecisiete corridas de 100 papeles
    barriendo la SEC para no cambiar nada de lo que la SEC aporta.

    Puro e idempotente: sin red, sin reloj, sin límite por corrida. Correrlo dos veces seguidas deja
    la base igual, y correrlo con el vocabulario sin cambios no modifica una sola fila.

    Efecto lateral deseado: alinea `estrategia_etf` con `nombre_largo`. La corrida contra la SEC la
    deriva del nombre que trae la lista de CEDEARs de BYMA, que puede faltar aunque el de la SEC
    esté; acá las dos columnas salen del mismo nombre, el que la fila realmente guarda.
    """
    filas = await nombres_persistidos(conn)

    a_escribir: list[tuple[str, str | None, str | None]] = []
    con_estrategia = con_region = 0
    for ticker, nombre in filas:
        estrategia = estrategia_de(nombre)
        region = region_declarada(nombre)
        clave = estrategia.clave if estrategia else None
        if clave is not None:
            con_estrategia += 1
        if region is not None:
            con_region += 1
        a_escribir.append((ticker, clave, region))

    await guardar_reclasificacion(conn, a_escribir)

    logger.info(
        "reclasificacion_etfs_termino",
        procesados=len(filas),
        con_estrategia=con_estrategia,
        con_region=con_region,
    )
    return ResumenReclasificacion(
        procesados=len(filas), con_estrategia=con_estrategia, con_region=con_region
    )
