import { describe, expect, it } from 'vitest'

import { facetar, type Faceta } from '../facetado'

interface Item {
  id: string
  sector: string | null
  emisor: string | null
  rendimiento: number
}

function item(extra: Partial<Item> = {}): Item {
  return { id: 'x', sector: null, emisor: null, rendimiento: 0.1, ...extra }
}

/** Faceta de valor único (0 o 1 elementos en `seleccion`) sobre un campo `string | null`. */
function facetaDeCampo(
  id: 'sector' | 'emisor',
  seleccion: string[],
): Faceta<Item> {
  return {
    id,
    seleccion,
    coincide: (i, valor) => i[id] === valor,
    valores: (i) => (i[id] === null ? [] : [i[id]]),
  }
}

function pasaTodo() {
  return true
}

describe('facetar', () => {
  const ITEMS = [
    item({ id: 'a', sector: 'O&G', emisor: 'YPF' }),
    item({ id: 'b', sector: 'O&G', emisor: 'Vista' }),
    item({ id: 'c', sector: 'Financiera', emisor: 'Galicia' }),
  ]

  it('sin selección, las opciones son todos los valores distintos', () => {
    const { opciones } = facetar(ITEMS, [facetaDeCampo('sector', []), facetaDeCampo('emisor', [])], pasaTodo)
    expect([...opciones.get('sector')!].sort()).toEqual(['Financiera', 'O&G'])
    expect([...opciones.get('emisor')!].sort()).toEqual(['Galicia', 'Vista', 'YPF'])
  })

  it('elegir un valor acota las opciones de la otra dimensión', () => {
    const { opciones, efectivas } = facetar(
      ITEMS,
      [facetaDeCampo('sector', ['O&G']), facetaDeCampo('emisor', [])],
      pasaTodo,
    )
    expect([...opciones.get('emisor')!].sort()).toEqual(['Vista', 'YPF'])
    expect(efectivas.get('sector')).toEqual(['O&G'])
  })

  it('el select propio no se acota a sí mismo: conserva todas sus opciones', () => {
    const { opciones } = facetar(
      ITEMS,
      [facetaDeCampo('sector', ['O&G']), facetaDeCampo('emisor', [])],
      pasaTodo,
    )
    expect([...opciones.get('sector')!].sort()).toEqual(['Financiera', 'O&G'])
  })

  it('funciona en las dos direcciones: elegir emisor acota sector', () => {
    const { opciones } = facetar(
      ITEMS,
      [facetaDeCampo('sector', []), facetaDeCampo('emisor', ['Vista'])],
      pasaTodo,
    )
    expect(opciones.get('sector')).toEqual(['O&G'])
  })

  it('pasaBase es una fuente siempre efectiva: acota igual que una dimensión', () => {
    const pasaBase = (i: Item) => i.rendimiento >= 0.5
    const conAltoRendimiento = [...ITEMS, item({ id: 'd', sector: 'O&G', emisor: 'Pampa', rendimiento: 0.9 })]
    const { opciones } = facetar(
      conAltoRendimiento,
      [facetaDeCampo('sector', []), facetaDeCampo('emisor', [])],
      pasaBase,
    )
    expect(opciones.get('sector')).toEqual(['O&G'])
    expect(opciones.get('emisor')).toEqual(['Pampa'])
  })

  it('una selección sin respaldo se apaga, se declara, y no envenena a las demás', () => {
    const { opciones, efectivas, apagadas } = facetar(
      ITEMS,
      [facetaDeCampo('sector', ['Mineria']), facetaDeCampo('emisor', [])],
      pasaTodo,
    )
    expect(efectivas.get('sector')).toEqual([])
    expect(apagadas).toEqual([{ dimension: 'sector', valor: 'Mineria' }])
    // Sin el punto fijo por orden, el sector inexistente dejaría emisor vacío.
    expect([...opciones.get('emisor')!].sort()).toEqual(['Galicia', 'Vista', 'YPF'])
  })

  it('sin nada apagado, `apagadas` queda vacío', () => {
    const { apagadas } = facetar(ITEMS, [facetaDeCampo('sector', ['O&G']), facetaDeCampo('emisor', [])], pasaTodo)
    expect(apagadas).toEqual([])
  })

  it('el orden de las dimensiones decide qué gana ante un conflicto: la primera', () => {
    // Ningún ítem es a la vez sector Financiera y emisor YPF.
    const { efectivas, apagadas } = facetar(
      ITEMS,
      [facetaDeCampo('sector', ['Financiera']), facetaDeCampo('emisor', ['YPF'])],
      pasaTodo,
    )
    expect(efectivas.get('sector')).toEqual(['Financiera'])
    expect(efectivas.get('emisor')).toEqual([])
    expect(apagadas).toEqual([{ dimension: 'emisor', valor: 'YPF' }])
  })

  it('invertir el orden invierte quién gana', () => {
    const { efectivas, apagadas } = facetar(
      ITEMS,
      [facetaDeCampo('emisor', ['YPF']), facetaDeCampo('sector', ['Financiera'])],
      pasaTodo,
    )
    expect(efectivas.get('emisor')).toEqual(['YPF'])
    expect(efectivas.get('sector')).toEqual([])
    expect(apagadas).toEqual([{ dimension: 'sector', valor: 'Financiera' }])
  })

  it('un multiselect es una disyunción: sobreviven los valores con respaldo individual', () => {
    const facetaCalificacion: Faceta<Item> = {
      id: 'calificacion',
      seleccion: ['O&G', 'Mineria'], // reusa el campo sector como si fuera calificación, para el caso
      coincide: (i, valor) => i.sector === valor,
      valores: (i) => (i.sector === null ? [] : [i.sector]),
    }
    const { efectivas, apagadas } = facetar(ITEMS, [facetaCalificacion], pasaTodo)
    expect(efectivas.get('calificacion')).toEqual(['O&G'])
    expect(apagadas).toEqual([{ dimension: 'calificacion', valor: 'Mineria' }])
  })

  it('un ítem sin dato (null) no aporta opción y no coincide con ningún valor concreto', () => {
    const conSinDato = [...ITEMS, item({ id: 'd', sector: null, emisor: null })]
    const { opciones } = facetar(conSinDato, [facetaDeCampo('sector', []), facetaDeCampo('emisor', [])], pasaTodo)
    expect([...opciones.get('sector')!].sort()).toEqual(['Financiera', 'O&G'])
  })

  it('lista vacía de ítems no rompe: todo queda vacío', () => {
    const { opciones, efectivas, apagadas } = facetar(
      [],
      [facetaDeCampo('sector', ['O&G']), facetaDeCampo('emisor', [])],
      pasaTodo,
    )
    expect(opciones.get('sector')).toEqual([])
    expect(efectivas.get('sector')).toEqual([])
    expect(apagadas).toEqual([{ dimension: 'sector', valor: 'O&G' }])
  })
})
