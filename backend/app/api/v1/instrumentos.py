"""Endpoints de la ficha de instrumento — F-039, más sensibilidad — F-040.

Vive separado de `universo.py` porque responde una pregunta distinta — "todo lo que se sabe de ESTE
ticker" contra "el universo entero paginado" — y de `condiciones.py` porque ese es el dato curado
como colección y acá se pide por especie. Cuatro recursos de sólo lectura, cada uno independiente:
- `/{ticker}`: la especie más sus hermanas de liquidación (F-011), vía `ficha_de`.
- `/{ticker}/condiciones`: el mismo triplete `campo/campo_origen/campo_fecha` que ya devuelve
  `GET /condiciones`, filtrado a un ticker.
- `/{ticker}/cronograma`: los pagos futuros del cronograma, por 100 de VN y en la moneda de emisión
  — sin pasar por paridad, que es lo que hace F-016/F-021 para expresarlos como plata.
- `/{ticker}/sensibilidad`: cuánto se movería el precio si la TIR vigente comprimiera o se abriera,
  por repricing completo del cashflow contractual (F-040) — nunca la aproximación por duración.

Los cuatro pueden fallar por separado en el frontend (F-039, Parte 2: queries independientes) y por
eso acá también son cuatro endpoints y no uno que junte todo: una ficha de precios que se puede
mostrar aunque el cronograma no cargue no puede depender de un solo request que falle entero.
"""

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.calendario.cupones import indexar_cronograma
from app.calendario.lectura import leer_cashflow
from app.calendario.metricas import retorno_por_tir
from app.condiciones.persistencia import COLUMNAS, TABLA, fila_para_api
from app.ingesta.raiz import raiz_emision
from app.instrumentos import ficha_de
from app.universo.segmentacion import NOMBRE_NATURALEZA, EspecieUniverso
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/instrumentos", tags=["instrumentos"])

# Escenarios de movimiento de la TIR, en bps. Los mismos del motor (tools/detectar_swaps.py:71):
# cinco compresiones, el escenario nulo y dos aperturas. El 0 no es decorativo — es la
# autoconsistencia del repricing a la vista (retorno exactamente 0).
ESCENARIOS_BPS: tuple[int, ...] = (-500, -400, -300, -200, -100, 0, 100, 200)

# Naturaleza cuyo rendimiento es TNA nominal en pesos: no es una tasa efectiva descontable (regla 2
# del proyecto). Cubre tasa_fija, badlar y tamar (ver NATURALEZA_TASA en universo/segmentacion.py).
NATURALEZA_TNA_NOMINAL = "tna_nominal_ars"

# Mismas columnas que `GET /condiciones`, filtradas a un solo ticker: la forma de la fila no cambia,
# sólo el WHERE. No se redefine la lista de columnas — divergiría de la semilla en cuanto alguien
# agregue un campo curado.
SQL_CONDICIONES_POR_TICKER = f"SELECT {', '.join(COLUMNAS)} FROM public.{TABLA} WHERE ticker = $1"


