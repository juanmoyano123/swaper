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

export interface CostoAcumulado {
  /** Suma en USD del costo verificable de cada pata de la cadena. `null` si ninguna pata tiene
   *  costo verificable — nunca un total parcial presentado como si fuera el total. */
  totalUsd: number | null
  rotacionesVerificables: number
  /** Pares `"A->B"` cuyo costo no entró al total: sin dato (`costo: null`), no verificable, o sin
   *  tipo de cambio para llevarlo a USD (regla 1 — el faltante se declara, no se omite en silencio). */
  sinCostoVerificable: string[]
  /** Mismo criterio que `montosAcumulados`: destino cuyo monto no se pudo llevar a la moneda de
   *  origen sin un tipo de cambio (regla 3/11). Esa pata tampoco entra al total. */
  noConvertibles: string[]
}

/**
 * El costo total de rotación acumulado, en USD, sobre la misma cadena que `montosAcumulados`.
 *
 * `costo.total_pct` (F-035) es un porcentaje del monto rotado de *esa* pata — sumar porcentajes de
 * bases distintas inventaría un número, así que cada pata se pasa a plata sobre el monto del origen
 * **vigente en ese punto de la cadena** (no el original: una rotación puede rotar lo que ya rotó
 * una anterior) y se normaliza a USD con el tipo de cambio implícito del universo (regla 3), igual
 * que `valuarCartera`. Sin ese TC, o con `costo: null` / no verificable / `total_pct: null`, la pata
 * se declara en `sinCostoVerificable` y el total cubre sólo lo que sí se pudo calcular.
 */
export function costoAcumulado(
  originales: PosicionConMonto[],
  aceptadas: Candidata[],
  monedaDe: (ticker: string) => 'usd' | 'ars' | null,
  tipoDeCambio: number | null,
): CostoAcumulado {
  let montos = originales
  let totalUsd = 0
  let rotacionesVerificables = 0
  const sinCostoVerificable: string[] = []
  const noConvertibles = new Set<string>()

  for (const candidata of aceptadas) {
    const origenTicker = candidata.origen.ticker
    const destinoTicker = candidata.destino.ticker
    const clave = `${origenTicker}->${destinoTicker}`

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
    let montoOrigenUsd: number | null = null
    if (monedaOrigen !== null && monedaOrigen === monedaDestino) {
      montoDestino = montoOrigen
      montoOrigenUsd = monedaOrigen === 'ars' ? (tipoDeCambio !== null ? montoOrigen / tipoDeCambio : null) : montoOrigen
    } else if (monedaOrigen !== null && monedaDestino !== null && tipoDeCambio !== null) {
      const montoUsd = monedaOrigen === 'ars' ? montoOrigen / tipoDeCambio : montoOrigen
      montoDestino = monedaDestino === 'ars' ? montoUsd * tipoDeCambio : montoUsd
      montoOrigenUsd = montoUsd
    }

    if (montoDestino === null) {
      noConvertibles.add(destinoTicker)
      montos = sinOrigen
      continue
    }

    const costo = candidata.costo
    if (costo !== null && costo.verificable && costo.total_pct !== null && montoOrigenUsd !== null) {
      totalUsd += montoOrigenUsd * (costo.total_pct / 100)
      rotacionesVerificables += 1
    } else {
      sinCostoVerificable.push(clave)
    }

    montos = sumarMontosPorTicker([...sinOrigen, { ticker: destinoTicker, monto: montoDestino }])
  }

  return {
    totalUsd: rotacionesVerificables > 0 ? totalUsd : null,
    rotacionesVerificables,
    sinCostoVerificable,
    noConvertibles: [...noConvertibles],
  }
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
