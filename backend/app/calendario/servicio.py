"""El calendario como una sola llamada: leer, cruzar y armar la grilla — F-015.

Es el equivalente de `app/universo/servicio.py`: junta la capa de lectura con las funciones puras y
devuelve lo que se reporta. La conexión llega **por parámetro y no de `app.state`** para que un job
pueda invocarlo fuera del ciclo HTTP, igual que hace `sanear_universo`.

## Las dos vistas, y por qué no son la misma llamada con un flag

- **`calendario_del_universo`** trabaja sobre la vista **colapsada** (F-011): una fila por emisión.
  Es la que consume F-016, donde el asesor elige qué comprar, y ahí una emisión tiene que valer uno
  — mostrar MR46O, MR46D y MR46C como tres candidatos distintos para tapar un mes vacío haría creer
  que se diversifica cuando se está comprando el mismo bono tres veces.
- **`calendario_de_cartera`** trabaja sobre la vista **viva**: todas las especies. Es la que
  consumen F-021 y F-036, y ahí el asesor **tiene** RUCED, no "la emisión RUCE": si se lo buscara
  en la vista colapsada y el representante de esa emisión fuera RUCEO, la posición desaparecería
  del calendario. Además la paridad es de la especie, así que la plata sale bien sólo mirando la
  que se tiene.

## El universo llega saneado, y sin salir a la red

Las dos parten de `sanear_universo(conn)` y no de la lectura cruda, por lo mismo que F-011 y F-012:
calcular la renta de una especie cuyo precio está mal escalado sería propagar el error en vez de
contenerlo. Y se pide **sin contraste** (`con_contraste=False`, el default): el índice de BYMA es lo
único de aquel servicio que sale a la red y este calendario no lo necesita para nada — el tipo de
cambio no interviene, porque la paridad ya es adimensional.

## Lo que este servicio hereda y no puede arreglar

`flujos_por_peso` necesita paridad, y la paridad existe **sólo para el ticker exacto que la tiene
calculada** — hoy, las especies donde el precio y el flujo comparten moneda; en la medición de
abajo, las que IAMC nombraba en su informe. La forma del agujero es la misma en los dos casos: la
paridad es de una especie y no se copia a sus hermanas. Medido contra la base del 7/08/2026:

- 241 de 2.894 filas de `resumen` tienen paridad, y 240 tienen TIR. Son casi las mismas filas.
- Sobre la vista **colapsada**, de 431 emisiones el calendario calcula **70**. Las 360 restantes
  quedan afuera por falta de paridad, y **ninguna de ellas declara rendimiento ni duración**: el
  representante que eligió F-011 no era el ticker con métricas. Es exactamente el efecto que
  `emisiones.py` cuenta como `rendimiento_perdido_al_colapsar`, llegando hasta acá.
- Los cuatro tickers del GWT-4 de la spec —RUCED, SBC2D, CS47D y LOC5D— **hoy no se pueden
  calcular** con el dato de la base: sus métricas están en RUCEO, SBC2O, CS47O y LOC5O. En el
  consolidado versionado de `data/output/` estaban al revés, y por eso ahí sí se calculan.

Nada de eso se corrige acá —completar una paridad sería inventar el precio de un bono— pero sí
cambia qué se alerta: en una cartera, **toda posición que no se pudo calcular se nombra**, coticen
o no sus números. El motor sólo nombra a las que cotizan, y con ese criterio una cartera de esos
cuatro tickers devolvía doce meses de renta cero sin una sola advertencia.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date
from typing import Any

import structlog

from app.calendario.alertas import (
    cobertura_del_calendario,
    fuera_del_universo,
    posiciones_sin_calendario,
)
from app.calendario.cupones import (
    Cronograma,
    flujos_por_peso,
    indexar_cronograma,
    indexar_paridades,
)
from app.calendario.grilla import HORIZONTE_MESES, Calendario, armar_calendario
from app.calendario.lectura import leer_cashflow, leer_paridades
from app.ingesta.alertas import Alerta
from app.universo.segmentacion import EspecieUniverso
from app.universo.servicio import sanear_universo

logger = structlog.get_logger()


async def calendario_del_universo(
    conn: Any, *, hoy: date | None = None, horizonte: int = HORIZONTE_MESES
) -> Calendario:
    """La grilla de doce meses del universo entero, en fracciones del monto que se invierta.

    Es lo que consume la grilla-selector de F-016: por cada mes, qué instrumentos pagan, cuánto de
    renta y cuánto de amortización por peso invertido, con qué rendimiento y hasta cuándo.

    **Siempre declara cuánto del universo llegó a la grilla**, aunque no haya un solo caso que
    revisar. La pantalla de F-016 es donde el asesor mira el universo para elegir, así que mostrar
    un subconjunto sin decir que lo es haría creer que lo que no está no existe.
    """
    hoy = hoy or date.today()
    saneado = await sanear_universo(conn)
    especies = saneado.emisiones().colapsado()
    calendario = _declarar_la_cobertura(await _armar(conn, especies, hoy, horizonte, montos=None))
    logger.info(
        "calendario_universo",
        instrumentos=len(especies),
        con_flujos=len(calendario.flujos.tickers),
        sin_cronograma=len(calendario.flujos.sin_cronograma),
        sin_paridad=len(calendario.flujos.sin_paridad),
        # Los dos números, porque el segundo es el que se alerta y el primero el que explica la
        # cobertura: verlos separados es lo que evita leer "0 alertas" como "no falta nada".
        sin_paridad_que_cotizan=len(calendario.flujos.sin_paridad_que_cotizan),
        meses_sin_renta=len(calendario.meses_sin_renta),
    )
    return calendario


async def calendario_de_cartera(
    conn: Any,
    montos: Mapping[str, float],
    *,
    hoy: date | None = None,
    horizonte: int = HORIZONTE_MESES,
) -> Calendario:
    """La grilla de doce meses de una cartera concreta, en plata y abierta por moneda de cobro.

    `montos` es {ticker: monto invertido}. El monto está **en la moneda en la que se compró la
    especie**, que es la única forma en que la cuenta cierra: `pct x monto` devuelve plata en esa
    misma moneda porque el `pct` es adimensional. Por eso los totales del mes salen abiertos por
    moneda y nunca sumados entre sí.

    Las posiciones que no están en el universo de hoy **no se calculan y se nombran**: la renta del
    mes va a salir más chica de lo que es, y eso tiene que decirse en vez de descubrirse.
    """
    hoy = hoy or date.today()
    saneado = await sanear_universo(conn)
    vivas = {e.ticker: e for e in saneado.emisiones().vivo()}

    especies = [vivas[t] for t in sorted(montos) if t in vivas]
    ausentes = sorted(t for t in montos if t not in vivas)
    alertas = [fuera_del_universo(ausentes)] if ausentes else []

    calendario = await _armar(
        conn, especies, hoy, horizonte, montos=montos, alertas_de_la_vista=alertas
    )
    calendario = _nombrar_las_que_no_se_pudieron_calcular(calendario, especies)
    logger.info(
        "calendario_cartera",
        posiciones=len(montos),
        en_el_universo=len(especies),
        fuera_del_universo=len(ausentes),
        monedas=calendario.monedas,
        meses_sin_renta=len(calendario.meses_sin_renta),
    )
    return calendario


async def _armar(
    conn: Any,
    especies: Sequence[EspecieUniverso],
    hoy: date,
    horizonte: int,
    *,
    montos: Mapping[str, float] | None,
    alertas_de_la_vista: Sequence[Alerta] = (),
) -> Calendario:
    """Lo común a las dos vistas: leer el cronograma y las paridades, y repartirlos en la grilla.

    El cronograma y las paridades se leen enteros aunque la cartera tenga tres posiciones. Es
    deliberado: son dos consultas planas contra tablas chicas —6.150 pagos y 2.894 filas— y filtrar
    por ticker obligaría a armar un `IN` con la lista de la cartera, que es más SQL y más caminos
    para equivocarse a cambio de una diferencia de milisegundos.
    """
    cronograma = indexar_cronograma(await leer_cashflow(conn))
    paridades = indexar_paridades(await leer_paridades(conn))
    _avisar_cronograma_incompleto(cronograma)

    flujos = flujos_por_peso(especies, cronograma, paridades, hoy)
    return armar_calendario(
        flujos,
        especies,
        hoy,
        montos=montos,
        horizonte=horizonte,
        alertas_de_la_vista=alertas_de_la_vista,
    )


def _declarar_la_cobertura(calendario: Calendario) -> Calendario:
    """Agrega la alerta que dice qué proporción del universo llegó a la grilla.

    Es la contracara de `_nombrar_las_que_no_se_pudieron_calcular`: aquélla nombra posiciones porque
    la pregunta era por una cartera, y ésta mide una proporción porque la pregunta era por el
    universo. Las dos son alertas de la vista, no del cálculo, y por eso las arma el servicio.

    Va **siempre**, también cuando la cobertura es total: en ese caso sale como información. Que la
    alerta aparezca o no según el resultado obligaría a distinguir "no falta nada" de "nadie lo
    midió", y esos dos no se pueden distinguir mirando una lista vacía.
    """
    flujos = calendario.flujos
    return replace(
        calendario,
        alertas_de_la_vista=[
            *calendario.alertas_de_la_vista,
            cobertura_del_calendario(
                emisiones=flujos.evaluados,
                con_calendario=len(flujos.tickers),
                sin_paridad=len(flujos.sin_paridad),
                sin_cronograma=len(flujos.sin_cronograma),
                vencidos=len(flujos.vencidos),
            ),
        ],
    )


def _nombrar_las_que_no_se_pudieron_calcular(
    calendario: Calendario, especies: Sequence[EspecieUniverso]
) -> Calendario:
    """Agrega la alerta de las posiciones que están en el universo pero no entraron a la grilla.

    Vive acá y no en `flujos_por_peso` porque depende de **quién pregunta**: en la vista del
    universo un instrumento sin métricas es uno de cientos que no cotizan, y nombrarlos a todos
    taparía los
    casos que importan; en una cartera es una posición que el asesor tiene y cuya renta acaba de
    desaparecer del total del mes. La función pura junta la información de los dos casos y el
    servicio decide cuál corresponde.
    """
    motivos = {
        especie.ticker: motivo
        for especie in especies
        if (motivo := calendario.flujos.motivo_de(especie.ticker)) is not None
    }
    if not motivos:
        return calendario
    return replace(
        calendario,
        alertas_de_la_vista=[*calendario.alertas_de_la_vista, posiciones_sin_calendario(motivos)],
    )


def _avisar_cronograma_incompleto(cronograma: Cronograma) -> None:
    """Deja en el log los pagos que la fuente publicó incompletos.

    Va al log y no a las alertas del calendario porque no habla de ningún instrumento en particular:
    es un problema de la ingesta, y quien tiene que verlo es quien mira las corridas. Sobre el
    cronograma versionado hoy son cero, y por eso esta línea sólo aparece el día que dejen de serlo.
    """
    if cronograma.sin_fecha or cronograma.sin_monto:
        logger.warning(
            "cronograma_incompleto",
            sin_fecha=len(cronograma.sin_fecha),
            sin_monto=len(cronograma.sin_monto),
            muestra=cronograma.sin_monto[:5],
        )
