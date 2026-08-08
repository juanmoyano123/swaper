/**
 * `resolverRentaVariable`, aislado: sin red, sin store, sin React — mismo patrón que
 * `resolver.test.ts`. La vuelta completa por la pantalla vive en `BloqueRentaVariable.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import {
  resolverRentaVariable,
  subtotalRentaVariableUsd,
  type EntradaRentaVariable,
} from '../lib/resolverRentaVariable'

function entrada(extra: Partial<EntradaRentaVariable> = {}): EntradaRentaVariable {
  return {
    ticker: 'GGAL',
    peso: 10,
    precio: 30,
    monedaCotizacion: 'USD',
    ...extra,
  }
}

describe('peso → cantidad, siempre por unidad entera', () => {
  it('redondea siempre hacia abajo, nunca hacia arriba', () => {
    // objetivo = 1000 * 10 / 100 = 100 USD; a 30 la unidad, 100/30 = 3,33 → floor 3, nunca 4.
    const [resuelta] = resolverRentaVariable([entrada()], 1000, null)

    expect(resuelta.cantidad).toBe(3)
    expect(resuelta.invertido).toBeCloseTo(90, 6) // 3 * 30
    expect(resuelta.invertidoUsd).toBeCloseTo(90, 6)
  })

  it('no compra ninguna unidad si el objetivo no alcanza para una sola', () => {
    const [resuelta] = resolverRentaVariable([entrada({ peso: 1, precio: 500 })], 1000, null)

    expect(resuelta.cantidad).toBe(0)
    expect(resuelta.invertido).toBe(0)
  })
})

describe('especie en ARS', () => {
  it('sin tipo de cambio, no inventa uno externo: declara la posición sin resolver', () => {
    const [resuelta] = resolverRentaVariable([entrada({ monedaCotizacion: 'ARS' })], 1000, null)

    expect(resuelta.cantidad).toBeNull()
    expect(resuelta.invertido).toBeNull()
    expect(resuelta.invertidoUsd).toBeNull()
    expect(resuelta.pesoReal).toBeNull()
  })

  it('con tipo de cambio disponible, resuelve en la moneda de cotización y normaliza a USD', () => {
    const [resuelta] = resolverRentaVariable(
      [entrada({ monedaCotizacion: 'ARS', precio: 3000, peso: 50 })],
      1000,
      1500,
    )

    // objetivoUsd = 500; objetivo en ARS = 500 * 1500 = 750.000; cantidad = floor(750.000/3000) = 250.
    expect(resuelta.cantidad).toBe(250)
    expect(resuelta.invertido).toBeCloseTo(750_000, 6) // en ARS, la moneda de cotización
    expect(resuelta.invertidoUsd).toBeCloseTo(500, 6) // normalizado de nuevo a USD
  })
})

describe('moneda EXT o sin declarar', () => {
  it('EXT no se interpreta (regla 11): la posición queda sin resolver', () => {
    const [resuelta] = resolverRentaVariable([entrada({ monedaCotizacion: 'EXT' })], 1000, null)

    expect(resuelta.cantidad).toBeNull()
    expect(resuelta.invertido).toBeNull()
    expect(resuelta.invertidoUsd).toBeNull()
  })

  it('sin moneda declarada, tampoco', () => {
    const [resuelta] = resolverRentaVariable([entrada({ monedaCotizacion: null })], 1000, null)

    expect(resuelta.cantidad).toBeNull()
  })
})

describe('sin precio publicado', () => {
  it('la posición queda sin resolver', () => {
    const [resuelta] = resolverRentaVariable([entrada({ precio: null })], 1000, null)

    expect(resuelta.cantidad).toBeNull()
    expect(resuelta.invertido).toBeNull()
  })
})

describe('montoTotal en 0', () => {
  it('no hay objetivo que repartir: todo sale null', () => {
    const resueltas = resolverRentaVariable([entrada(), entrada({ ticker: 'YPFD' })], 0, null)

    for (const r of resueltas) {
      expect(r.cantidad).toBeNull()
      expect(r.invertido).toBeNull()
      expect(r.invertidoUsd).toBeNull()
      expect(r.pesoReal).toBeNull()
    }
  })
})

describe('peso real dentro del bloque, no de la cartera entera', () => {
  it('se calcula sobre la Σ invertidoUsd de las posiciones de renta variable, sin mirar el resto de la cartera', () => {
    const resueltas = resolverRentaVariable(
      [
        entrada({ ticker: 'GGAL', peso: 20, precio: 30 }), // objetivo 200 USD -> cantidad 6 -> 180
        entrada({ ticker: 'YPFD', peso: 10, precio: 20 }), // objetivo 100 USD -> cantidad 5 -> 100
      ],
      1000,
      null,
    )

    const ggal = resueltas.find((r) => r.ticker === 'GGAL')!
    const ypfd = resueltas.find((r) => r.ticker === 'YPFD')!

    // Σ invertidoUsd = 280: 180/280*100 y 100/280*100 — no 18% y 10% (que sería sobre el total pedido).
    expect(ggal.pesoReal).toBeCloseTo((180 / 280) * 100, 6)
    expect(ypfd.pesoReal).toBeCloseTo((100 / 280) * 100, 6)
  })

  it('una posición sin resolver no entra al denominador de las demás', () => {
    const resueltas = resolverRentaVariable(
      [
        entrada({ ticker: 'GGAL', peso: 50, precio: 30 }), // objetivo 500 -> cantidad 16 -> 480
        entrada({ ticker: 'SIN-DATO', peso: 20, precio: null }),
      ],
      1000,
      null,
    )

    const ggal = resueltas.find((r) => r.ticker === 'GGAL')!
    expect(ggal.pesoReal).toBeCloseTo(100, 6)
  })
})

describe('subtotalRentaVariableUsd', () => {
  it('suma sólo lo resuelto; null si ninguna posición se resolvió (no 0)', () => {
    const sinNinguna = resolverRentaVariable([entrada({ precio: null })], 1000, null)
    expect(subtotalRentaVariableUsd(sinNinguna)).toBeNull()

    const conDos = resolverRentaVariable(
      [entrada({ ticker: 'GGAL', peso: 20, precio: 30 }), entrada({ ticker: 'YPFD', peso: 10, precio: 20 })],
      1000,
      null,
    )
    expect(subtotalRentaVariableUsd(conDos)).toBeCloseTo(280, 6) // 180 + 100
  })
})
