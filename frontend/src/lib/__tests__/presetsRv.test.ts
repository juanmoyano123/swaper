/**
 * `lib/presetsRv.ts` — F-078 (metales-preciosos, cripto) y F-079 (sectores, financieras,
 * tecnologicas, medicina).
 *
 * Lo que importa de los tres presets nuevos es la regresión: hasta F-079 `financieras`,
 * `tecnologicas` y `medicina` vivían como `rubroRv: 'Office of ...'` inline en
 * `features/armador/lib/tematicas.ts`, comparando literalmente contra `sic_oficina`. Acá se prueba
 * que el preset compartido filtra exactamente ese mismo conjunto — un CEDEAR con esa oficina entra,
 * uno con otra oficina no, y uno sin oficina declarada tampoco (regla 1: un dato que falta nunca
 * cumple un filtro activo).
 */

import { describe, expect, it } from 'vitest'

import type { EspecieRentaVariable } from '../rentaVariable'
import { cumpleFiltroRv, presetRvPorId, PRESETS_RV, type FiltroRv } from '../presetsRv'

function especie(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  return {
    ticker: 'AAPL',
    clase_activo: 'cedear',
    precio: 100,
    moneda_cotizacion: 'USD',
    cierre_anterior: 99,
    variacion: 0.01,
    volumen: 1000,
    volumen_usd: 1000,
    px_bid: null,
    px_ask: null,
    operaciones: null,
    fuente: null,
    emision: 'AAPL',
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    sector_codigo: null,
    sector: null,
    sector_titulo: null,
    rubro_especifico: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    region_etf: null,
    etf_indice: null,
    etf_alcance: null,
    etf_pais: null,
    etf_region: null,
    etf_geo_fuente: null,
    etf_geo_verificado: null,
    pais: null,
    region: null,
    pais_fuente: null,
    pais_verificado: null,
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    ...extra,
  }
}

describe('PRESETS_RV', () => {
  it('trae los cinco presets: los dos de F-078 y los tres de F-079', () => {
    expect(PRESETS_RV.map((p) => p.id)).toEqual([
      'metales-preciosos',
      'cripto',
      'financieras',
      'tecnologicas',
      'medicina',
    ])
  })

  it.each([
    ['financieras', 'Office of Finance'],
    ['tecnologicas', 'Office of Technology'],
    ['medicina', 'Office of Life Sciences'],
  ])('%s tiene id, etiqueta, modo interseccion y una nota que declara la oficina', (id, oficina) => {
    const preset = presetRvPorId(id)

    expect(preset).not.toBeNull()
    expect(preset?.id).toBe(id)
    expect(preset?.etiqueta.length).toBeGreaterThan(0)
    expect(preset?.modo).toBe('interseccion')
    expect(preset?.filtro).toEqual({ rubros: [oficina] })
    expect(preset?.nota).toContain(oficina)
  })

  it.each([
    ['financieras', 'Office of Finance'],
    ['tecnologicas', 'Office of Technology'],
    ['medicina', 'Office of Life Sciences'],
  ])(
    '%s filtra el mismo conjunto que el `rubroRv` inline de antes de F-079: sólo esa oficina',
    (id, oficina) => {
      const filtro = presetRvPorId(id)!.filtro
      const modo = presetRvPorId(id)!.modo

      const deLaOficina = especie({ ticker: 'A', sic_oficina: oficina })
      const deOtraOficina = especie({ ticker: 'B', sic_oficina: 'Office of Trade & Services' })
      const sinOficina = especie({ ticker: 'C', sic_oficina: null })

      expect(cumpleFiltroRv(deLaOficina, filtro, modo)).toBe(true)
      expect(cumpleFiltroRv(deOtraOficina, filtro, modo)).toBe(false)
      // Regla 1: un dato que falta no cumple un filtro activo, nunca se asume.
      expect(cumpleFiltroRv(sinOficina, filtro, modo)).toBe(false)
    },
  )

  it('metales-preciosos y cripto (F-078) no cambiaron con esta fase', () => {
    expect(presetRvPorId('metales-preciosos')?.modo).toBe('union')
    expect(presetRvPorId('metales-preciosos')?.filtro).toEqual({
      estrategiasEtf: ['activo_fisico'],
      sicCodigos: ['1040'],
      palabrasEnNombre: ['gold', 'silver', 'oro', 'plata'],
    })
    expect(presetRvPorId('cripto')?.filtro).toEqual({ estrategiasEtf: ['cripto'] })
  })

  it('presetRvPorId devuelve null para un id que no existe o para null, en vez de tirar', () => {
    expect(presetRvPorId('no-existe')).toBeNull()
    expect(presetRvPorId(null)).toBeNull()
  })
})

describe('el filtro `sectores` (F-079)', () => {
  const filtro: FiltroRv = { sectores: ['73'] }

  it('compara contra `sector_codigo`, el major group de dos dígitos', () => {
    expect(cumpleFiltroRv(especie({ sector_codigo: '73' }), filtro)).toBe(true)
    expect(cumpleFiltroRv(especie({ sector_codigo: '28' }), filtro)).toBe(false)
  })

  it('un papel sin sector_codigo no cumple un filtro de sectores activo', () => {
    expect(cumpleFiltroRv(especie({ sector_codigo: null }), filtro)).toBe(false)
  })
})
