/**
 * Presets temáticos — Tanda 13.
 *
 * El test que importa es el primero: ningún preset puede filtrar por un sector que no existe en el
 * universo. Un atajo que devuelve cero papeles sin explicar por qué es peor que no tener el atajo,
 * y la lista de sectores válidos sale de `data/condiciones_emision.csv`, no de lo que suene bien.
 */

import { describe, expect, it } from 'vitest'

import { FILTROS_ARMADOR_VACIOS } from '../lib/filtros'
import {
  coincideConPreset,
  filtrosDelPreset,
  presetPorId,
  PRESETS_TEMATICOS,
} from '../lib/tematicas'

/** Los sectores que de verdad existen en `data/condiciones_emision.csv`, verificados el 10/08/2026. */
const SECTORES_DE_RENTA_FIJA = [
  'Soberano',
  'O&G',
  'Financiera',
  'Subsoberano',
  'Servicios',
  'Agro',
  'Industria',
  'Real Estate',
  'Energias Renovables',
  'Alimentos y Consumo',
  'Telecomunicaciones',
  'Construccion',
  'Infraestructura',
  'Mineria',
]

/** Las claves de segmento del universo. */
const SEGMENTOS = ['usd_hard', 'cer', 'tasa_fija', 'dollar_linked', 'badlar', 'tamar']

describe('los presets sólo referencian datos que existen', () => {
  it.each(PRESETS_TEMATICOS)('$etiqueta filtra por un sector real del universo', (preset) => {
    const sector = preset.filtrosRf?.sector
    if (sector) expect(SECTORES_DE_RENTA_FIJA).toContain(sector)
  })

  it.each(PRESETS_TEMATICOS)('$etiqueta filtra por un segmento real', (preset) => {
    const segmento = preset.filtrosRf?.segmento
    if (segmento) expect(SEGMENTOS).toContain(segmento)
  })

  it.each(PRESETS_TEMATICOS)('$etiqueta explica en su nota qué precarga', (preset) => {
    expect(preset.nota.length).toBeGreaterThan(20)
  })

  it('el preset de tecnológicas declara que no filtra renta fija en vez de aproximar con otro sector', () => {
    const tecnologicas = presetPorId('tecnologicas')

    // No hay emisores tecnológicos en el universo de bonos: mapearlo a Telecomunicaciones sería
    // presentar una aproximación como si fuera el dato pedido.
    expect(tecnologicas?.filtrosRf).toBeNull()
    expect(tecnologicas?.sectorRv).toBe('Technology')
    expect(tecnologicas?.nota).toMatch(/Sólo renta variable/)
  })

  it('cobertura inflación no filtra renta variable: una acción no ajusta por CER', () => {
    expect(presetPorId('cobertura-inflacion')?.sectorRv).toBeNull()
  })
})

describe('filtrosDelPreset', () => {
  it('parte de todo limpio, para que el resultado no dependa de lo que estaba activo antes', () => {
    const energia = presetPorId('energia')!
    const filtros = filtrosDelPreset(energia)

    expect(filtros.sector).toBe('O&G')
    expect(filtros.tirMin).toBe('')
    expect(filtros.calificaciones).toEqual([])
  })

  it('un preset sin filtros de renta fija deja la grilla sin filtrar', () => {
    const tecnologicas = presetPorId('tecnologicas')!

    expect(filtrosDelPreset(tecnologicas)).toEqual(FILTROS_ARMADOR_VACIOS)
  })
})

describe('coincideConPreset', () => {
  it('reconoce los filtros que el preset acaba de dejar', () => {
    const energia = presetPorId('energia')!

    expect(coincideConPreset(filtrosDelPreset(energia), energia)).toBe(true)
  })

  it('deja de coincidir apenas se toca un filtro a mano', () => {
    const energia = presetPorId('energia')!
    const tocado = { ...filtrosDelPreset(energia), tirMin: '8' }

    expect(coincideConPreset(tocado, energia)).toBe(false)
  })

  it('no coincide con los filtros de otro preset', () => {
    const energia = presetPorId('energia')!
    const financieras = presetPorId('financieras')!

    expect(coincideConPreset(filtrosDelPreset(financieras), energia)).toBe(false)
  })
})

describe('presetPorId', () => {
  it('devuelve null para un id que no existe, en vez de tirar', () => {
    expect(presetPorId('no-existe')).toBeNull()
    expect(presetPorId(null)).toBeNull()
  })
})
