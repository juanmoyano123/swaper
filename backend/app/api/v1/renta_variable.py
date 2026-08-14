"""Endpoints de renta variable — F-052.

Base común de la tanda 8b: el router se creó vacío y se montó en `router.py` antes de soltar los
agentes, para que F-052 no tuviera que editar un archivo que comparte con las otras tres features de
la tanda. Es la lección de la Tanda 1 — lo que colisionó no fue el código de las features, fueron
los archivos compartidos que ninguna había previsto.

**Por qué existe este módulo y no un parámetro más en `universo.py`.** La renta variable no está en
el listado del universo y no es un descuido: `segmentar()` la descarta *antes* de segmentar, porque
una acción no tiene TIR, ni duración, ni cronograma, y nunca fue comparable con un bono.
`Segmentacion.renta_variable` es un contador, no una lista — las filas se cuentan y se sueltan. Y
`EspecieUniverso` no puede representarlas: su `naturaleza` busca el segmento en `NATURALEZA_TASA` y
una acción no tiene ninguno.

Así que acá se lee aparte, con el mismo criterio que `posiciones/lectura.py` ya usa por esta misma
razón: SQL propio contra el universo consolidado, filtrando por `clase_activo`. El precedente está
escrito allá y conviene mirarlo antes de escribir el de acá.

**Lo que este recurso no va a tener nunca es una columna de rendimiento.** Ni TIR, ni nada puesto en
su lugar. Una acción no tiene TIR y presentar otra magnitud en esa columna sería exactamente lo que
la regla 2 prohíbe — y el hecho de que desde F-051 el universo de renta fija tenga TIR calculada no
cambia nada acá.
"""

import asyncio
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.pagination import CursorParams, Page, build_page
from app.externos import bloque_pausado, cliente_yahoo
from app.externos.data912 import cliente_data912_historico
from app.externos.sec_ficha import cliente_sec_ficha
from app.renta_variable import EspecieRentaVariable, armar_renta_variable, leer_renta_variable
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/renta-variable", tags=["renta variable"])

# El bloque propio lleva su fuente escrita al lado del dato, igual que el externo: en una ficha que
# junta dos orígenes, cuál es cuál no puede quedar librado a que el lector se acuerde.
#
# Experimento data912: hoy `especie.fuente` (de la vista `resumen`) es la fuente real, más precisa
# que esta constante — distingue BYMA de data912 y de data912-arrastre. `FUENTE_PROPIA` queda como
# el fallback de una corrida anterior a la migración que la expone (`especie.fuente is None`).
FUENTE_PROPIA = "BYMA"


