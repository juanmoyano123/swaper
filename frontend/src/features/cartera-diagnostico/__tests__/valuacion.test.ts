/**
 * `valuarCartera` en aislamiento — F-030. Sin red, sin universo real: fixtures a mano para cubrir
 * las cuatro reglas de exclusión en orden y los edge cases del plan.
 */

import { describe, expect, it } from 'vitest'

import type { PosicionResuelta } from '@/features/cartera-resolucion/lib/schema'
import type { Especie } from '@/lib/cartera/esquemaEspecie'

import { valuarCartera } from '../lib/valuacion'

function posicion(overrides: Partial<PosicionResuelta> = {}): PosicionResuelta {
  return {
    id: 'id-1',
    fila: 1,
    ticker_declarado: 'AL30D',
    nominal: 1000,
    monto: null,
    resuelta: true,
    ticker: 'AL30D',
    emision: 'AL30',
    sufijo_liquidacion: 'D',
    moneda_cotizacion: 'USD',
    plazo_liquidacion: '2',
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    dato_sano: true,
    motivo: null,
    motivo_descripcion: null,
    ...overrides,
  }
}

function especie(overrides: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30D',
    emision: 'AL30',
    sufijo_liquidacion: 'D',
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.12,
    duracion: 3.5,
    vencimiento: '2030-07-09',
    periodicidad: 'semestral',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 70,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: 1,
    sector: 'Soberano',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    ...overrides,
  }
}

describe('una posición que se puede valuar entera', () => {
  it('calcula invertido con la fórmula precio cada 100 de nominal', () => {
    const universo = new Map([['AL30D', especie({ precio: 70 })]])
    const { valuadas, excluidas } = valuarCartera([posicion({ nominal: 1000 })], universo, null)

    expect(excluidas).toHaveLength(0)
    expect(valuadas).toHaveLength(1)
    // nominal 1000 * precio 70 / 100 = 700
    expect(valuadas[0].invertido).toBeCloseTo(700, 6)
  })

  it('en dólares, invertidoUsd es igual a invertido', () => {
    const universo = new Map([['AL30D', especie({ precio: 100, moneda_cotizacion: 'USD' })]])
    const { valuadas } = valuarCartera([posicion({ nominal: 1000 })], universo, null)

    expect(valuadas[0].invertido).toBeCloseTo(1000, 6)
    expect(valuadas[0].invertidoUsd).toBeCloseTo(1000, 6)
  })

  it('con una sola posición, pesoReal es 100', () => {
    const universo = new Map([['AL30D', especie({ precio: 100 })]])
    const { valuadas } = valuarCartera([posicion({ nominal: 1000 })], universo, null)

    expect(valuadas[0].pesoReal).toBeCloseTo(100, 6)
    expect(valuadas[0].peso).toBe(valuadas[0].pesoReal)
  })

  it('pesoReal se reparte proporcional a invertidoUsd entre varias posiciones', () => {
    const universo = new Map([
      ['AL30D', especie({ ticker: 'AL30D', precio: 100 })],
      ['GD30D', especie({ ticker: 'GD30D', precio: 300 })],
    ])
    const { valuadas } = valuarCartera(
      [
        posicion({ id: 'a', ticker: 'AL30D', ticker_declarado: 'AL30D', nominal: 1000 }),
        posicion({ id: 'b', ticker: 'GD30D', ticker_declarado: 'GD30D', nominal: 1000 }),
      ],
      universo,
      null,
    )

    // invertido: 1000 y 3000 → pesos 25% y 75%
    const porTicker = new Map(valuadas.map((v) => [v.ticker, v]))
    expect(porTicker.get('AL30D')!.pesoReal).toBeCloseTo(25, 6)
    expect(porTicker.get('GD30D')!.pesoReal).toBeCloseTo(75, 6)
  })
})

describe('conversión ARS → USD', () => {
  it('divide por el tipo de cambio, no multiplica — TC 1050 de ejemplo', () => {
    // 1500 nominal * precio 700 / 100 = 10.500 ARS invertido; / TC 1050 = 10 USD.
    const universo = new Map([['TX26', especie({ ticker: 'TX26', precio: 700, moneda_cotizacion: 'ARS' })]])
    const { valuadas } = valuarCartera(
      [posicion({ ticker: 'TX26', ticker_declarado: 'TX26', nominal: 1500 })],
      universo,
      1050,
    )

    expect(valuadas[0].invertido).toBeCloseTo(10_500, 6)
    expect(valuadas[0].invertidoUsd).toBeCloseTo(10, 6)
  })

  it('normaliza moneda_cotizacion a minúscula antes de comparar', () => {
    const universo = new Map([['TX26', especie({ ticker: 'TX26', precio: 100, moneda_cotizacion: 'ARS' })]])
    const { valuadas, excluidas } = valuarCartera(
      [posicion({ ticker: 'TX26', ticker_declarado: 'TX26', nominal: 100 })],
      universo,
      1050,
    )
    expect(excluidas).toHaveLength(0)
    expect(valuadas).toHaveLength(1)
  })
})

