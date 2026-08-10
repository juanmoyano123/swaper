/**
 * GWT-1 de F-036: "declara qué mes del calendario se llena y qué mes se vacía si se acepta". El
 * mismo núcleo sirve para GWT-2 de F-037 (`diffCalendarioCarteras`): "los meses que pasaron de
 * cero a cubierto y los que pasaron de cubierto a cero están marcados" al comparar la cartera
 * original contra la propuesta completa.
 *
 * Compara dos calendarios (los dos vienen de `POST /calendario/cartera?detalle=true`,
 * `esquemaCalendarioUniverso`), mes a mes y **moneda por moneda por separado** — la renta viene
 * abierta por moneda de cobro con ceros explícitos (`grilla.py`), y sumar entre monedas para
 * decidir qué mes "se llena" mezclaría magnitudes que la regla 3 del proyecto prohíbe comparar. Un
 * mes puede llenarse en USD y vaciarse en ARS a la vez: las dos cosas se declaran, nunca se
 * compensan.
 *
 * El criterio es la **renta**, no la amortización — es el mismo criterio de "mes descubierto" que
 * ya usa F-015 (`meses_sin_renta`). Un cambio de monto que no cruza cero se cuenta, no se detalla.
 *
 * Regla 1: si alguna de las dos puntas no llegó a tener cronograma calculable (alertas
 * `posicion_sin_calendario` / `posicion_fuera_del_universo`), el efecto se declara **no
 * calculable**, con el ticker y el motivo nombrados — nunca se muestra un diff con una punta
 * silenciosamente ausente.
 */

import type { AlertaCalendario, CalendarioUniverso } from '../cartera/esquemaCalendario'

import type { Candidata } from './esquemaRotaciones'

export interface EfectoMes {
  etiqueta: string
  nombre: string
  moneda: string
}

export interface EfectoCalendario {
  calculable: boolean
  /** Nombra el ticker y la causa cuando `calculable` es `false`. */
  motivoNoCalculable: string | null
  seLlenan: EfectoMes[]
  seVacian: EfectoMes[]
  /** Meses cuya renta cambió en alguna moneda sin cruzar cero de ningún lado. */
  mesesQueCambian: number
}

/** Exportada para `useEfectoCalendario`: el caso de moneda no convertible (`montosAcumulados`) es
 *  otro motivo de no-calculable, no un cuarto estado que la UI tenga que distinguir. */
export function efectoNoCalculable(motivo: string): EfectoCalendario {
  return { calculable: false, motivoNoCalculable: motivo, seLlenan: [], seVacian: [], mesesQueCambian: 0 }
}

/** Tickers nombrados por `posicion_sin_calendario` (`detalle.motivos`, un objeto ticker→motivo) o
 *  `posicion_fuera_del_universo` (`detalle.tickers`) — los dos shapes reales de
 *  `backend/app/calendario/alertas.py`, no asumidos. */
function ticketsSinCalendarioCalculable(alertas: AlertaCalendario[]): Set<string> {
  const tickers = new Set<string>()
  for (const alerta of alertas) {
    if (alerta.codigo === 'posicion_sin_calendario') {
      const motivos = alerta.detalle.motivos
      if (motivos && typeof motivos === 'object') {
        for (const ticker of Object.keys(motivos as Record<string, unknown>)) tickers.add(ticker)
      }
    }
    if (alerta.codigo === 'posicion_fuera_del_universo') {
      const lista = alerta.detalle.tickers
      if (Array.isArray(lista)) {
        for (const ticker of lista) if (typeof ticker === 'string') tickers.add(ticker)
      }
    }
  }
  return tickers
}

/** El núcleo mes a mes, moneda por moneda, común a `diffCalendario` (F-036, una candidata) y
 *  `diffCalendarioCarteras` (F-037, cartera original vs propuesta) — ver el porqué del criterio en
 *  el docstring del módulo. Asume que las alertas y la ventana de doce meses ya se validaron. */
