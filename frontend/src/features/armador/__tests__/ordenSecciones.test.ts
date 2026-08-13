/**
 * El orden de las secciones y su reconciliación contra el registro.
 *
 * Lo que más importa acá no es que el orden se guarde —eso es `localStorage`— sino que **ninguna
 * sección se pierda** al reconciliar contra un orden guardado por otra versión de la app. Una
 * sección que no se renderiza es una función que desaparece sin aviso.
 */

import { describe, expect, it } from 'vitest'

import type { SeccionId } from '../lib/plegado'
import {
  guardarOrden,
  leerOrden,
  moverSeccion,
  olvidarOrden,
  ORDEN_DE_FABRICA,
  reconciliarOrden,
} from '../lib/ordenSecciones'

describe('reconciliarOrden', () => {
  it('respeta el orden guardado cuando nombra todas las secciones', () => {
    const guardado: SeccionId[] = ['rv', 'cartera', 'cordillera', 'asistido', 'calendario', 'analisis']
    expect(reconciliarOrden(guardado)).toEqual(guardado)
  })

  it('una sección que existe y no estaba guardada entra al final, nunca se pierde', () => {
    // El caso de agregar una sección nueva a una app que ya tenía orden guardado.
    const guardado = ['rv', 'cartera']
    const reconciliado = reconciliarOrden(guardado)

    expect(reconciliado.slice(0, 2)).toEqual(['rv', 'cartera'])
    expect(new Set(reconciliado)).toEqual(new Set(ORDEN_DE_FABRICA))
  })

  it('descarta un id que ya no existe sin romper el resto', () => {
    // El caso de sacar una sección de una app que ya tenía orden guardado.
    const reconciliado = reconciliarOrden(['rv', 'seccion-que-ya-no-existe', 'cartera'])

    expect(reconciliado).not.toContain('seccion-que-ya-no-existe')
    expect(reconciliado.slice(0, 2)).toEqual(['rv', 'cartera'])
    expect(reconciliado).toHaveLength(ORDEN_DE_FABRICA.length)
  })

  it('un id repetido se cuenta una sola vez', () => {
    const reconciliado = reconciliarOrden(['rv', 'rv', 'cartera'])
    expect(reconciliado.filter((id) => id === 'rv')).toHaveLength(1)
    expect(reconciliado).toHaveLength(ORDEN_DE_FABRICA.length)
  })

  it('sin nada guardado devuelve el orden de fábrica', () => {
    expect(reconciliarOrden([])).toEqual([...ORDEN_DE_FABRICA])
  })
})

describe('moverSeccion', () => {
  it('sube una sección un lugar', () => {
    expect(moverSeccion(['a', 'b', 'c'] as SeccionId[], 'c' as SeccionId, 'arriba')).toEqual([
      'a',
      'c',
      'b',
    ])
  })

  it('baja una sección un lugar', () => {
    expect(moverSeccion(['a', 'b', 'c'] as SeccionId[], 'a' as SeccionId, 'abajo')).toEqual([
      'b',
      'a',
      'c',
    ])
  })

  it('subir la primera no hace nada, y no es un error', () => {
    const orden = ['a', 'b'] as SeccionId[]
    expect(moverSeccion(orden, 'a' as SeccionId, 'arriba')).toEqual(orden)
  })

  it('bajar la última no hace nada', () => {
    const orden = ['a', 'b'] as SeccionId[]
    expect(moverSeccion(orden, 'b' as SeccionId, 'abajo')).toEqual(orden)
  })

  it('no muta el array original', () => {
    const orden = ['a', 'b', 'c'] as SeccionId[]
    moverSeccion(orden, 'a' as SeccionId, 'abajo')
    expect(orden).toEqual(['a', 'b', 'c'])
  })

  it('un id que no está en el orden lo deja igual', () => {
    const orden = ['a', 'b'] as SeccionId[]
    expect(moverSeccion(orden, 'z' as SeccionId, 'arriba')).toEqual(orden)
  })
})

describe('leerOrden / guardarOrden', () => {
  it('sin nada guardado devuelve el orden de fábrica', () => {
    expect(leerOrden()).toEqual([...ORDEN_DE_FABRICA])
  })

  it('lo guardado sobrevive a la relectura', () => {
    const elegido: SeccionId[] = ['rv', 'asistido', 'cartera', 'cordillera', 'calendario', 'analisis']
    guardarOrden(elegido)
    expect(leerOrden()).toEqual(elegido)
  })

  it('olvidar el orden vuelve al de fábrica', () => {
    guardarOrden(['rv', 'cordillera'] as SeccionId[])
    olvidarOrden()
    expect(leerOrden()).toEqual([...ORDEN_DE_FABRICA])
  })

  it('un valor corrupto en localStorage no rompe: devuelve el orden de fábrica', () => {
    localStorage.setItem('swaper-armador-orden-v1', 'no es json')
    expect(leerOrden()).toEqual([...ORDEN_DE_FABRICA])
  })

  it('un JSON válido que no es lista tampoco rompe', () => {
    localStorage.setItem('swaper-armador-orden-v1', '{"rv":1}')
    expect(leerOrden()).toEqual([...ORDEN_DE_FABRICA])
  })
})
