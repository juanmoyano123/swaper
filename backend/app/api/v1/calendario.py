"""Endpoints del calendario de doce meses — F-015.

Router vacío a propósito, creado antes que la feature. Es el mismo arreglo que las tres fuentes
de la Tanda 1: F-015 y F-029 se construyen en paralelo y las dos tendrían que registrarse en
`api/v1/router.py` al terminar, o sea editar el mismo archivo a la vez. Se monta acá de entrada y
cada feature agrega sus rutas a su propio módulo.

**El calendario es el criterio de armado, no un reporte.** Lo dice la regla 5 del proyecto, y por
eso este recurso es el que alimenta la grilla-selector de F-016 y el panel de renta de F-021: las
tres leen la misma estructura de doce meses en vez de recalcularla cada una con su criterio.

## Por qué la grilla no se pagina

Todas las colecciones de este API se paginan por cursor, y ésta no. La diferencia es que la grilla
**no es una colección**: es una estructura de tamaño fijo de doce meses donde el mes vacío importa
tanto como el lleno. Paginarla haría imposible garantizar lo que la spec pide —los doce meses
siempre presentes, con cero explícito— porque una página podría cortar entre septiembre y octubre y
el consumidor tendría que reconstruir la continuidad del ingreso a partir de pedazos.

Lo que sí puede crecer es el detalle por instrumento adentro de cada mes, y por eso existe
`?detalle=false`: quien sólo quiere saber qué meses quedan descubiertos —el panel de F-021— no
necesita traerse la lista entera de instrumentos que pagan.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.calendario.servicio import calendario_de_cartera, calendario_del_universo

router = APIRouter(prefix="/calendario", tags=["calendario"])

MAX_POSICIONES = 500


class PosicionEntrada(BaseModel):
    """Una posición de la cartera: qué especie y cuánto hay puesto en ella.

    Es **la especie** y no la emisión: el asesor tiene RUCED o RUCEO, no "la emisión RUCE", y las
    dos tienen paridades distintas porque cotizan en monedas distintas. Calcular la renta con la
    paridad de la hermana daría un número que no es el de la posición que se tiene.
    """

    ticker: str = Field(min_length=1, max_length=20)
    monto: float = Field(gt=0)
    """El monto invertido, **en la moneda en la que se compró la especie**. Es lo que hace que la
    cuenta cierre: el flujo por peso es adimensional, así que multiplicarlo por este monto devuelve
    plata en esta misma moneda. Por eso los totales del mes salen abiertos por moneda."""


class CarteraEntrada(BaseModel):
    posiciones: list[PosicionEntrada] = Field(min_length=1, max_length=MAX_POSICIONES)


@router.get(
    "/universo",
    summary="La grilla de doce meses del universo: qué instrumentos pagan cada mes",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def universo(
    conn: Annotated[object, Depends(get_db)],
    detalle: Annotated[
        bool, Query(description="Si cada mes trae la lista de instrumentos que pagan.")
    ] = True,
) -> dict[str, object]:
    """Los doce meses que vienen, con los instrumentos que pagan en cada uno.

    Es lo que consume la grilla-selector de F-016. Los montos vienen como **fracción del monto que
    se invierta** en cada instrumento (`pct_renta`, `pct_amortizacion`): multiplicando por la plata
    que se le ponga se obtiene el cobro, en la moneda de esa inversión. No hay totales por mes acá —
    sumar fracciones de instrumentos distintos no daría plata ni ninguna otra cosa que signifique
    algo — y en su lugar cada mes dice cuántos instrumentos pagan renta y cuántos amortizan.

    **La ventana arranca el mes que viene.** Los cupones de este mes anteriores a hoy ya se
    cobraron, y dejar el mes en curso en la grilla lo marcaría como mes sin renta casi todos los
    días del mes. Los pagos que faltan de este mes se cuentan en `resumen.pendientes_este_mes`.

    Trabaja sobre el universo saneado y **colapsado**: una fila por emisión. Mostrar las tres
    especies de liquidación del mismo bono como tres candidatos para tapar un mes vacío haría creer
    que se diversifica comprando tres veces el mismo crédito.
    """
    calendario = await calendario_del_universo(conn)
    return calendario.como_dict(detalle=detalle)


@router.post(
    "/cartera",
    summary="La grilla de doce meses de una cartera concreta, en plata",
    responses={503: {"description": "La base de datos no está disponible"}},
)
async def cartera(
    conn: Annotated[object, Depends(get_db)],
    entrada: CarteraEntrada,
    detalle: Annotated[
        bool, Query(description="Si cada mes trae la lista de instrumentos que pagan.")
    ] = True,
) -> dict[str, object]:
    """La renta y la amortización mes a mes de una cartera dada, abiertas por moneda de cobro.

    Es lo que consumen el panel de renta de F-021 y la comparación de F-036. Va por POST y con las
    posiciones en el cuerpo —no por query string— porque lo que entra son pares ticker/monto y
    porque una cartera real tiene decenas de posiciones: meterlas en la URL las expondría en cada
    log de acceso y chocaría con el límite de largo mucho antes de lo que parece.

    **Las posiciones se pasan explícitas y no por identificador de cartera**: este servicio calcula
    el calendario de lo que se le da, y así sirve igual para una cartera guardada, para una
    propuesta que todavía no existe y para el "antes y después" de un swap, que es justamente lo que
    F-036 necesita comparar.

    Un ticker repetido suma sus montos: son dos compras de la misma especie, y en el calendario
    cobra como una sola posición. Una posición que hoy no está en el universo no se calcula y **se
    nombra en las alertas**: la renta proyectada sale más chica de lo que es, y eso hay que decirlo.
    """
    montos: dict[str, float] = {}
    for posicion in entrada.posiciones:
        montos[posicion.ticker] = montos.get(posicion.ticker, 0.0) + posicion.monto
    calendario = await calendario_de_cartera(conn, montos)
    return calendario.como_dict(detalle=detalle)
