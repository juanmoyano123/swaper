/**
 * El motor de F-022, aislado: sin red, sin store, sin React — mismo criterio que
 * `renta.test.ts`/`resolver.test.ts`. Cubre los cuatro GWT de la spec a nivel de cálculo puro; la
 * vuelta completa por la pantalla vive en `PanelRendimientos.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import { plazoPromedio, rendimientosPorNaturaleza, sensibilidadPorSegmento } from '../lib/rendimientos'
import type { PosicionResuelta } from '../lib/resolver'
import type { Especie } from '../lib/schema'

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'GD30',
    emision: 'GD30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.11,
    duracion: 3.2,
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
    ...extra,
  }
}

function posicion(extra: Partial<PosicionResuelta> = {}): PosicionResuelta {
  return {
    ticker: 'GD30',
    peso: 0,
    vn: 100,
    invertido: 1000,
    invertidoUsd: 1000,
    pesoReal: null,
    laminaConocida: true,
    esFci: false,
    cuotapartes: null,
    motivo: null,
    ...extra,
  }
}

/** Arma `porTicker` a partir de una lista de especies, indexado como lo hace `useCarteraResuelta`. */
function mapaDeEspecies(especies: Especie[]): Map<string, Especie> {
  return new Map(especies.map((e) => [e.ticker, e]))
}

describe('rendimientosPorNaturaleza', () => {
  it('GIVEN una cartera con hard-dollar, CER y tasa fija THEN aparecen tres números separados y el dólar-linked en cero, no ausente', () => {
    const especies = [
      especie({ ticker: 'GD30', naturaleza: 'tir_usd', rendimiento: 0.11 }),
      especie({
        ticker: 'TX26',
        naturaleza: 'tasa_real_cer',
        naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)',
        rendimiento: 0.06,
      }),
      especie({
        ticker: 'S31O5',
        naturaleza: 'tna_nominal_ars',
        naturaleza_nombre: 'TNA nominal en pesos',
        rendimiento: 0.4,
      }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 50, pesoReal: 50 }),
      posicion({ ticker: 'TX26', peso: 30, pesoReal: 30 }),
      posicion({ ticker: 'S31O5', peso: 20, pesoReal: 20 }),
    ]

    const resultado = rendimientosPorNaturaleza(posiciones, mapaDeEspecies(especies))

    expect(resultado.map((r) => r.naturaleza)).toEqual([
      'tir_usd',
      'tir_dolar_linked',
      'tasa_real_cer',
      'tna_nominal_ars',
    ])

    const hard = resultado.find((r) => r.naturaleza === 'tir_usd')!
    expect(hard.pctCartera).toBeCloseTo(50)
    expect(hard.rendimientoPond).toBeCloseTo(0.11)

    const cer = resultado.find((r) => r.naturaleza === 'tasa_real_cer')!
    expect(cer.pctCartera).toBeCloseTo(30)
    expect(cer.rendimientoPond).toBeCloseTo(0.06)

    const tna = resultado.find((r) => r.naturaleza === 'tna_nominal_ars')!
    expect(tna.pctCartera).toBeCloseTo(20)
    expect(tna.rendimientoPond).toBeCloseTo(0.4)

    const dl = resultado.find((r) => r.naturaleza === 'tir_dolar_linked')!
    expect(dl.pctCartera).toBe(0)
    expect(dl.rendimientoPond).toBeNull()
    expect(dl.posiciones).toBe(0)
  })

  it('GIVEN una cartera 100% hard-dollar THEN las otras tres aparecen en cero por ciento, no ausentes', () => {
    const especies = [especie({ ticker: 'GD30', naturaleza: 'tir_usd', rendimiento: 0.11 })]
    const posiciones = [posicion({ ticker: 'GD30', peso: 100, pesoReal: 100 })]

    const resultado = rendimientosPorNaturaleza(posiciones, mapaDeEspecies(especies))

    expect(resultado).toHaveLength(4)
    for (const naturaleza of ['tir_dolar_linked', 'tasa_real_cer', 'tna_nominal_ars']) {
      const fila = resultado.find((r) => r.naturaleza === naturaleza)!
      expect(fila.pctCartera).toBe(0)
      expect(fila.rendimientoPond).toBeNull()
    }
  })

  it('GIVEN posiciones sin rendimiento informado THEN quedan excluidas del ponderado pero siguen contando en pctCartera', () => {
    const especies = [
      especie({ ticker: 'GD30', naturaleza: 'tir_usd', rendimiento: 0.11 }),
      especie({ ticker: 'AL30', naturaleza: 'tir_usd', rendimiento: null }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 60, pesoReal: 60 }),
      posicion({ ticker: 'AL30', peso: 40, pesoReal: 40 }),
    ]

    const resultado = rendimientosPorNaturaleza(posiciones, mapaDeEspecies(especies))
    const hard = resultado.find((r) => r.naturaleza === 'tir_usd')!

    // pctCartera cuenta las dos posiciones (la plata está ahí); el ponderado sólo usa GD30.
    expect(hard.pctCartera).toBeCloseTo(100)
    expect(hard.rendimientoPond).toBeCloseTo(0.11)
    expect(hard.posiciones).toBe(2)
    expect(hard.posicionesExcluidas).toBe(1)
    expect(hard.pctExcluido).toBeCloseTo(40)
  })

  it('GIVEN que TODAS las posiciones de una naturaleza no tienen rendimiento THEN rendimientoPond es null, nunca cero, y pctExcluido iguala al pctCartera del grupo', () => {
    const especies = [
      especie({ ticker: 'GD30', naturaleza: 'tir_usd', rendimiento: null }),
      especie({ ticker: 'AL30', naturaleza: 'tir_usd', rendimiento: null }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 60, pesoReal: 60 }),
      posicion({ ticker: 'AL30', peso: 40, pesoReal: 40 }),
    ]

    const resultado = rendimientosPorNaturaleza(posiciones, mapaDeEspecies(especies))
    const hard = resultado.find((r) => r.naturaleza === 'tir_usd')!

    expect(hard.pctCartera).toBeCloseTo(100)
    expect(hard.rendimientoPond).toBeNull()
    expect(hard.pctExcluido).toBeCloseTo(hard.pctCartera)
  })

  it('GIVEN una posición sin peso ni pesoReal resuelto THEN no aporta a pctCartera de ninguna naturaleza', () => {
    const especies = [especie({ ticker: 'GD30', naturaleza: 'tir_usd', rendimiento: 0.11 })]
    const posiciones = [
      // Fixture sintética: `peso` es `number` por contrato del resolver y nunca llega null en la
      // app real, pero la función pura se defiende igual contra el caso — se simula acá con un
      // cast, no reproducible desde `useCarteraResuelta`.
      posicion({ ticker: 'GD30', peso: null as unknown as number, pesoReal: null }),
    ]

    const resultado = rendimientosPorNaturaleza(posiciones, mapaDeEspecies(especies))
    const hard = resultado.find((r) => r.naturaleza === 'tir_usd')!

    expect(hard.pctCartera).toBe(0)
    expect(hard.posiciones).toBe(0)
    expect(hard.rendimientoPond).toBeNull()
  })

  it('GIVEN una cartera vacía THEN las cuatro naturalezas quedan en pctCartera 0 y rendimientoPond null', () => {
    const resultado = rendimientosPorNaturaleza([], new Map())

    expect(resultado).toHaveLength(4)
    for (const fila of resultado) {
      expect(fila.pctCartera).toBe(0)
      expect(fila.rendimientoPond).toBeNull()
    }
  })
})

