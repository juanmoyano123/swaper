import { describe, expect, it } from 'vitest'

import { intentarMapeoAutomatico, mapeoCompleto, mapeoVacio } from '../lib/mapeoColumnas'

describe('intentarMapeoAutomatico', () => {
  it('reconoce encabezados conocidos sin importar el orden', () => {
    expect(intentarMapeoAutomatico(['Nominal', 'Especie', 'Monto'])).toEqual(['nominal', 'ticker', 'monto'])
  })

  it('reconoce variantes y mayúsculas/acentos', () => {
    expect(intentarMapeoAutomatico(['Símbolo', 'Cantidad'])).toEqual(['ticker', 'nominal'])
    expect(intentarMapeoAutomatico(['TICKER', 'IMPORTE'])).toEqual(['ticker', 'monto'])
  })

  it('devuelve null cuando no hay ni ticker ni columna numérica reconocibles', () => {
    expect(intentarMapeoAutomatico(['Columna A', 'Columna B'])).toBeNull()
  })

  it('devuelve null si solo se reconoce el ticker pero ninguna columna numérica', () => {
    expect(intentarMapeoAutomatico(['Especie', 'Observaciones'])).toBeNull()
  })

  it('marca como "ignorar" las columnas que no matchean ningún sinónimo', () => {
    expect(intentarMapeoAutomatico(['Especie', 'Fecha', 'Nominal'])).toEqual(['ticker', 'ignorar', 'nominal'])
  })
})

describe('mapeoVacio', () => {
  it('produce un mapeo del tamaño pedido, todo sin asignar', () => {
    expect(mapeoVacio(3)).toEqual(['ignorar', 'ignorar', 'ignorar'])
  })
})

describe('mapeoCompleto', () => {
  it('es válido con un ticker y un nominal', () => {
    expect(mapeoCompleto(['ticker', 'nominal', 'ignorar'])).toBe(true)
  })

  it('es válido con un ticker y un monto, sin nominal', () => {
    expect(mapeoCompleto(['ticker', 'monto'])).toBe(true)
  })

  it('es inválido sin ticker', () => {
    expect(mapeoCompleto(['ignorar', 'nominal'])).toBe(false)
  })

  it('es inválido sin ninguna columna numérica', () => {
    expect(mapeoCompleto(['ticker', 'ignorar'])).toBe(false)
  })

  it('es inválido con dos columnas de ticker', () => {
    expect(mapeoCompleto(['ticker', 'ticker', 'nominal'])).toBe(false)
  })
})
