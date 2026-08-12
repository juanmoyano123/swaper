import { describe, expect, it } from 'vitest'

import type { ResueltaGuardada, SnapshotArmador, SnapshotCargada } from '../lib/esquemaSnapshot'
import {
  comparablesDesdeSnapshotArmador,
  comparablesDesdeSnapshotCargada,
  comparablesDesdeValuacionHoy,
  compararValuaciones,
  revaluarResueltasHoy,
  type PosicionComparable,
} from '../lib/revaluacion'

function comparable(overrides: Partial<PosicionComparable> = {}): PosicionComparable {
  return { ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, motivo: null, ...overrides }
}

describe('compararValuaciones', () => {
  it('misma moneda en las dos puntas: delta directo', () => {
    const resultado = compararValuaciones([comparable({ invertido: 700, invertidoUsd: 700 })], [comparable({ invertido: 750, invertidoUsd: 750 })])
    expect(resultado.posiciones[0].delta).toBe(50)
    expect(resultado.posiciones[0].motivo).toBeNull()
    expect(resultado.deltaTotalUsd).toBe(50)
  })

  it('ARS con TC distinto en cada punta: el delta es en ARS, el total en USD ya viene convertido', () => {
    const congelada = comparable({ ticker: 'TX26', moneda: 'ars', invertido: 100_000, invertidoUsd: 95.2 })
    const hoy = comparable({ ticker: 'TX26', moneda: 'ars', invertido: 105_000, invertidoUsd: 91.3 })
    const resultado = compararValuaciones([congelada], [hoy])
    expect(resultado.posiciones[0].delta).toBe(5000)
    expect(resultado.totalUsdGuardado).toBeCloseTo(95.2)
    expect(resultado.totalUsdHoy).toBeCloseTo(91.3)
  })

  it('moneda distinta entre las dos puntas: sin delta, motivo declarado', () => {
    const resultado = compararValuaciones(
      [comparable({ moneda: 'usd' })],
      [comparable({ moneda: 'ars', invertido: 700_000, invertidoUsd: 666 })],
    )
    expect(resultado.posiciones[0].delta).toBeNull()
    expect(resultado.posiciones[0].motivo).toBe('moneda_distinta')
  })

  it('sin_precio_hoy: la posición existía al guardar y hoy no se pudo valuar', () => {
    const resultado = compararValuaciones(
      [comparable()],
      [comparable({ invertido: null, invertidoUsd: null, moneda: null, motivo: 'sin_precio_hoy' })],
    )
    expect(resultado.posiciones[0].delta).toBeNull()
    expect(resultado.posiciones[0].motivo).toBe('sin_precio_hoy')
    expect(resultado.excluidosDelTotal).toContainEqual({ ticker: 'AL30D', motivo: 'sin_precio_hoy' })
  })

  it('sin_valuar_al_guardar: la posición no se pudo valuar al momento de guardar', () => {
    const resultado = compararValuaciones(
      [comparable({ invertido: null, invertidoUsd: null, moneda: null, motivo: 'no_resuelta' })],
      [comparable()],
    )
    expect(resultado.posiciones[0].motivo).toBe('no_resuelta')
    expect(resultado.excluidosDelTotal).toContainEqual({ ticker: 'AL30D', motivo: 'no_resuelta' })
  })

  it('el total es parcial cuando falta alguna pata: se suma sólo lo verificable en cada punta', () => {
    const resultado = compararValuaciones(
      [comparable({ ticker: 'A', invertidoUsd: 100 }), comparable({ ticker: 'B', invertido: null, invertidoUsd: null, moneda: null, motivo: 'sin_precio' })],
      [comparable({ ticker: 'A', invertidoUsd: 110 }), comparable({ ticker: 'B', invertido: null, invertidoUsd: null, moneda: null, motivo: 'sin_precio_hoy' })],
    )
    expect(resultado.totalUsdGuardado).toBe(100)
    expect(resultado.totalUsdHoy).toBe(110)
    expect(resultado.excluidosDelTotal).toHaveLength(2)
  })
})

describe('comparablesDesdeSnapshotCargada', () => {
  const snapshot: SnapshotCargada = {
    version: 1,
    origen: 'cargada',
    tipoDeCambio: 1050,
    perfil: 'moderado',
    posiciones: [
      { id: 'p1', fila: 1, tickerDeclarado: 'AL30D', nominal: 1000, monto: null, valida: true, motivo: null },
      { id: 'p2', fila: 2, tickerDeclarado: 'XYZ', nominal: 500, monto: null, valida: true, motivo: null },
    ],
    valuadas: [{ ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, pesoReal: 100 }],
    excluidas: [{ id: 'p2', motivo: 'no_resuelta', montoDeclarado: null }],
    totalInvertidoUsd: 700,
    plan: { aceptadas: [], descartadas: [] },
  }

  it('usa el ticker declarado (no inventado) para las excluidas sin ticker resuelto', () => {
    const comparables = comparablesDesdeSnapshotCargada(snapshot)
    const excluida = comparables.find((c) => c.motivo === 'no_resuelta')
    expect(excluida?.ticker).toBe('XYZ')
  })
})

