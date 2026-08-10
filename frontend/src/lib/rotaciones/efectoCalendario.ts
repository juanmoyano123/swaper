/**
 * GWT-1 de F-036: "declara qué mes del calendario se llena y qué mes se vacía si se acepta".
 *
 * Compara el calendario de la cartera actual contra el de la cartera simulada de una candidata
 * (los dos vienen de `POST /calendario/cartera?detalle=true`, `esquemaCalendarioUniverso`), mes a
 * mes y **moneda por moneda por separado** — la renta viene abierta por moneda de cobro con ceros
 * explícitos (`grilla.py`), y sumar entre monedas para decidir qué mes "se llena" mezclaría
 * magnitudes que la regla 3 del proyecto prohíbe comparar. Un mes puede llenarse en USD y vaciarse
 * en ARS a la vez: las dos cosas se declaran, nunca se compensan.
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

function noCalculable(motivo: string): EfectoCalendario {
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

export function diffCalendario(
  actual: CalendarioUniverso,
  simulado: CalendarioUniverso,
  candidata: Candidata,
): EfectoCalendario {
  const sinCalendarioSimulado = ticketsSinCalendarioCalculable(simulado.alertas)
  if (sinCalendarioSimulado.has(candidata.destino.ticker)) {
    return noCalculable(
      `El efecto sobre el calendario no se puede afirmar: ${candidata.destino.ticker} no tiene ` +
        'cronograma calculable hoy.',
    )
  }

  const sinCalendarioActual = ticketsSinCalendarioCalculable(actual.alertas)
  if (sinCalendarioActual.has(candidata.origen.ticker)) {
    return noCalculable(
      `El efecto sobre el calendario no se puede afirmar: ${candidata.origen.ticker} no tiene ` +
        'cronograma calculable hoy en la cartera actual.',
    )
  }

  if (!actual.resumen.con_montos || !simulado.resumen.con_montos) {
    return noCalculable('El calendario no trae montos: no se puede calcular el efecto.')
  }

  const mesesSimulado = new Map(simulado.meses.map((m) => [m.etiqueta, m]))
  if (actual.meses.length !== simulado.meses.length || actual.meses.some((m) => !mesesSimulado.has(m.etiqueta))) {
    return noCalculable('Las ventanas de doce meses no coinciden entre el calendario actual y el propuesto.')
  }

  const monedas = new Set([...actual.resumen.monedas, ...simulado.resumen.monedas])
  const seLlenan: EfectoMes[] = []
  const seVacian: EfectoMes[] = []
  const etiquetasQueCambian = new Set<string>()

  for (const mesActual of actual.meses) {
    const mesSimulado = mesesSimulado.get(mesActual.etiqueta)!
    for (const moneda of monedas) {
      const valorActual = mesActual.renta?.[moneda] ?? 0
      const valorSimulado = mesSimulado.renta?.[moneda] ?? 0
      if (valorActual === 0 && valorSimulado > 0) {
        seLlenan.push({ etiqueta: mesActual.etiqueta, nombre: mesActual.nombre, moneda })
      } else if (valorActual > 0 && valorSimulado === 0) {
        seVacian.push({ etiqueta: mesActual.etiqueta, nombre: mesActual.nombre, moneda })
      } else if (valorActual !== valorSimulado) {
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
