import { describe, expect, it } from 'vitest'

import type { EspecieRentaVariable } from '@/lib/rentaVariable'
import { agruparEnPapeles, papelCoincide } from '../lib/papelesRentaVariable'

function especie(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  return {
    ticker: 'AAPL',
    clase_activo: 'cedear',
    precio: 24050,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 23800,
    variacion: 0.0105,
    volumen: 700545,
    volumen_usd: 700545,
    px_bid: null,
    px_ask: null,
    operaciones: 120,
    fuente: 'byma',
    emision: 'AAPL',
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_corto: null,
    nombre_largo: null,
    sector: null,
    industria: null,
    pais: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    ...extra,
  }
}

const APPLE = [
  especie({ ticker: 'AAPL', volumen_usd: 700545 }),
  especie({ ticker: 'AAPLD', sufijo_liquidacion: 'D', precio: 15.8, volumen_usd: 485259 }),
  especie({ ticker: 'AAPLC', sufijo_liquidacion: 'C', precio: 15.17, volumen_usd: null }),
]

describe('agruparEnPapeles', () => {
  it('las tres especies de Apple son un solo papel', () => {
    const papeles = agruparEnPapeles(APPLE)

    expect(papeles).toHaveLength(1)
    expect(papeles[0].emision).toBe('AAPL')
    expect(papeles[0].especies.map((e) => e.especie.ticker)).toEqual(['AAPL', 'AAPLD', 'AAPLC'])
  })

  it('las monedas se rotulan y se ordenan ARS → MEP → Cable', () => {
    const [papel] = agruparEnPapeles(APPLE)
    expect(papel.especies.map((e) => e.rotulo)).toEqual(['ARS', 'MEP', 'Cable'])
  })

  it('marca qué especies operan: sin precio no se puede comprar', () => {
    const [papel] = agruparEnPapeles([
      especie({ ticker: 'AAPL' }),
      especie({ ticker: 'AAPLD', sufijo_liquidacion: 'D', precio: null }),
    ])
    expect(papel.especies.map((e) => e.opera)).toEqual([true, false])
  })

  it('representa al papel la especie de más volumen EN DÓLARES, no el crudo', () => {
    // La especie en pesos muestra ~1.500 veces más volumen crudo por el tipo de cambio, no por
    // liquidez: con el crudo siempre ganaría ella.
    const [papel] = agruparEnPapeles([
      especie({ ticker: 'AAPL', volumen: 900_000_000, volumen_usd: 100 }),
      especie({ ticker: 'AAPLD', sufijo_liquidacion: 'D', volumen: 500, volumen_usd: 90_000 }),
    ])
    expect(papel.representante.ticker).toBe('AAPLD')
  })

  it('un papel de una sola especie sigue siendo un papel', () => {
    const papeles = agruparEnPapeles([especie({ ticker: 'ABEV3', emision: 'ABEV3' })])
    expect(papeles).toHaveLength(1)
    expect(papeles[0].especies).toHaveLength(1)
  })

  it('las no identificadas no se mezclan entre sí', () => {
    // Compartir el cajón de lo desconocido no las hace el mismo CEDEAR.
    const papeles = agruparEnPapeles([
      especie({ ticker: 'AAPLB', emision: 'n/n', no_identificado: true }),
      especie({ ticker: 'XOMB', emision: 'n/n', no_identificado: true }),
    ])
    expect(papeles).toHaveLength(2)
    expect(papeles.every((p) => p.noIdentificado)).toBe(true)
  })

  it('sin `emision` cada especie es su propio papel: se degrada, no rompe', () => {
    // Una respuesta de un backend anterior a esta feature.
    const papeles = agruparEnPapeles([
      especie({ ticker: 'AAPL', emision: null }),
      especie({ ticker: 'AAPLD', emision: null, sufijo_liquidacion: null }),
    ])
    expect(papeles).toHaveLength(2)
  })
})

describe('papelCoincide', () => {
  it('buscar el ticker de una hermana encuentra el papel entero', () => {
    const [papel] = agruparEnPapeles(APPLE)
    expect(papelCoincide(papel, 'AAPLD')).toBe(true)
  })

  it('busca también por nombre de empresa', () => {
    const [papel] = agruparEnPapeles([especie({ nombre_corto: 'Apple Inc.' })])
    expect(papelCoincide(papel, 'apple')).toBe(true)
  })

  it('sin búsqueda, todos coinciden', () => {
    const [papel] = agruparEnPapeles(APPLE)
    expect(papelCoincide(papel, '  ')).toBe(true)
  })

  it('lo que no coincide, no coincide', () => {
    const [papel] = agruparEnPapeles(APPLE)
    expect(papelCoincide(papel, 'TSLA')).toBe(false)
  })
})