describe('comparablesDesdeValuacionHoy', () => {
  it('deriva la moneda del universo de hoy, no del snapshot', () => {
    const comparables = comparablesDesdeValuacionHoy(
      [{ id: 'p1', tickerDeclarado: 'AL30D' }],
      { valuadas: [{ ticker: 'AL30D', invertido: 750, invertidoUsd: 750 }], excluidas: [] },
      new Map([['AL30D', { moneda_cotizacion: 'USD' }]]),
    )
    expect(comparables[0]).toEqual({ ticker: 'AL30D', moneda: 'usd', invertido: 750, invertidoUsd: 750, motivo: null })
  })
})

describe('comparablesDesdeSnapshotArmador', () => {
  it('una resuelta sin invertidoUsd se declara sin_valuar_al_guardar', () => {
    const snapshot: SnapshotArmador = {
      version: 1,
      origen: 'armador',
      tipoDeCambio: null,
      montoTotalUsd: 10_000,
      posiciones: [{ ticker: 'FCI-X', peso: 10, clase: 'fci' }],
      resueltas: [
        { ticker: 'FCI-X', clase: 'fci', peso: 10, moneda: null, precio: null, vn: null, cantidad: null, invertido: null, invertidoUsd: null },
      ],
      totalInvertidoUsd: 0,
    }
    const comparables = comparablesDesdeSnapshotArmador(snapshot)
    expect(comparables[0].motivo).toBe('sin_valuar_al_guardar')
  })
})

describe('revaluarResueltasHoy', () => {
  function resuelta(overrides: Partial<ResueltaGuardada> = {}): ResueltaGuardada {
    return {
      ticker: 'AL30D',
      clase: 'renta_fija',
      peso: 60,
      moneda: 'usd',
      precio: 70,
      vn: 10_000,
      cantidad: null,
      invertido: 7000,
      invertidoUsd: 7000,
      ...overrides,
    }
  }

  it('renta fija: vn · precio / 100, misma fórmula que resolver.ts', () => {
    const [resultado] = revaluarResueltasHoy([resuelta({ vn: 10_000 })], new Map([['AL30D', { precio: 75, moneda_cotizacion: 'USD' }]]), null)
    expect(resultado.invertido).toBe(7500)
    expect(resultado.invertidoUsd).toBe(7500)
  })

  it('renta variable: cantidad · precio, unidades enteras', () => {
    const rv = resuelta({ ticker: 'GGAL', clase: 'renta_variable', vn: null, cantidad: 100 })
    const [resultado] = revaluarResueltasHoy([rv], new Map([['GGAL', { precio: 32, moneda_cotizacion: 'USD' }]]), null)
    expect(resultado.invertido).toBe(3200)
  })

  it('ARS convertido con el TC de hoy, no con el del snapshot', () => {
    const [resultado] = revaluarResueltasHoy([resuelta({ vn: 10_000 })], new Map([['AL30D', { precio: 75_000, moneda_cotizacion: 'ARS' }]]), 1100)
    expect(resultado.invertido).toBe(7_500_000)
    expect(resultado.invertidoUsd).toBeCloseTo(7_500_000 / 1100)
  })

  it('un FCI nunca tiene precio hoy, por construcción', () => {
    const [resultado] = revaluarResueltasHoy([resuelta({ ticker: 'FCI-X', clase: 'fci', vn: null })], new Map(), null)
    expect(resultado.motivo).toBe('sin_precio_hoy')
  })

  it('ARS sin TC de hoy: sin_tipo_de_cambio, no se inventa una conversión', () => {
    const [resultado] = revaluarResueltasHoy([resuelta()], new Map([['AL30D', { precio: 75_000, moneda_cotizacion: 'ARS' }]]), null)
    expect(resultado.motivo).toBe('sin_tipo_de_cambio')
    expect(resultado.invertidoUsd).toBeNull()
  })

  it('ticker que salió del universo hoy: sin_precio_hoy', () => {
    const [resultado] = revaluarResueltasHoy([resuelta()], new Map(), null)
    expect(resultado.motivo).toBe('sin_precio_hoy')
  })
})
