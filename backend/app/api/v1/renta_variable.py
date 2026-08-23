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
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.core.pagination import CursorParams, Page, build_page
from app.externos.data912 import cliente_data912_historico
from app.externos.sec_calendario import cliente_sec_calendario
from app.externos.sec_ficha import cliente_sec_ficha
from app.renta_variable import EspecieRentaVariable, armar_renta_variable, leer_renta_variable
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/renta-variable", tags=["renta variable"])

# Una cartera real no supera unas pocas decenas de CEDEARs; el tope está para no convertir el
# endpoint en un scraper masivo de la SEC desde un solo pedido.
MAX_PAPELES_BALANCES = 40

# La SEC admite ~10 pedidos por segundo (ver `externos/sec.py`); se pide a la mitad de ese ritmo.
MAX_CONCURRENCIA_SEC = 5

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
    summary="La ficha de una acción o un CEDEAR: lo nuestro de BYMA, el histórico de data912 y los "
    "estados contables de la SEC",
    responses={
        404: {"description": "El ticker no es renta variable del universo de hoy"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def ficha(
    ticker: str,
    conn: Annotated[object, Depends(get_db)],
) -> dict[str, object]:
    """Tres bloques con su fuente a la vista, y la ficha se muestra aunque cualquiera de los dos
    últimos falte.

    **El bloque propio** —precio, cierre anterior, variación, puntas, operaciones, apertura, rango
    del día, VWAP— sale del universo consolidado de BYMA y es el que sostiene la pantalla.

    Lo que la ficha **nunca** trae es recomendación de analistas, precio objetivo ni consenso: es
    opinión de terceros y la regla 6 del dominio mantiene el análisis determinístico.

    **El segundo bloque, `historico`**, es el sparkline de cierres diarios de data912: rotulado, y
    declarado ausente sin romper el resto de la ficha si la fuente no tiene la serie de este
    ticker.

    **El tercer bloque, `sec`**, es el paquete de ratios financieros (14/08/2026): ROE, margen
    operativo, crecimiento de ingresos, EPS, deuda/patrimonio y liquidez corriente, calculados
    sobre XBRL de `companyfacts` — **sólo para CEDEARs** (decisión del dueño del producto: las
    acciones argentinas se sacaron de la UI). `assets`/`liabilities`/`equity` se parsean para el
    cálculo pero no se serializan acá (ver `sec_ficha.py::_ratios_como_dict`). Para las empresas
    que reportan ante la SEC como emisor privado extranjero (la mayoría de los CEDEARs
    sudamericanos) declara `solo_anual=true`: la fuente no publica trimestral para ellas, y se
    dice en vez de esconderse.

    404 y no una ficha vacía cuando el ticker no es renta variable del universo de hoy: es también
    lo que le permite al frontend distinguir una acción de un bono sin adivinarlo por el ticker.
    """
    especie = await _especie_de(conn, ticker)
    if especie is None:
        raise HTTPException(404, detail=f"{ticker} no es renta variable del universo de hoy")

    # `historico` y `sec` van en paralelo: son dos fuentes independientes que nunca se bloquean
    # entre sí.
    historico, sec = await asyncio.gather(
        cliente_data912_historico().bloque_historico(especie.ticker, especie.clase_activo),
        cliente_sec_ficha().bloque_sec(especie.ticker, especie.clase_activo, especie.emision),
    )
    return {
        "ticker": especie.ticker,
        # `**especie.como_dict()` va primero: si trae `fuente` (experimento data912), gana sobre
        # la constante. Si no (corrida anterior a la migración, `fuente is None`), el `or` la pisa.
        "propio": {**especie.como_dict(), "fuente": especie.fuente or FUENTE_PROPIA},
        "historico": historico.como_dict(),
        "sec": sec.como_dict(),
    }


class PapelesEntrada(BaseModel):
    """Los papeles a consultar. Van por POST y no por query string por el mismo motivo que
    `POST /calendario/cartera`: es una lista, no un solo valor, y crece con el tamaño de la
    cartera."""

    papeles: list[str] = Field(min_length=1, max_length=MAX_PAPELES_BALANCES)


@router.post(
    "/balances",
    summary="El patrón mensual de presentación de balances de una lista de CEDEARs — F-027",
    responses={422: {"description": "Sin papeles, o más de los que admite un solo pedido"}},
)
async def balances(entrada: PapelesEntrada) -> dict[str, object]:
    """El calendario de F-027: en qué mes cada CEDEAR suele presentar su balance ante la SEC,
    como patrón histórico derivado de `submissions/CIK.json` — nunca una fecha confirmada.

    **Se reciben papeles ya resueltos, no tickers de especie.** El llamador (el bloque de renta
    variable del armador) ya sabe qué papel de la SEC corresponde a cada posición —`emision` si
    lo tiene, si no el ticker— porque es el mismo dato que resuelve la ficha de F-053. Este
    endpoint no vuelve a tocar la base para reconstruirlo.

    Un papel repetido en la lista se pide una sola vez. Cada elemento de la respuesta corresponde
    a un papel pedido, disponible o declarado ausente por igual: no hay 404 por papel, porque un
    CEDEAR sin patrón detectable en la SEC es un resultado válido, no un error.
    """
    papeles = list(dict.fromkeys(p.strip().upper() for p in entrada.papeles if p.strip()))
    if not papeles:
        return {"calendarios": []}

    semaforo = asyncio.Semaphore(MAX_CONCURRENCIA_SEC)
    cliente = cliente_sec_calendario()

    async def _uno(papel: str) -> dict[str, object]:
        async with semaforo:
            calendario = await cliente.calendario_de(papel, "cedear", None)
        return calendario.como_dict()

    calendarios = await asyncio.gather(*(_uno(papel) for papel in papeles))
    return {"calendarios": list(calendarios)}
