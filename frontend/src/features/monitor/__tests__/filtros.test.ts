/**
 * Lógica pura de `../lib/filtros.ts` — facetado en cascada del universo (14/08/2026).
 */

import { describe, expect, it } from 'vitest'

import {
  CALIFICACION_NO_INFORMADA,
  FILTROS_VACIOS,
  LEY_NO_INFORMADA,
  facetarUniverso,
  pasaFiltros,
  type FiltrosUniverso,
} from '../lib/filtros'
import type { Especie } from '../lib/schema'

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.1,
    duracion: 2.5,
    vencimiento: '2030-07-09',
    ley: 'Ley Argentina',
    moneda_cupon: 'USD',
    emisor: 'Tesoro Nacional',
    precio: 62.5,
    moneda_cotizacion: 'USD',
    volumen: 1_000_000,
    volumen_usd: 1_000_000,
    paridad: 0.875,
    sector: 'Soberano',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    fuente: null,
    ...extra,
  }
}

/** Cuatro especies con perfiles cruzados: dos sectores, dos créditos, una sin ley y otra sin
 *  calificación. YPFD es la única que paga más de 10% de rendimiento. */
function universo(): Especie[] {
  return [
    especie({ ticker: 'AL30', sector: 'Soberano', emisor: 'Tesoro Nacional', clase_activo: 'bono_soberano', ley: 'Ley Argentina', calificacion: 'AAA(arg)', rendimiento: 0.08 }),
    especie({ ticker: 'YPFD', sector: 'O&G', emisor: 'YPF S.A.', clase_activo: 'on_corporativo', ley: 'Ley N.Y.', calificacion: null, rendimiento: 0.12, moneda_cotizacion: 'USD' }),
    especie({ ticker: 'PAMP', sector: 'O&G', emisor: 'Pampa Energía', clase_activo: 'on_corporativo', ley: null, calificacion: 'AA(arg)', rendimiento: 0.09, moneda_cotizacion: 'ARS' }),
    especie({ ticker: 'BYMA', sector: 'Financiera', emisor: 'Banco Galicia', clase_activo: 'on_corporativo', ley: 'Ley Argentina', calificacion: 'AA(arg)', rendimiento: 0.07 }),
  ]
}

function facetar(parcial: Partial<FiltrosUniverso> = {}) {
  return facetarUniverso(universo(), { ...FILTROS_VACIOS, ...parcial })
}

describe('facetarUniverso', () => {
  it('sin filtros ofrece todo lo que hay', () => {
    const { opciones } = facetar()
    expect([...opciones.sectores].sort()).toEqual(['Financiera', 'O&G', 'Soberano'])
    expect([...opciones.emisores].sort()).toEqual(['Banco Galicia', 'Pampa Energía', 'Tesoro Nacional', 'YPF S.A.'])
    expect(opciones.tieneLeyNoInformada).toBe(true)
    expect(opciones.tieneCalificacionNoInformada).toBe(true)
  })

  it('elegir sector deja sólo los emisores de ese sector', () => {
    const { opciones } = facetar({ sector: 'O&G' })
    expect([...opciones.emisores].sort()).toEqual(['Pampa Energía', 'YPF S.A.'])
  })

  it('y la inversa: elegir emisor deja sólo su sector', () => {
    const { opciones } = facetar({ emisor: 'YPF S.A.' })
    expect(opciones.sectores).toEqual(['O&G'])
  })

  it('el select propio no se acota a sí mismo', () => {
    const { opciones } = facetar({ sector: 'O&G' })
    expect([...opciones.sectores].sort()).toEqual(['Financiera', 'O&G', 'Soberano'])
  })

  it('un umbral numérico también acota las dimensiones discretas', () => {
    const { opciones } = facetar({ rendimientoMin: '10' })
    expect(opciones.sectores).toEqual(['O&G'])
    expect(opciones.emisores).toEqual(['YPF S.A.'])
  })

  it('crédito y moneda son facetas: crédito acota sector y viceversa', () => {
    const { opciones } = facetar({ credito: 'bono_soberano' })
    expect(opciones.sectores).toEqual(['Soberano'])
  })

  it('una selección sin respaldo se apaga, se declara, y no envenena las demás', () => {
    const { opciones, efectivos, apagadas } = facetar({ sector: 'Mineria' })
    expect(efectivos.sector).toBeNull()
    expect(apagadas).toEqual([{ dimension: 'sector', valor: 'Mineria' }])
    expect([...opciones.emisores].sort()).toEqual(['Banco Galicia', 'Pampa Energía', 'Tesoro Nacional', 'YPF S.A.'])
  })

  it('conflicto entre dos dimensiones: gana la que va antes en el orden', () => {
    // El orden es crédito → moneda → ley → sector → calificaciones → emisor: sector gana sobre
    // emisor cuando no pueden convivir.
    const { efectivos, apagadas } = facetar({ sector: 'Soberano', emisor: 'YPF S.A.' })
    expect(efectivos.sector).toBe('Soberano')
    expect(efectivos.emisor).toBeNull()
    expect(apagadas).toEqual([{ dimension: 'emisor', valor: 'YPF S.A.' }])
  })

  it('ley no informada se ofrece y se filtra igual que una ley concreta', () => {
    const { opciones } = facetar({ ley: LEY_NO_INFORMADA })
    expect(opciones.sectores).toEqual(['O&G']) // sólo PAMP no declara ley
  })

  it('calificaciones es un multiselect: sobreviven los valores con respaldo', () => {
    const { efectivos } = facetar({ sector: 'O&G', calificaciones: ['AA(arg)', 'AAA(arg)'] })
    // Bajo O&G sólo PAMP tiene AA(arg); AAA(arg) es de AL30 (Soberano) y no tiene respaldo acá.
    expect(efectivos.calificaciones).toEqual(['AA(arg)'])
  })

  it(`"${CALIFICACION_NO_INFORMADA}" filtra igual que un valor concreto`, () => {
    const { opciones } = facetar({ calificaciones: [CALIFICACION_NO_INFORMADA] })
    expect(opciones.emisores).toEqual(['YPF S.A.']) // sólo YPFD no declara calificación
  })
})

describe('pasaFiltros', () => {
  it('campo null contra filtro activo no pasa; sin ese filtro, se muestra igual', () => {
    const pamp = universo()[2] // ley: null
    expect(pasaFiltros(pamp, { ...FILTROS_VACIOS, ley: 'Ley Argentina' })).toBe(false)
    expect(pasaFiltros(pamp, FILTROS_VACIOS)).toBe(true)
  })

  it('nunca filtra "todas mezcladas": sin moneda elegida, cualquier moneda pasa', () => {
    const [al30] = universo()
    expect(pasaFiltros(al30, { ...FILTROS_VACIOS, moneda: null })).toBe(true)
    expect(pasaFiltros(al30, { ...FILTROS_VACIOS, moneda: 'ARS' })).toBe(false)
  })
})
