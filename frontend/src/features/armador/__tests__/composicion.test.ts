/**
 * El motor de F-023, aislado: sin red, sin store, sin React — mismo criterio que
 * `rendimientos.test.ts`. La vuelta completa por la pantalla vive en `PanelComposicion.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import {
  composicionPorClase,
  composicionPorEmisor,
  composicionPorSegmento,
  leyendaDelPeso,
} from '../lib/composicion'
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
    ...extra,
  }
}

function mapaDeEspecies(especies: Especie[]): Map<string, Especie> {
  return new Map(especies.map((e) => [e.ticker, e]))
}

describe('composicionPorClase', () => {
  it('GIVEN posiciones soberanas con distintos prefijos (GD/AE/DIC/TZX/TY3) THEN quedan en un único tramo, la regla 4 hecha agrupación', () => {
    const especies = [
      especie({ ticker: 'GD30', clase_activo: 'bono_soberano' }),
      especie({ ticker: 'AE38', clase_activo: 'bono_soberano' }),
      especie({ ticker: 'DICP', clase_activo: 'bono_soberano' }),
      especie({ ticker: 'TZX26', clase_activo: 'bono_soberano' }),
      especie({ ticker: 'TY3', clase_activo: 'bono_soberano' }),
    ]
    const posiciones = especies.map((e) => posicion({ ticker: e.ticker, peso: 20, pesoReal: 20 }))

    const resultado = composicionPorClase(posiciones, mapaDeEspecies(especies))

    expect(resultado).toHaveLength(1)
    expect(resultado[0]).toEqual({ nombre: 'Soberano', peso: 100, sinDato: undefined })
  })

  it('GIVEN clases distintas THEN aparecen en tramos separados, ordenados por peso descendente', () => {
    const especies = [
      especie({ ticker: 'GD30', clase_activo: 'bono_soberano' }),
      especie({ ticker: 'YMCHO', clase_activo: 'on_corporativo' }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 30, pesoReal: 30 }),
      posicion({ ticker: 'YMCHO', peso: 70, pesoReal: 70 }),
    ]

    const resultado = composicionPorClase(posiciones, mapaDeEspecies(especies))

    expect(resultado.map((t) => t.nombre)).toEqual(['ON corporativa', 'Soberano'])
    expect(resultado[0].peso).toBeCloseTo(70)
    expect(resultado[1].peso).toBeCloseTo(30)
  })

  it('una posición cuyo ticker no está en el universo se excluye del corte', () => {
    const especies = [especie({ ticker: 'GD30' })]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 50, pesoReal: 50 }),
      posicion({ ticker: 'FUERA_DE_UNIVERSO', peso: 50, pesoReal: 50 }),
    ]

    const resultado = composicionPorClase(posiciones, mapaDeEspecies(especies))

    expect(resultado).toHaveLength(1)
    expect(resultado[0].peso).toBeCloseTo(50)
  })

  it('cartera vacía devuelve un corte vacío, no un tramo con peso cero', () => {
    expect(composicionPorClase([], new Map())).toEqual([])
  })
})

describe('composicionPorSegmento', () => {
  it('GIVEN dos segmentos THEN devuelve dos tramos, ninguno agregado entre sí', () => {
    const especies = [
      especie({ ticker: 'GD30', segmento: 'usd_hard' }),
      especie({ ticker: 'TX26', segmento: 'cer' }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 60, pesoReal: 60 }),
      posicion({ ticker: 'TX26', peso: 40, pesoReal: 40 }),
    ]

    const resultado = composicionPorSegmento(posiciones, mapaDeEspecies(especies))

    expect(resultado.map((t) => t.nombre)).toEqual(['Dólar hard', 'CER'])
  })
})

describe('composicionPorEmisor', () => {
  it('GIVEN un emisor con `emisor: null` THEN agrupa en "emisor no informado", con `sinDato: true`, sin repartir entre los conocidos', () => {
    const especies = [
      especie({ ticker: 'GD30', emisor: 'República Argentina' }),
      especie({ ticker: 'YMCHO', emisor: null }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 60, pesoReal: 60 }),
      posicion({ ticker: 'YMCHO', peso: 40, pesoReal: 40 }),
    ]

    const resultado = composicionPorEmisor(posiciones, mapaDeEspecies(especies))

    const sinInformar = resultado.find((t) => t.sinDato)
    expect(sinInformar).toEqual({ nombre: 'emisor no informado', peso: 40, sinDato: true })
    const conocido = resultado.find((t) => !t.sinDato)
    expect(conocido).toEqual({ nombre: 'República Argentina', peso: 60, sinDato: undefined })
  })

  it('suma el peso de dos emisiones del mismo emisor en un solo tramo', () => {
    const especies = [
      especie({ ticker: 'GD30', emisor: 'República Argentina' }),
      especie({ ticker: 'AE38', emisor: 'República Argentina' }),
    ]
    const posiciones = [
      posicion({ ticker: 'GD30', peso: 30, pesoReal: 30 }),
      posicion({ ticker: 'AE38', peso: 30, pesoReal: 30 }),
    ]

    const resultado = composicionPorEmisor(posiciones, mapaDeEspecies(especies))

    expect(resultado).toEqual([{ nombre: 'República Argentina', peso: 60, sinDato: undefined }])
  })
})

describe('ponderación por peso real o pedido', () => {
  it('cuando ninguna posición tiene `pesoReal`, se pondera por `peso`', () => {
    const especies = [especie({ ticker: 'GD30' })]
    const posiciones = [posicion({ ticker: 'GD30', peso: 100, pesoReal: null })]

    const resultado = composicionPorClase(posiciones, mapaDeEspecies(especies))

    expect(resultado[0].peso).toBeCloseTo(100)
  })
})

describe('leyendaDelPeso', () => {
  it('declara peso real cuando se resolvió todo', () => {
    expect(leyendaDelPeso(2, 2)).toMatch(/peso real de las 2 posiciones/)
  })

  it('declara ponderación pedida cuando no se resolvió nada', () => {
    expect(leyendaDelPeso(0, 2)).toMatch(/ponderación pedida de las 2 posiciones/)
  })

  it('declara la mezcla cuando sólo una parte se resolvió', () => {
    expect(leyendaDelPeso(1, 2)).toMatch(/peso real en 1 de 2 posiciones/)
  })
})
