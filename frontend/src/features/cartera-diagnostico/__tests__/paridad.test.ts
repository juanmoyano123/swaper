/**
 * El criterio de aceptación central de F-030 (riesgo R12 de `plan.md:2774`): la misma tenencia
 * física, armada a mano en `/armador` o cargada y valuada en el diagnóstico, tiene que dar los
 * mismos números — porque las dos vías llaman a las mismas funciones de `@/lib/cartera/*`.
 *
 * Construye la misma cartera por las dos vías:
 * - **Armador**: `resolver()` de `features/armador/lib/resolver` (sólo lectura — archivo
 *   congelado de otra feature de esta tanda, pero un test puede leerlo).
 * - **Diagnóstico**: `valuarCartera()` de `lib/valuacion.ts`, con los mismos nominales que
 *   produjo el armador (`vn`), simulando que F-029 los resolvió así.
 *
 * No hay red acá: se compara puramente la salida de las funciones puras de las dos vías.
 */

import { describe, expect, it } from 'vitest'

import { resolver, type EntradaResolver } from '@/features/armador/lib/resolver'
import type { PosicionResuelta as PosicionResueltaF029 } from '@/features/cartera-resolucion/lib/schema'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import { plazoPromedio, rendimientosPorNaturaleza, sensibilidadPorSegmento } from '@/lib/cartera/metricas'

import { valuarCartera } from '../lib/valuacion'

function especie(overrides: Partial<Especie>): Especie {
  return {
    ticker: 'X',
    emision: 'X',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: null,
    duracion: null,
    vencimiento: null,
    ley: null,
    moneda_cupon: null,
    emisor: null,
    precio: null,
    moneda_cotizacion: null,
    volumen: null,
    volumen_usd: null,
    paridad: null,
    lamina: null,
    sector: null,
    dato_sano: true,
    hermanas: [],
    ...overrides,
  }
}

const TC = 1200
const MONTO_TOTAL_USD = 10_000

const AL30D = especie({
  ticker: 'AL30D',
  emision: 'AL30',
  precio: 70,
  moneda_cotizacion: 'USD',
  lamina: 1,
  naturaleza: 'tir_usd',
  naturaleza_nombre: 'TIR en dólares (hard dollar)',
  segmento: 'usd_hard',
  rendimiento: 0.11,
  duracion: 4.2,
  sector: 'Soberano',
})

const GD30D = especie({
  ticker: 'GD30D',
  emision: 'GD30',
  precio: 65,
  moneda_cotizacion: 'USD',
  lamina: 100,
  naturaleza: 'tir_usd',
  naturaleza_nombre: 'TIR en dólares (hard dollar)',
  segmento: 'usd_hard',
  rendimiento: 0.115,
  duracion: 4.5,
  sector: 'Soberano',
})

const TX26 = especie({
  ticker: 'TX26',
  emision: 'TX26',
  precio: 150,
  moneda_cotizacion: 'ARS',
  lamina: 1000,
  naturaleza: 'tasa_real_cer',
  naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)',
  segmento: 'ars_cer',
  rendimiento: 0.09,
  duracion: 2.1,
  sector: 'Soberano',
})

const UNIVERSO = new Map<string, Especie>([
  ['AL30D', AL30D],
  ['GD30D', GD30D],
  ['TX26', TX26],
])

const ENTRADAS: EntradaResolver[] = [
  { ticker: 'AL30D', peso: 40, precio: AL30D.precio, monedaCotizacion: 'usd', lamina: AL30D.lamina, esFci: false },
  { ticker: 'GD30D', peso: 35, precio: GD30D.precio, monedaCotizacion: 'usd', lamina: GD30D.lamina, esFci: false },
  { ticker: 'TX26', peso: 25, precio: TX26.precio, monedaCotizacion: 'ars', lamina: TX26.lamina, esFci: false },
]

