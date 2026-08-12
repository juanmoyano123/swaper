/**
 * Agrupación de la cartera en bloques por clase de activo — Tanda 13.
 *
 * Lo que importa acá es el orden (es el del formato de la mesa) y qué pasa con lo que no encaja: un
 * ticker sin clase conocida tiene que quedar visible en su propio bloque, nunca repartido al que
 * más se le parece.
 */

import { describe, expect, it } from 'vitest'

import { agruparEnBloques, ORDEN_DE_BLOQUES } from '../lib/bloques'
import type { PosicionArmador } from '../store/carteraStore'

function rf(ticker: string, peso = 10): PosicionArmador {
  return { ticker, peso, clase: 'renta_fija' }
}

const CLASES: Record<string, string> = {
  AL30: 'bono_soberano',
  GD41: 'bono_soberano',
  BA37A: 'bono_subsoberano',
  YMCXO: 'on_corporativo',
  IRCPO: 'on_corporativo',
}

const claseDe = (ticker: string) => CLASES[ticker]

describe('agruparEnBloques', () => {
  it('separa soberanos de corporativos', () => {
    const bloques = agruparEnBloques([rf('AL30'), rf('YMCXO'), rf('GD41')], claseDe)

    expect(bloques.map((b) => b.id)).toEqual(['soberanos', 'corporativos'])
    expect(bloques[0].posiciones.map((p) => p.ticker)).toEqual(['AL30', 'GD41'])
    expect(bloques[1].posiciones.map((p) => p.ticker)).toEqual(['YMCXO'])
  })

  it('los subsoberanos van con los soberanos, como en el formato de la mesa', () => {
    const bloques = agruparEnBloques([rf('BA37A'), rf('AL30')], claseDe)

    expect(bloques).toHaveLength(1)
    expect(bloques[0].id).toBe('soberanos')
  })

  it('respeta el orden de bloques aunque las posiciones se hayan cargado al revés', () => {
    const posiciones = [
      { ticker: 'GGAL', peso: 20, clase: 'renta_variable' as const },
      { ticker: 'FCI Dólar', peso: 10, clase: 'fci' as const },
      rf('YMCXO'),
      rf('AL30'),
    ]
    const bloques = agruparEnBloques(posiciones, claseDe)

    expect(bloques.map((b) => b.id)).toEqual(['soberanos', 'corporativos', 'fci', 'renta_variable'])
  })

  it('suma el peso pedido de cada bloque', () => {
    const bloques = agruparEnBloques([rf('AL30', 30), rf('GD41', 25), rf('YMCXO', 45)], claseDe)

    expect(bloques[0].pesoPedido).toBe(55)
    expect(bloques[1].pesoPedido).toBe(45)
  })

  it('un ticker que no cruzó contra el universo queda visible en "sin clasificar"', () => {
    const bloques = agruparEnBloques([rf('AL30'), rf('DESCONOCIDO')], claseDe)

    expect(bloques.map((b) => b.id)).toEqual(['soberanos', 'sin_clasificar'])
    expect(bloques[1].posiciones.map((p) => p.ticker)).toEqual(['DESCONOCIDO'])
  })

  it('una clase de activo que no está en la tabla tampoco se reparte al bloque más parecido', () => {
    const bloques = agruparEnBloques([rf('RARO')], () => 'fideicomiso_financiero')

    expect(bloques).toHaveLength(1)
    expect(bloques[0].id).toBe('sin_clasificar')
  })

  it('la clase de la posición manda: un FCI es un FCI aunque cruce contra el universo', () => {
    const bloques = agruparEnBloques([{ ticker: 'AL30', peso: 10, clase: 'fci' }], claseDe)

    expect(bloques[0].id).toBe('fci')
  })

  it('no devuelve bloques vacíos: la cartera muestra sólo los que tienen algo', () => {
    const bloques = agruparEnBloques([rf('AL30')], claseDe)

    expect(bloques).toHaveLength(1)
    expect(bloques.length).toBeLessThan(ORDEN_DE_BLOQUES.length)
  })

  it('una cartera vacía no tiene bloques', () => {
    expect(agruparEnBloques([], claseDe)).toEqual([])
  })
})