describe('plazoPromedio', () => {
  it('pondera la duración de toda la cartera de renta fija, sin agrupar por naturaleza', () => {
    const especies = [
      especie({ ticker: 'GD30', naturaleza: 'tir_usd', duracion: 3 }),
      especie({ ticker: 'TX26', naturaleza: 'tasa_real_cer', duracion: 1 }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 50, pesoReal: 50 }),
      posicion({ ticker: 'TX26', peso: 50, pesoReal: 50 }),
    ]

    const resultado = plazoPromedio(posiciones, mapaDeEspecies(especies))

    expect(resultado.anios).toBeCloseTo(2)
    expect(resultado.posicionesExcluidas).toBe(0)
  })

  it('excluye del cálculo las posiciones sin duración informada y las declara', () => {
    const especies = [
      especie({ ticker: 'GD30', duracion: 4 }),
      especie({ ticker: 'AL30', duracion: null }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 50, pesoReal: 50 }),
      posicion({ ticker: 'AL30', peso: 50, pesoReal: 50 }),
    ]

    const resultado = plazoPromedio(posiciones, mapaDeEspecies(especies))

    expect(resultado.anios).toBeCloseTo(2) // 4 * 50/100, la otra no aporta
    expect(resultado.posicionesExcluidas).toBe(1)
  })

  it('cartera vacía → anios null y cero posiciones excluidas', () => {
    expect(plazoPromedio([], new Map())).toEqual({ anios: null, posicionesExcluidas: 0 })
  })
})

describe('sensibilidadPorSegmento', () => {
  it('GIVEN dos segmentos con posiciones THEN devuelve dos entradas, ninguna agregada entre sí', () => {
    const especies = [
      especie({ ticker: 'GD30', segmento: 'usd_hard', duracion: 3 }),
      especie({ ticker: 'TX26', segmento: 'cer', duracion: 1.5 }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 60, pesoReal: 60 }),
      posicion({ ticker: 'TX26', peso: 40, pesoReal: 40 }),
    ]

    const resultado = sensibilidadPorSegmento(posiciones, mapaDeEspecies(especies))

    expect(resultado).toHaveLength(2)
    const hard = resultado.find((s) => s.segmento === 'usd_hard')!
    const cer = resultado.find((s) => s.segmento === 'cer')!
    expect(hard.duracionPond).toBeCloseTo(3)
    expect(cer.duracionPond).toBeCloseTo(1.5)
    expect(hard.pctCartera).toBeCloseTo(60)
    expect(cer.pctCartera).toBeCloseTo(40)
    // Orden por pctCartera desc.
    expect(resultado[0].segmento).toBe('usd_hard')
  })

  it('dos segmentos en pesos con la misma naturaleza (tasa_fija y badlar) se reportan separados', () => {
    const especies = [
      especie({ ticker: 'S31O5', segmento: 'tasa_fija', naturaleza: 'tna_nominal_ars', duracion: 0.5 }),
      especie({ ticker: 'BADLAR1', segmento: 'badlar', naturaleza: 'tna_nominal_ars', duracion: 1 }),
    ]
    const posiciones = [
      posicion({ ticker: 'S31O5', peso: 50, pesoReal: 50 }),
      posicion({ ticker: 'BADLAR1', peso: 50, pesoReal: 50 }),
    ]

    const resultado = sensibilidadPorSegmento(posiciones, mapaDeEspecies(especies))

    expect(resultado.map((s) => s.segmento).sort()).toEqual(['badlar', 'tasa_fija'])
  })
})
