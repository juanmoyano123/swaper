"""Endpoints de la ficha de instrumento — F-039.

Vive separado de `universo.py` porque responde una pregunta distinta — "todo lo que se sabe de ESTE
ticker" contra "el universo entero paginado" — y de `condiciones.py` porque ese es el dato curado
como colección y acá se pide por especie. Tres recursos de sólo lectura, cada uno independiente:
- `/{ticker}`: la especie más sus hermanas de liquidación (F-011), vía `ficha_de`.
- `/{ticker}/condiciones`: el mismo triplete `campo/campo_origen/campo_fecha` que ya devuelve
  `GET /condiciones`, filtrado a un ticker.
- `/{ticker}/cronograma`: los pagos futuros del cronograma, por 100 de VN y en la moneda de emisión
  — sin pasar por paridad, que es lo que hace F-016/F-021 para expresarlos como plata.

Los tres pueden fallar por separado en el frontend (F-039, Parte 2: tres queries independientes) y
por eso acá también son tres endpoints y no uno que junte todo: una ficha de precios que se puede
mostrar aunque el cronograma no cargue no puede depender de un solo request que falle entero.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.calendario.cupones import indexar_cronograma
from app.calendario.lectura import leer_cashflow
from app.condiciones.persistencia import COLUMNAS, TABLA
from app.ingesta.consolidacion import raiz_emision
from app.instrumentos import ficha_de
from app.universo.servicio import sanear_universo

router = APIRouter(prefix="/instrumentos", tags=["instrumentos"])

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
    return {"ticker": ticker, "condiciones": dict(fila) if fila is not None else None}


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


async def _moneda_de_emision(conn: Any, ticker: str) -> str | None:
    """La moneda de emisión del ticker, o `None` si ninguna fuente la da.

    El cronograma no trae moneda (`COLUMNAS_CASHFLOW` no la tiene), así que se busca en el universo
    saneado: es lo único de acá que puede contestar en qué moneda paga el bono. No se infiere del
    sufijo del ticker ni de ninguna otra convención — la regla 1 del proyecto.
    """
    saneado = await sanear_universo(conn)
    especie = next((e for e in saneado.especies if e.ticker == ticker), None)
    return especie.moneda_cupon if especie is not None else None
