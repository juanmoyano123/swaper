/**
 * La aritmética del plan acumulado de F-036: acumulación de posiciones y de montos en cadena,
 * inversas de lo aceptado, y separación de candidatas ya decididas en la sesión.
 */

import { describe, expect, it } from 'vitest'

import type { Candidata } from '../esquemaRotaciones'
import { clavesInversas, montosAcumulados, posicionesAcumuladas, separarYaDecididas } from '../plan'

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: {
      ticker: origenTicker,
      emisor: 'República Argentina',
      rendimiento: 0.1,
      duracion: 3,
      moneda_cupon: 'USD',
      ley: 'Ley N.Y.',
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 100_000,
    },
    destino: {
      ticker: destinoTicker,
      emisor: 'República Argentina',
      rendimiento: 0.12,
      duracion: 4,
      moneda_cupon: 'USD',
      ley: 'Ley N.Y.',
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 200_000,
    },
    delta: { rendimiento_pp: 2, duracion: 1 },
    flags: {
      mismo_emisor: true,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: null,
  }
}

describe('posicionesAcumuladas', () => {
  it('aplica una cadena de rotaciones en orden: A->B y después B->C', () => {
    const originales = [{ ticker: 'A', peso: 40 }, { ticker: 'X', peso: 60 }]
    const resultado = posicionesAcumuladas(originales, [candidata('A', 'B'), candidata('B', 'C')])
    expect(resultado).toEqual(expect.arrayContaining([{ ticker: 'X', peso: 60 }, { ticker: 'C', peso: 40 }]))
    expect(resultado).toHaveLength(2)
  })

  it('suma el peso si el destino ya está en la cartera', () => {
    const originales = [{ ticker: 'A', peso: 30 }, { ticker: 'B', peso: 20 }]
    const resultado = posicionesAcumuladas(originales, [candidata('A', 'B')])
    expect(resultado).toEqual([{ ticker: 'B', peso: 50 }])
  })

  it('sin aceptadas, devuelve las originales sin tocar', () => {
    const originales = [{ ticker: 'A', peso: 100 }]
    expect(posicionesAcumuladas(originales, [])).toEqual(originales)
  })
})

describe('montosAcumulados', () => {
  const monedaUsd = () => 'usd' as const

  it('pasa el monto sin convertir cuando origen y destino cotizan en la misma moneda', () => {
    const originales = [{ ticker: 'A', monto: 1000 }]
    const { montos, noConvertibles } = montosAcumulados(originales, [candidata('A', 'B')], monedaUsd, null)
    expect(montos).toEqual([{ ticker: 'B', monto: 1000 }])
    expect(noConvertibles).toEqual([])
  })

  it('normaliza con el tipo de cambio cuando las monedas de cotización difieren', () => {
    const monedaDe = (ticker: string) => ticker === 'A' ? ('ars' as const) : ('usd' as const)
    const originales = [{ ticker: 'A', monto: 105_000 }]
    const { montos, noConvertibles } = montosAcumulados(originales, [candidata('A', 'B')], monedaDe, 1050)
    expect(montos).toEqual([{ ticker: 'B', monto: 100 }])
    expect(noConvertibles).toEqual([])
  })

  it('sin tipo de cambio y monedas distintas, declara el ticker no convertible y no inventa un monto', () => {
    const monedaDe = (ticker: string) => ticker === 'A' ? ('ars' as const) : ('usd' as const)
    const originales = [{ ticker: 'A', monto: 105_000 }]
    const { montos, noConvertibles } = montosAcumulados(originales, [candidata('A', 'B')], monedaDe, null)
    expect(montos).toEqual([])
    expect(noConvertibles).toEqual(['B'])
  })

  it('una moneda de cotización no reconocida (EXT, regla 11) tampoco se convierte', () => {
    const monedaDe = (ticker: string) => (ticker === 'A' ? 'usd' : null)
    const originales = [{ ticker: 'A', monto: 500 }]
    const { montos, noConvertibles } = montosAcumulados(originales, [candidata('A', 'B')], monedaDe, 1050)
    expect(montos).toEqual([])
    expect(noConvertibles).toEqual(['B'])
  })

  it('suma el monto si el destino ya está en la cartera', () => {
    const originales = [{ ticker: 'A', monto: 300 }, { ticker: 'B', monto: 200 }]
    const { montos } = montosAcumulados(originales, [candidata('A', 'B')], monedaUsd, null)
    expect(montos).toEqual([{ ticker: 'B', monto: 500 }])
  })
})

describe('clavesInversas', () => {
  it('devuelve la clave B->A por cada A->B aceptada', () => {
    const resultado = clavesInversas([candidata('A', 'B'), candidata('B', 'C')])
    expect(resultado).toEqual(new Set(['B->A', 'C->B']))
  })

  it('sin aceptadas, el set está vacío', () => {
    expect(clavesInversas([])).toEqual(new Set())
  })
})

describe('separarYaDecididas', () => {
  it('excluye las candidatas cuya clave está en el set de exclusión', () => {
    const candidatas = [candidata('A', 'B'), candidata('C', 'D')]
    const { vigentes, excluidas } = separarYaDecididas(candidatas, new Set(['A->B']))
    expect(vigentes).toEqual([candidata('C', 'D')])
    expect(excluidas).toBe(1)
  })

  it('sin exclusiones, todas quedan vigentes', () => {
    const candidatas = [candidata('A', 'B')]
    const { vigentes, excluidas } = separarYaDecididas(candidatas, new Set())
    expect(vigentes).toEqual(candidatas)
    expect(excluidas).toBe(0)
  })
})