function diffMesAMes(actual: CalendarioUniverso, propuesto: CalendarioUniverso): EfectoCalendario {
  const mesesPropuesto = new Map(propuesto.meses.map((m) => [m.etiqueta, m]))
  const monedas = new Set([...actual.resumen.monedas, ...propuesto.resumen.monedas])
  const seLlenan: EfectoMes[] = []
  const seVacian: EfectoMes[] = []
  const etiquetasQueCambian = new Set<string>()

  for (const mesActual of actual.meses) {
    const mesPropuesto = mesesPropuesto.get(mesActual.etiqueta)!
    for (const moneda of monedas) {
      const valorActual = mesActual.renta?.[moneda] ?? 0
      const valorPropuesto = mesPropuesto.renta?.[moneda] ?? 0
      if (valorActual === 0 && valorPropuesto > 0) {
        seLlenan.push({ etiqueta: mesActual.etiqueta, nombre: mesActual.nombre, moneda })
      } else if (valorActual > 0 && valorPropuesto === 0) {
        seVacian.push({ etiqueta: mesActual.etiqueta, nombre: mesActual.nombre, moneda })
      } else if (valorActual !== valorPropuesto) {
        etiquetasQueCambian.add(mesActual.etiqueta)
      }
    }
  }

  return {
    calculable: true,
    motivoNoCalculable: null,
    seLlenan,
    seVacian,
    mesesQueCambian: etiquetasQueCambian.size,
  }
}

/** Regla 1 común a los dos diffs: sin montos, o con ventanas de doce meses que no coinciden entre
 *  las dos carteras, el efecto no es calculable — nunca se compara una cordillera de doce meses
 *  contra otra de una ventana distinta. */
function diffCalculable(actual: CalendarioUniverso, propuesto: CalendarioUniverso): string | null {
  if (!actual.resumen.con_montos || !propuesto.resumen.con_montos) {
    return 'El calendario no trae montos: no se puede calcular el efecto.'
  }
  const mesesPropuesto = new Map(propuesto.meses.map((m) => [m.etiqueta, m]))
  if (actual.meses.length !== propuesto.meses.length || actual.meses.some((m) => !mesesPropuesto.has(m.etiqueta))) {
    return 'Las ventanas de doce meses no coinciden entre el calendario actual y el propuesto.'
  }
  return null
}

export function diffCalendario(
  actual: CalendarioUniverso,
  simulado: CalendarioUniverso,
  candidata: Candidata,
): EfectoCalendario {
  const sinCalendarioSimulado = ticketsSinCalendarioCalculable(simulado.alertas)
  if (sinCalendarioSimulado.has(candidata.destino.ticker)) {
    return efectoNoCalculable(
      `El efecto sobre el calendario no se puede afirmar: ${candidata.destino.ticker} no tiene ` +
        'cronograma calculable hoy.',
    )
  }

  const sinCalendarioActual = ticketsSinCalendarioCalculable(actual.alertas)
  if (sinCalendarioActual.has(candidata.origen.ticker)) {
    return efectoNoCalculable(
      `El efecto sobre el calendario no se puede afirmar: ${candidata.origen.ticker} no tiene ` +
        'cronograma calculable hoy en la cartera actual.',
    )
  }

  const motivo = diffCalculable(actual, simulado)
  if (motivo !== null) return efectoNoCalculable(motivo)

  return diffMesAMes(actual, simulado)
}

/**
 * GWT-1/2 de F-037: el mismo diff que `diffCalendario`, pero entre la cartera original y la
 * propuesta completa (todas las rotaciones aceptadas), no entre una cartera y la simulación de una
 * sola candidata.
 *
 * `tickersQueCambian` son los tickers cuyo monto difiere entre las dos carteras (típicamente los
 * orígenes y destinos de las rotaciones aceptadas) — sólo esos tickers, si les falta cronograma
 * calculable en cualquiera de las dos puntas, tumban el diff a no calculable. Un ticker sin
 * cronograma que está igual en las dos carteras ya lo declara la alerta visible de cada calendario
 * por separado; no es un problema de la comparación (regla 1: no se declara dos veces el mismo
 * faltante con causas distintas).
 */
export function diffCalendarioCarteras(
  actual: CalendarioUniverso,
  propuesto: CalendarioUniverso,
  tickersQueCambian: string[],
): EfectoCalendario {
  const sinCalendarioPropuesto = ticketsSinCalendarioCalculable(propuesto.alertas)
  const sinCalendarioActual = ticketsSinCalendarioCalculable(actual.alertas)

  for (const ticker of tickersQueCambian) {
    if (sinCalendarioPropuesto.has(ticker)) {
      return efectoNoCalculable(
        `El efecto sobre el calendario no se puede afirmar: ${ticker} no tiene cronograma ` +
          'calculable hoy en la cartera propuesta.',
      )
    }
    if (sinCalendarioActual.has(ticker)) {
      return efectoNoCalculable(
        `El efecto sobre el calendario no se puede afirmar: ${ticker} no tiene cronograma ` +
          'calculable hoy en la cartera original.',
      )
    }
  }

  const motivo = diffCalculable(actual, propuesto)
  if (motivo !== null) return efectoNoCalculable(motivo)

  return diffMesAMes(actual, propuesto)
}