// --- Las cuatro reglas de exclusión, en orden -----------------------------------------------------

describe('regla 1 — no resuelta', () => {
  it('excluye una posición no resuelta por F-029, sin exigir nada más', () => {
    const universo = new Map<string, Especie>()
    const { valuadas, excluidas } = valuarCartera(
      [posicion({ resuelta: false, ticker: null, monto: 5000, nominal: null })],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(0)
    expect(excluidas).toEqual([{ id: 'id-1', motivo: 'no_resuelta', montoDeclarado: 5000 }])
  })
})

describe('regla 2 — sin nominal', () => {
  it('una posición resuelta con sólo monto (sin nominal) se excluye sin convertir el monto', () => {
    const universo = new Map([['AL30D', especie()]])
    const { valuadas, excluidas } = valuarCartera(
      [posicion({ nominal: null, monto: 12_345 })],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(0)
    expect(excluidas).toEqual([{ id: 'id-1', motivo: 'sin_nominal', montoDeclarado: 12_345 }])
  })
})

describe('regla 3 — sin precio', () => {
  it('excluye cuando la especie no tiene precio', () => {
    const universo = new Map([['AL30D', especie({ precio: null })]])
    const { valuadas, excluidas } = valuarCartera([posicion({ nominal: 1000 })], universo, null)
    expect(valuadas).toHaveLength(0)
    expect(excluidas[0].motivo).toBe('sin_precio')
  })

  it('excluye como sin_precio cuando el ticker resuelto no está en el universo cargado', () => {
    const universo = new Map<string, Especie>()
    const { valuadas, excluidas } = valuarCartera([posicion({ nominal: 1000 })], universo, null)
    expect(valuadas).toHaveLength(0)
    expect(excluidas[0].motivo).toBe('sin_precio')
  })
})

describe('regla 4 — sin tipo de cambio', () => {
  it('una posición en pesos sin TC implícito se excluye y se declara', () => {
    const universo = new Map([['TX26', especie({ ticker: 'TX26', precio: 100, moneda_cotizacion: 'ARS' })]])
    const { valuadas, excluidas } = valuarCartera(
      [posicion({ ticker: 'TX26', ticker_declarado: 'TX26', nominal: 100, monto: null })],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(0)
    expect(excluidas[0].motivo).toBe('sin_tipo_de_cambio')
  })
})

// --- Edge cases del plan ---------------------------------------------------------------------------

describe('edge cases', () => {
  it('ninguna posición valuable: todas excluidas, cartera vacía y declarada', () => {
    const universo = new Map<string, Especie>()
    const { valuadas, excluidas, totalInvertidoUsd } = valuarCartera(
      [posicion({ resuelta: false, ticker: null })],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(0)
    expect(excluidas).toHaveLength(1)
    expect(totalInvertidoUsd).toBe(0)
  })

  it('un ticker duplicado en dos filas se valúa fila por fila, sin fusionar', () => {
    const universo = new Map([['AL30D', especie({ precio: 100 })]])
    const { valuadas } = valuarCartera(
      [
        posicion({ id: 'fila-1', fila: 1, nominal: 1000 }),
        posicion({ id: 'fila-2', fila: 2, nominal: 500 }),
      ],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(2)
    expect(valuadas.map((v) => v.invertido).sort((a, b) => a - b)).toEqual([500, 1000])
  })

  it('un resultado en cero se explica: la exclusión queda contada, no en silencio', () => {
    const universo = new Map<string, Especie>()
    const { valuadas, excluidas, totalInvertidoUsd } = valuarCartera(
      [posicion({ nominal: null, monto: 1000 }), posicion({ id: 'id-2', resuelta: false, ticker: null })],
      universo,
      null,
    )
    expect(valuadas).toHaveLength(0)
    expect(totalInvertidoUsd).toBe(0)
    expect(excluidas).toHaveLength(2)
    expect(excluidas.map((e) => e.motivo).sort()).toEqual(['no_resuelta', 'sin_nominal'])
  })
})
