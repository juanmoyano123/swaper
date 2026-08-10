/**
 * La aritmética del plan de rotaciones acumulado — F-036.
 *
 * El principio del store (`features/optimizador/store/planRotacionStore.tsx`) es que el estado
 * guarda **decisiones**, nunca carteras derivadas: `aceptadas` es la pila de `Candidata` en el
 * orden en que el asesor las aceptó, y todo lo demás —la cartera resultante, los montos, qué
 * rotaciones no hay que volver a proponer— se recalcula acá, puro y sin red, a partir de esa pila.
 * Así "deshacer" es sacar el último elemento y todo vuelve exacto, sin un snapshot que pueda
 * desincronizarse del árbol de decisiones.
 */

import type { PosicionConPeso } from '../cartera/riesgo'

import { carteraSimuladaDeCandidata, claveCandidata } from './ejes'
import type { Candidata } from './esquemaRotaciones'

/** Una posición con su monto en la moneda de cotización de la especie — la forma que pide
 *  `POST /calendario/cartera` (`useCalendarioCartera.ts`), no la que usan concentración/riesgo. */
export interface PosicionConMonto {
  ticker: string
  monto: number
}

/** La cartera resultante de aplicar, en orden, cada rotación aceptada sobre las posiciones
 *  originales. Cada paso es una rotación total de la posición (`carteraSimuladaDeCandidata`). */
export function posicionesAcumuladas(
  originales: PosicionConPeso[],
  aceptadas: Candidata[],
): PosicionConPeso[] {
  return aceptadas.reduce(carteraSimuladaDeCandidata, originales)
}

function sumarMontosPorTicker(posiciones: PosicionConMonto[]): PosicionConMonto[] {
  const montos = new Map<string, number>()
  const orden: string[] = []
  for (const p of posiciones) {
    if (!montos.has(p.ticker)) orden.push(p.ticker)
    montos.set(p.ticker, (montos.get(p.ticker) ?? 0) + p.monto)
  }
  return orden.map((ticker) => ({ ticker, monto: montos.get(ticker)! }))
}

/**
 * La misma cadena de rotaciones que `posicionesAcumuladas`, pero en plata: el monto del origen pasa
 * al destino (venta y recompra a mercado — aritmética, no inferencia; regla 1). El costo F-035 no
 * se descuenta acá: viaja aparte en cada fila (`NotaCosto`), nunca se resta en silencio del monto.
 *
 * Si origen y destino cotizan en la misma moneda, el monto pasa sin tocar. Si cotizan en monedas
 * distintas, se normaliza con el tipo de cambio implícito del universo (regla 3 — misma fórmula que
 * `valuarCartera`: a USD y de USD a la moneda destino). Sin ese TC, o con una moneda de cotización
 * que no es `usd` ni `ars` (por ejemplo `EXT`, regla 11), el ticker destino no se puede convertir:
 * se declara en `noConvertibles` en vez de inventarse un monto.
 */
export function montosAcumulados(
  originales: PosicionConMonto[],
  aceptadas: Candidata[],
  monedaDe: (ticker: string) => 'usd' | 'ars' | null,
  tipoDeCambio: number | null,
): { montos: PosicionConMonto[]; noConvertibles: string[] } {
  let montos = originales
  const noConvertibles = new Set<string>()

  for (const candidata of aceptadas) {
    const origenTicker = candidata.origen.ticker
    const destinoTicker = candidata.destino.ticker

    const montoOrigen = montos
      .filter((p) => p.ticker === origenTicker)
      .reduce((acumulado, p) => acumulado + p.monto, 0)
    const sinOrigen = montos.filter((p) => p.ticker !== origenTicker)

    if (montoOrigen === 0) {
      montos = sinOrigen
      continue
    }

    const monedaOrigen = monedaDe(origenTicker)
    const monedaDestino = monedaDe(destinoTicker)

    let montoDestino: number | null = null
    if (monedaOrigen !== null && monedaOrigen === monedaDestino) {
      montoDestino = montoOrigen
    } else if (monedaOrigen !== null && monedaDestino !== null && tipoDeCambio !== null) {
      const montoUsd = monedaOrigen === 'ars' ? montoOrigen / tipoDeCambio : montoOrigen
      montoDestino = monedaDestino === 'ars' ? montoUsd * tipoDeCambio : montoUsd
    }

    if (montoDestino === null) {
      noConvertibles.add(destinoTicker)
      montos = sinOrigen
      continue
    }

    montos = sumarMontosPorTicker([...sinOrigen, { ticker: destinoTicker, monto: montoDestino }])
  }

  return { montos, noConvertibles: [...noConvertibles] }
}

/** `"B->A"` por cada `"A->B"` aceptada: es la rotación que deshace la aceptada, y proponerla de
 *  nuevo sería un "deshacer" disfrazado de mejora — se filtra en los hooks de F-033/F-034. */
export function clavesInversas(aceptadas: Candidata[]): Set<string> {
  return new Set(aceptadas.map((c) => `${c.destino.ticker}->${c.origen.ticker}`))
}

/** Parte las candidatas del motor entre las que siguen vigentes y las que ya se decidieron en esta
 *  sesión (descartadas o inversas de una aceptada) — GWT-4 de F-036. */
export function separarYaDecididas(
  candidatas: Candidata[],
  excluir: ReadonlySet<string>,
): { vigentes: Candidata[]; excluidas: number } {
  const vigentes = candidatas.filter((c) => !excluir.has(claveCandidata(c)))
  return { vigentes, excluidas: candidatas.length - vigentes.length }
}