@router.get(
    "/{ticker}",
    summary="La especie pedida más sus hermanas de liquidación",
    responses={
        404: {"description": "El ticker no está en el universo de hoy"},
        503: {"description": "La base de datos no está disponible"},
    },
)
async def instrumento(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """El mismo bono en sus especies de liquidación (GWT-1): precio, moneda y volumen de cada una,
    nunca sumados ni promediados entre sí — son tickers distintos del mismo instrumento.

    404 y no una ficha vacía: no se inventa una ficha para un ticker que no cotiza hoy.
    """
    resultado = await ficha_de(conn, ticker)
    if resultado is None:
        raise HTTPException(404, detail=f"{ticker} no está en el universo de hoy")
    return resultado


@router.get(
    "/{ticker}/condiciones",
    summary="Las condiciones de emisión curadas de un ticker, con origen y fecha",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def condiciones(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Ley, moneda de pago, lámina, calificación, sector y emisor, cada uno con de dónde salió y
    cuándo (GWT-4). `condiciones: null` cuando el ticker no tiene fila curada: no es un 404, es un
    estado normal y declarado — que no haya condiciones curadas no es que el ticker no exista.
    """
    fila = await conn.fetchrow(SQL_CONDICIONES_POR_TICKER, ticker)
    return {"ticker": ticker, "condiciones": fila_para_api(fila) if fila is not None else None}


@router.get(
    "/{ticker}/cronograma",
    summary="Los pagos futuros del cronograma, por 100 de VN y en la moneda de emisión",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def cronograma(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """El flujo de fondos hasta el vencimiento, distinguiendo interés de amortización (GWT-3).

    Los montos vienen tal como los publica la fuente — por 100 nominales, en la moneda de emisión,
    sin pasar por paridad ni convertir a fracción del invertido: eso es lo que hacen los cálculos de
    cartera (F-016/F-021), y esta ficha muestra el dato crudo, no una proyección.

    Sin cronograma para la raíz de este ticker: `pagos: []`, declarado y no 404 — puede ser
    legítimamente un instrumento sin cashflow cargado en la fuente.
    """
    filas = await leer_cashflow(conn)
    pagos = indexar_cronograma(filas).pagos_de(raiz_emision(ticker))
    moneda = await _moneda_de_emision(conn, ticker)
    return {
        "ticker": ticker,
        "pagos": [
            {
                "fecha": pago.fecha.isoformat(),
                "interes": pago.interes,
                "amortizacion": pago.capital,
                "moneda": moneda,
            }
            for pago in pagos
        ],
    }


async def _especie_de(conn: Any, ticker: str) -> EspecieUniverso | None:
    """La especie del universo saneado de hoy, o `None` si el ticker no está."""
    saneado = await sanear_universo(conn)
    return next((e for e in saneado.especies if e.ticker == ticker), None)


async def _moneda_de_emision(conn: Any, ticker: str) -> str | None:
    """La moneda de emisión del ticker, o `None` si ninguna fuente la da.

    El cronograma no trae moneda (`COLUMNAS_CASHFLOW` no la tiene), así que se busca en el universo
    saneado: es lo único de acá que puede contestar en qué moneda paga el bono. No se infiere del
    sufijo del ticker ni de ninguna otra convención — la regla 1 del proyecto.
    """
    especie = await _especie_de(conn, ticker)
    return especie.moneda_cupon if especie is not None else None


@router.get(
    "/{ticker}/sensibilidad",
    summary="Cuánto se movería el precio si la TIR vigente comprimiera o se abriera",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def sensibilidad(ticker: str, conn: Annotated[object, Depends(get_db)]) -> dict[str, object]:
    """Repricing completo del cashflow contractual a la TIR de cada escenario (GWT-1): se descuentan
    todos los flujos futuros a la TIR nueva y se compara contra descontarlos a la TIR vigente. Nunca
    la aproximación lineal por duración — en bonos largos subestima fuerte la suba ante compresiones
    grandes, y esos son justamente los escenarios que interesan.

    Siempre 200 con una declaración (GWT-3): sin TIR vigente en una unidad descontable, sin
    cronograma o sin pagos futuros, `calculable` sale `false` con su `motivo` y nunca se cae a
    duración x delta. Un ticker fuera del universo de hoy también da 200 y no 404: éste es un
    endpoint derivado, y el 404 de "el ticker no existe" ya lo da la ficha del instrumento.
    """

    def _sin_calcular(motivo: str, especie: EspecieUniverso | None = None) -> dict[str, object]:
        nombre = NOMBRE_NATURALEZA[especie.naturaleza] if especie is not None else None
        return {
            "ticker": ticker,
            "tir_actual": especie.rendimiento if especie is not None else None,
            "naturaleza": especie.naturaleza if especie is not None else None,
            "naturaleza_nombre": nombre,
            "calculable": False,
            "motivo": motivo,
            "escenarios": [],
            "omitidos_bps": [],
        }

    especie = await _especie_de(conn, ticker)
    if especie is None:
        return _sin_calcular("no está en el universo de hoy: no hay TIR vigente para descontar")

    if especie.naturaleza == NATURALEZA_TNA_NOMINAL:
        return _sin_calcular(
            "el rendimiento de este segmento es TNA nominal en pesos, no una tasa efectiva "
            "descontable: no se calcula",
            especie,
        )

    if especie.rendimiento is None:
        return _sin_calcular("sin TIR vigente publicada ni calculada hoy", especie)

    filas = await leer_cashflow(conn)
    pagos = indexar_cronograma(filas).pagos_de(raiz_emision(ticker))
    if not pagos:
        return _sin_calcular("sin cronograma de pagos en la fuente", especie)

    hoy = date.today()
    if not any(p.fecha > hoy for p in pagos):
        return _sin_calcular("sin pagos futuros: la emisión ya venció", especie)

    deltas = [d / 10_000 for d in ESCENARIOS_BPS]
    r = retorno_por_tir(pagos, especie.rendimiento, deltas, hoy)
    if r is None:
        return _sin_calcular(
            "valor presente no positivo a la TIR vigente: no hay base de repricing", especie
        )

    escenarios = [
        {
            "delta_bps": d,
            "tir_escenario": especie.rendimiento + (d / 10_000),
            "retorno": r[d / 10_000],
        }
        for d in ESCENARIOS_BPS
        if (d / 10_000) in r
    ]
    omitidos_bps = [d for d in ESCENARIOS_BPS if (d / 10_000) not in r]

    return {
        "ticker": ticker,
        "tir_actual": especie.rendimiento,
        "naturaleza": especie.naturaleza,
        "naturaleza_nombre": NOMBRE_NATURALEZA[especie.naturaleza],
        "calculable": True,
        "motivo": None,
        "escenarios": escenarios,
        "omitidos_bps": omitidos_bps,
    }