@router.get(
    "/especies",
    summary="Las acciones y CEDEARs del día, con puntas, variación y volumen en dólares",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def especies(
    conn: Annotated[object, Depends(get_db)],
    params: Annotated[CursorParams, Depends()],
    clase: Annotated[
        Literal["accion", "cedear"],
        Query(description="Qué pestaña de renta variable se pide. Obligatorio: sin él, 422."),
    ],
) -> Page[dict[str, object]]:
    """Acciones o CEDEARs del universo, con precio, variación, volumen en dólares y puntas.

    El tipo de cambio sale de `sanear_universo(conn).cambio` — el MEP implícito derivado de la
    renta fija del propio universo (regla 3) — y no de ninguna otra fuente, aunque esta especie
    no sea renta fija. Una clase sin filas hoy devuelve página vacía, no 404: no es un error, es
    el estado real de la primera corrida después de que BYMA deje de publicar algo, o del primer
    día sin ninguna acción cargada.
    """
    # sólo se usa saneado.cambio: el FX del día sale del propio universo, regla 3
    saneado = await sanear_universo(conn)
    filas = await leer_renta_variable(conn)
    listado = [e for e in armar_renta_variable(filas, saneado.cambio) if e.clase_activo == clase]

    desde = params.decoded_cursor()
    if desde is not None:
        ultimo = str(desde.get("ticker", ""))
        listado = [e for e in listado if e.ticker > ultimo]

    filas_api = [e.como_dict() for e in listado[: params.limit + 1]]
    return build_page(filas_api, params.limit, lambda f: {"ticker": f["ticker"]})


async def _especie_de(conn: Any, ticker: str) -> EspecieRentaVariable | None:
    """La especie de renta variable del universo de hoy, o `None`.

    Se lee el listado entero y se filtra en memoria en vez de agregarle un WHERE a la lectura: es la
    misma consulta que ya sirve al monitor, y duplicar el SQL para un solo ticker haría que un
    cambio en una de las dos lecturas dejara la otra desalineada sin que nada avise.
    """
    saneado = await sanear_universo(conn)
    filas = await leer_renta_variable(conn)
    pedido = ticker.strip().upper()
    especies = armar_renta_variable(filas, saneado.cambio)
    return next((e for e in especies if e.ticker.upper() == pedido), None)


@router.get(
    "/{ticker}/ficha",
    summary="La ficha de una acción o un CEDEAR: lo nuestro de BYMA, el histórico de data912, los "
    "estados contables de la SEC y el bloque externo de Yahoo",
    responses={
        404: {"description": "El ticker no es renta variable del universo de hoy"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def ficha(
    ticker: str,
    conn: Annotated[object, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, object]:
    """Cuatro bloques con su fuente a la vista, y la ficha se muestra aunque cualquiera de los
    últimos tres falte.

    **El bloque propio** —precio, cierre anterior, variación, puntas, operaciones, apertura, rango
    del día, VWAP— sale del universo consolidado de BYMA y es el que sostiene la pantalla. **El
    bloque externo** es Yahoo Finance, rotulado con su fuente y la hora en que se lo capturó, y
    puede venir declarado no disponible sin que eso rompa nada: Yahoo no publica una API y sus
    endpoints no son contractuales (ver `app/externos/yahoo.py`).

    **Con `settings.yahoo_habilitado` en `False` (el default desde el 13/08/2026) no se le pide
    nada a Yahoo**: el bloque externo llega directamente como `bloque_pausado()`, con el motivo de
    la pausa en castellano. Es la misma forma que un fallo de red — el frontend no necesita
    distinguir los dos casos — y evita el único costo real de la pausa: seguir gastando cuota contra
    una fuente que ya nos tiene limitados.

    Lo que el bloque externo **nunca** trae es recomendación de analistas, precio objetivo ni
    consenso: es opinión de terceros y la regla 6 del dominio mantiene el análisis determinístico.
    Y los valores propietarios de Yahoo viajan tal como la fuente los declara, sin traducir
    (regla 11).

    **El tercer bloque, `historico`**, es el sparkline de cierres diarios — de data912, no de
    Yahoo: cubre más papeles y más años de los que Yahoo daba, y no depende de la pausa. Mismo
    contrato que `externo`: rotulado, y declarado ausente sin romper el resto de la ficha si
    data912 no tiene la serie de este ticker.

    **El cuarto bloque, `sec`**, es el paquete de estados contables (14/08/2026): activos,
    pasivos, patrimonio, ROE, márgenes y links a los filings reales — **sólo para CEDEARs**
    (decisión del dueño del producto: las acciones argentinas se sacaron de la UI). Para las
    empresas que reportan ante la SEC como emisor privado extranjero (la mayoría de los CEDEARs
    sudamericanos) declara `solo_anual=true`: la fuente no publica trimestral para ellas, y se
    dice en vez de esconderse.

    404 y no una ficha vacía cuando el ticker no es renta variable del universo de hoy: es también
    lo que le permite al frontend distinguir una acción de un bono sin adivinarlo por el ticker.
    """
    especie = await _especie_de(conn, ticker)
    if especie is None:
        raise HTTPException(404, detail=f"{ticker} no es renta variable del universo de hoy")

    # `historico` y `sec` siempre van en paralelo: son dos fuentes independientes que nunca se
    # bloquean entre sí. `externo` se suma al mismo `gather` sólo cuando Yahoo está habilitado —
    # pausado, `bloque_pausado()` no hace red y no tiene sentido esperarlo junto a los otros dos.
    if settings.yahoo_habilitado:
        externo, historico, sec = await asyncio.gather(
            cliente_yahoo().bloque_externo(especie.ticker),
            cliente_data912_historico().bloque_historico(especie.ticker, especie.clase_activo),
            cliente_sec_ficha().bloque_sec(especie.ticker, especie.clase_activo, especie.emision),
        )
    else:
        externo = bloque_pausado(especie.ticker)
        historico, sec = await asyncio.gather(
            cliente_data912_historico().bloque_historico(especie.ticker, especie.clase_activo),
            cliente_sec_ficha().bloque_sec(especie.ticker, especie.clase_activo, especie.emision),
        )
    return {
        "ticker": especie.ticker,
        # `**especie.como_dict()` va primero: si trae `fuente` (experimento data912), gana sobre
        # la constante. Si no (corrida anterior a la migración, `fuente is None`), el `or` la pisa.
        "propio": {**especie.como_dict(), "fuente": especie.fuente or FUENTE_PROPIA},
        "externo": externo.como_dict(),
        "historico": historico.como_dict(),
        "sec": sec.como_dict(),
    }
