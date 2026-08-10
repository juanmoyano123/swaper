import { describe, expect, it } from 'vitest'

import type { CarteraValuada } from '@/features/cartera-diagnostico/lib/valuacion'
import type { PosicionResuelta } from '@/features/armador/lib/resolver'
import type { PosicionRvResuelta } from '@/features/armador/lib/resolverRentaVariable'
import type { PosicionArmador } from '@/features/armador/store/carteraStore'
import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import { armarSnapshotArmador, armarSnapshotCargada, montoDeCartera, resumenDeCartera } from '../lib/armarSnapshot'
import type { SnapshotArmador, SnapshotCargada } from '../lib/esquemaSnapshot'

describe('armarSnapshotCargada', () => {
  const posiciones: PosicionCruda[] = [
    { id: 'p1', fila: 1, tickerDeclarado: 'AL30D', nominal: 1000, monto: null, valida: true, motivo: null },
    { id: 'p2', fila: 2, tickerDeclarado: 'XYZINEXISTENTE', nominal: 500, monto: null, valida: true, motivo: null },
  ]

  const valuacion: CarteraValuada = {
    valuadas: [{ ticker: 'AL30D', invertido: 700, invertidoUsd: 700, pesoReal: 100, peso: 100 }],
    excluidas: [{ id: 'p2', motivo: 'no_resuelta', montoDeclarado: null }],
    totalInvertidoUsd: 700,
  }

  const porTicker = new Map([['AL30D', { precio: 70, moneda_cotizacion: 'USD' }]])

  it('congela moneda, invertido y peso real por posición valuada', () => {
    const snapshot = armarSnapshotCargada(posiciones, valuacion, porTicker, 'moderado', { aceptadas: [], descartadas: [] }, 1050)
    expect(snapshot.valuadas).toEqual([{ ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, pesoReal: 100 }])
  })

  it('declara las excluidas sin inventar su moneda ni su monto', () => {
    const snapshot = armarSnapshotCargada(posiciones, valuacion, porTicker, 'moderado', { aceptadas: [], descartadas: [] }, 1050)
    expect(snapshot.excluidas).toEqual([{ id: 'p2', motivo: 'no_resuelta', montoDeclarado: null }])
  })

  it('conserva las posiciones crudas tal cual, inválidas incluidas', () => {
    const snapshot = armarSnapshotCargada(posiciones, valuacion, porTicker, 'moderado', { aceptadas: [], descartadas: [] }, 1050)
    expect(snapshot.posiciones).toHaveLength(2)
    expect(snapshot.posiciones[1].tickerDeclarado).toBe('XYZINEXISTENTE')
  })

  it('una moneda de cotización no reconocida se declara null, no se inventa', () => {
    const porTickerSinMoneda = new Map([['AL30D', { precio: 70, moneda_cotizacion: 'EXT' }]])
    const snapshot = armarSnapshotCargada(posiciones, valuacion, porTickerSinMoneda, 'moderado', { aceptadas: [], descartadas: [] }, 1050)
    expect(snapshot.valuadas[0].moneda).toBeNull()
  })
})