function posicionResueltaSimulada(
  ticker: string,
  nominal: number,
  especieDeReferencia: Especie,
): PosicionResueltaF029 {
  return {
    id: `id-${ticker}`,
    fila: 1,
    ticker_declarado: ticker,
    nominal,
    monto: null,
    resuelta: true,
    ticker,
    emision: especieDeReferencia.emision,
    sufijo_liquidacion: especieDeReferencia.sufijo_liquidacion,
    moneda_cotizacion: especieDeReferencia.moneda_cotizacion,
    plazo_liquidacion: '2',
    clase_activo: especieDeReferencia.clase_activo,
    segmento: especieDeReferencia.segmento,
    naturaleza: especieDeReferencia.naturaleza,
    dato_sano: true,
    motivo: null,
    motivo_descripcion: null,
  }
}

describe('paridad armador ↔ diagnóstico, misma tenencia física', () => {
  const resueltasArmador = resolver(ENTRADAS, MONTO_TOTAL_USD, TC)

  // Ninguna entrada del fixture debería quedar sin resolver: si esto falla, el fixture está mal
  // armado y el resto del test no dice nada sobre paridad.
  it('el fixture resuelve las tres posiciones en el armador', () => {
    expect(resueltasArmador.every((r) => r.vn !== null)).toBe(true)
  })

  const posicionesF029Simuladas: PosicionResueltaF029[] = resueltasArmador.map((r) =>
    posicionResueltaSimulada(r.ticker, r.vn as number, UNIVERSO.get(r.ticker) as Especie),
  )

  const valuacionDiagnostico = valuarCartera(posicionesF029Simuladas, UNIVERSO, TC)

  it('no excluye ninguna posición en el diagnóstico', () => {
    expect(valuacionDiagnostico.excluidas).toHaveLength(0)
    expect(valuacionDiagnostico.valuadas).toHaveLength(3)
  })

  it('pesoReal coincide entre las dos vías, ticker por ticker', () => {
    const pesoArmador = new Map(resueltasArmador.map((r) => [r.ticker, r.pesoReal]))
    const pesoDiagnostico = new Map(valuacionDiagnostico.valuadas.map((v) => [v.ticker, v.pesoReal]))

    for (const ticker of UNIVERSO.keys()) {
      expect(pesoDiagnostico.get(ticker)).toBeCloseTo(pesoArmador.get(ticker) as number, 6)
    }
  })

  it('rendimientosPorNaturaleza da el mismo resultado con las dos salidas', () => {
    const deArmador = rendimientosPorNaturaleza(resueltasArmador, UNIVERSO)
    const deDiagnostico = rendimientosPorNaturaleza(valuacionDiagnostico.valuadas, UNIVERSO)
    expect(deDiagnostico).toEqual(deArmador)
  })

  it('plazoPromedio da el mismo resultado con las dos salidas', () => {
    const deArmador = plazoPromedio(resueltasArmador, UNIVERSO)
    const deDiagnostico = plazoPromedio(valuacionDiagnostico.valuadas, UNIVERSO)
    expect(deDiagnostico).toEqual(deArmador)
  })

  it('sensibilidadPorSegmento da el mismo resultado con las dos salidas', () => {
    const deArmador = sensibilidadPorSegmento(resueltasArmador, UNIVERSO)
    const deDiagnostico = sensibilidadPorSegmento(valuacionDiagnostico.valuadas, UNIVERSO)
    expect(deDiagnostico).toEqual(deArmador)
  })

  it('el cuerpo para /calendario/cartera es idéntico posición por posición', () => {
    const deArmador = resueltasArmador
      .filter((r): r is typeof r & { invertido: number } => r.invertido !== null && r.invertido > 0)
      .map((r) => ({ ticker: r.ticker, monto: r.invertido }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker))

    const deDiagnostico = valuacionDiagnostico.valuadas
      .map((v) => ({ ticker: v.ticker, monto: v.invertido }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker))

    expect(deDiagnostico).toEqual(deArmador)
  })

  it('el cuerpo para /concentracion es idéntico posición por posición', () => {
    const deArmador = resueltasArmador
      .map((r) => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker))

    const deDiagnostico = valuacionDiagnostico.valuadas
      .map((v) => ({ ticker: v.ticker, peso: v.pesoReal }))
      .sort((a, b) => a.ticker.localeCompare(b.ticker))

    expect(deDiagnostico).toEqual(deArmador)
  })
})
