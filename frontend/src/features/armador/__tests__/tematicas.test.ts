/**
 * Presets temáticos — Tanda 13.
 *
 * El test que importa es el primero: ningún preset puede filtrar por un sector que no existe en el
 * universo. Un atajo que devuelve cero papeles sin explicar por qué es peor que no tener el atajo,
 * y la lista de sectores válidos sale de `data/condiciones_emision.csv`, no de lo que suene bien.
 */

import { describe, expect, it } from 'vitest'

import { presetRvPorId } from '@/lib/presetsRv'

import { FILTROS_ARMADOR_VACIOS } from '../lib/filtros'
import {
  coincideConPreset,
  filtraRentaVariable,
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
    const compartido = presetRvPorId('tecnologicas')

    // No hay emisores tecnológicos en el universo de bonos: mapearlo a Telecomunicaciones sería
    // presentar una aproximación como si fuera el dato pedido.
    expect(tecnologicas?.filtrosRf).toBeNull()
    // F-079: migrado de `rubroRv` inline a referenciar el preset compartido — mismo `sic_oficina`
    // (`Office of Technology`), mismo conjunto de especies, sólo cambia dónde vive la definición.
    expect(tecnologicas?.rubroRv).toBeNull()
    expect(tecnologicas?.filtroRv).toBe(compartido?.filtro)
    expect(tecnologicas?.filtroRv).toEqual({ rubros: ['Office of Technology'] })
    expect(tecnologicas?.nota).toMatch(/Sólo renta variable/)
  })

  it('cobertura inflación no filtra renta variable: una acción no ajusta por CER', () => {
    expect(presetPorId('cobertura-inflacion')?.rubroRv).toBeNull()
  })

  // --- F-078 -----------------------------------------------------------------------------------

  it('metales preciosos referencia el preset compartido en vez de duplicar su definición', () => {
    const metales = presetPorId('metales-preciosos')
    const compartido = presetRvPorId('metales-preciosos')

    // Identidad, no igualdad estructural: si alguien duplicara la definición acá, el monitor y el
    // armador podrían empezar a decir cosas distintas sobre qué es un metal precioso.
    expect(metales?.filtroRv).toBe(compartido?.filtro)
    expect(metales?.modoFiltroRv).toBe('union')
    // Es multidimensional, así que no se puede decir con un `sic_oficina`: `rubroRv` queda en null.
    expect(metales?.rubroRv).toBeNull()
    // Y su nota lleva la del preset compartido, con lo que deja afuera.
    expect(metales?.nota).toContain(compartido!.nota)
  })

  it('las temáticas que acotan la renta variable son las que se ofrecen en el armado asistido', () => {
    const ofrecidas = PRESETS_TEMATICOS.filter(filtraRentaVariable).map((p) => p.id)

    // Las dos formas de acotar: por rubro suelto y por filtro multidimensional.
    expect(ofrecidas).toContain('tecnologicas')
    expect(ofrecidas).toContain('metales-preciosos')
    // Las que declaran que no pueden acotar la renta variable no se ofrecen: elegirlas no
    // cambiaría nada del bloque de CEDEARs.
    expect(ofrecidas).not.toContain('petroleo-gas')
    expect(ofrecidas).not.toContain('cobertura-inflacion')
  })

  // --- F-079: financieras, tecnológicas y medicina migran de `rubroRv` inline a referenciar el
  // preset compartido de `lib/presetsRv.ts` — mismo `sic_oficina`, mismo conjunto de especies.

  it.each([
    ['financieras', 'Office of Finance'],
    ['tecnologicas', 'Office of Technology'],
    ['medicina', 'Office of Life Sciences'],
  ])('%s referencia el preset compartido "%s" por identidad, no lo duplica', (id, oficina) => {
    const tematica = presetPorId(id)
    const compartido = presetRvPorId(id)

    expect(compartido?.filtro).toEqual({ rubros: [oficina] })
    // Identidad, no igualdad estructural: si alguien duplicara la definición acá, el monitor y el
    // armador podrían empezar a decir cosas distintas sobre qué oficina define la temática.
    expect(tematica?.filtroRv).toBe(compartido?.filtro)
    expect(tematica?.modoFiltroRv).toBe(compartido?.modo)
    expect(tematica?.rubroRv).toBeNull()
  })
})

describe('filtrosDelPreset', () => {
  it('parte de todo limpio, para que el resultado no dependa de lo que estaba activo antes', () => {
    const petroleoGas = presetPorId('petroleo-gas')!
    const filtros = filtrosDelPreset(petroleoGas)

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
    const petroleoGas = presetPorId('petroleo-gas')!

    expect(coincideConPreset(filtrosDelPreset(petroleoGas), petroleoGas)).toBe(true)
  })

  it('deja de coincidir apenas se toca un filtro a mano', () => {
    const petroleoGas = presetPorId('petroleo-gas')!
    const tocado = { ...filtrosDelPreset(petroleoGas), tirMin: '8' }

    expect(coincideConPreset(tocado, petroleoGas)).toBe(false)
  })

  it('no coincide con los filtros de otro preset', () => {
    const petroleoGas = presetPorId('petroleo-gas')!
    const financieras = presetPorId('financieras')!

    expect(coincideConPreset(filtrosDelPreset(financieras), petroleoGas)).toBe(false)
  })
})

describe('presetPorId', () => {
  it('devuelve null para un id que no existe, en vez de tirar', () => {
    expect(presetPorId('no-existe')).toBeNull()
    expect(presetPorId(null)).toBeNull()
  })
})