describe('armarSnapshotArmador', () => {
  const pos: PosicionArmador[] = [
    { ticker: 'AL30D', peso: 60, clase: 'renta_fija' },
    { ticker: 'GGAL', peso: 30, clase: 'renta_variable' },
    { ticker: 'FCI-RENTA', peso: 10, clase: 'fci' },
  ]

  const resueltasRentaFija: PosicionResuelta[] = [
    { ticker: 'AL30D', peso: 60, vn: 8571.4, invertido: 6000, invertidoUsd: 6000, pesoReal: 60, laminaConocida: true, esFci: false },
    { ticker: 'FCI-RENTA', peso: 10, vn: null, invertido: null, invertidoUsd: null, pesoReal: null, laminaConocida: false, esFci: true },
  ]
  const porTickerRentaFija = new Map([['AL30D', { precio: 70, moneda_cotizacion: 'USD' }]])

  const resueltasRentaVariable: PosicionRvResuelta[] = [
    { ticker: 'GGAL', peso: 30, cantidad: 100, invertido: 3000, invertidoUsd: 3000, pesoReal: 100 },
  ]
  const porTickerRentaVariable = new Map([['GGAL', { precio: 30, moneda_cotizacion: 'USD' }]])

  it('arma una resuelta por posición del mandato, clasificada correctamente', () => {
    const snapshot = armarSnapshotArmador(pos, resueltasRentaFija, porTickerRentaFija, resueltasRentaVariable, porTickerRentaVariable, 1050, 10_000)
    expect(snapshot.resueltas.map((r) => [r.ticker, r.clase])).toEqual([
      ['AL30D', 'renta_fija'],
      ['GGAL', 'renta_variable'],
      ['FCI-RENTA', 'fci'],
    ])
  })

  it('renta fija guarda vn y no cantidad; renta variable guarda cantidad y no vn', () => {
    const snapshot = armarSnapshotArmador(pos, resueltasRentaFija, porTickerRentaFija, resueltasRentaVariable, porTickerRentaVariable, 1050, 10_000)
    const [rf, rv] = snapshot.resueltas
    expect(rf.vn).toBe(8571.4)
    expect(rf.cantidad).toBeNull()
    expect(rv.cantidad).toBe(100)
    expect(rv.vn).toBeNull()
  })

  it('un FCI queda sin precio ni moneda, declarado por construcción', () => {
    const snapshot = armarSnapshotArmador(pos, resueltasRentaFija, porTickerRentaFija, resueltasRentaVariable, porTickerRentaVariable, 1050, 10_000)
    const fci = snapshot.resueltas[2]
    expect(fci.precio).toBeNull()
    expect(fci.moneda).toBeNull()
    expect(fci.invertidoUsd).toBeNull()
  })

  it('totalInvertidoUsd es la suma de lo efectivamente valuado, no el monto objetivo', () => {
    const snapshot = armarSnapshotArmador(pos, resueltasRentaFija, porTickerRentaFija, resueltasRentaVariable, porTickerRentaVariable, 1050, 10_000)
    expect(snapshot.totalInvertidoUsd).toBe(9000)
    expect(snapshot.montoTotalUsd).toBe(10_000)
  })
})

describe('resumenDeCartera', () => {
  it('origen cargada: cuenta posiciones, sin valuar y rotaciones aceptadas', () => {
    const snapshot: SnapshotCargada = {
      version: 1,
      origen: 'cargada',
      tipoDeCambio: 1050,
      perfil: 'moderado',
      posiciones: [],
      valuadas: [
        { ticker: 'A', moneda: 'usd', invertido: 1, invertidoUsd: 1, pesoReal: 50 },
        { ticker: 'B', moneda: 'usd', invertido: 1, invertidoUsd: 1, pesoReal: 50 },
      ],
      excluidas: [{ id: 'x', motivo: 'sin_precio', montoDeclarado: null }],
      totalInvertidoUsd: 2,
      plan: { aceptadas: [], descartadas: [] },
    }
    expect(resumenDeCartera(snapshot)).toBe('2 posiciones · 1 sin valuar')
  })

  it('origen cargada sin excluidas ni rotaciones: sólo el conteo de posiciones', () => {
    const snapshot: SnapshotCargada = {
      version: 1,
      origen: 'cargada',
      tipoDeCambio: 1050,
      perfil: 'moderado',
      posiciones: [],
      valuadas: [{ ticker: 'A', moneda: 'usd', invertido: 1, invertidoUsd: 1, pesoReal: 100 }],
      excluidas: [],
      totalInvertidoUsd: 1,
      plan: { aceptadas: [], descartadas: [] },
    }
    expect(resumenDeCartera(snapshot)).toBe('1 posición')
  })

  it('origen armador: mix de clases', () => {
    const snapshot: SnapshotArmador = {
      version: 1,
      origen: 'armador',
      tipoDeCambio: 1050,
      montoTotalUsd: 10_000,
      posiciones: [
        { ticker: 'AL30D', peso: 60, clase: 'renta_fija' },
        { ticker: 'GGAL', peso: 30, clase: 'renta_variable' },
        { ticker: 'FCI-RENTA', peso: 10, clase: 'fci' },
      ],
      resueltas: [],
      totalInvertidoUsd: 9000,
    }
    expect(resumenDeCartera(snapshot)).toBe('3 posiciones · 1 renta fija · 1 renta variable · 1 FCI')
  })
})

describe('montoDeCartera', () => {
  it('es el total efectivamente invertido, sea cual sea el origen', () => {
    const snapshot: SnapshotArmador = {
      version: 1,
      origen: 'armador',
      tipoDeCambio: 1050,
      montoTotalUsd: 10_000,
      posiciones: [],
      resueltas: [],
      totalInvertidoUsd: 9000,
    }
    expect(montoDeCartera(snapshot)).toBe(9000)
  })
})
