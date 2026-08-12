import { describe, expect, it } from 'vitest'

import { parseCsv, parsePegado } from '../lib/parseTabla'

describe('parsePegado', () => {
  it('separa por tabulador, el formato más común al copiar de una tabla', () => {
    const texto = 'AL30D\t1200\nGD35\t850,50'
    expect(parsePegado(texto)).toEqual([
      ['AL30D', '1200'],
      ['GD35', '850,50'],
    ])
  })

  it('separa por punto y coma cuando no hay tabuladores', () => {
    const texto = 'Ticker;Nominal\nAL30D;1200\nGD35;850,50'
    expect(parsePegado(texto)).toEqual([
      ['Ticker', 'Nominal'],
      ['AL30D', '1200'],
      ['GD35', '850,50'],
    ])
  })

  it('no confunde la coma decimal con un separador de columnas', () => {
    const texto = 'AL30D\t1.200,50\nGD35\t850,00'
    const filas = parsePegado(texto)
    expect(filas[0]).toEqual(['AL30D', '1.200,50'])
    expect(filas[1]).toEqual(['GD35', '850,00'])
  })

  it('cae a espacios múltiples cuando el texto viene alineado a mano', () => {
    const texto = 'AL30D      1200\nGD35       850,50'
    expect(parsePegado(texto)).toEqual([
      ['AL30D', '1200'],
      ['GD35', '850,50'],
    ])
  })

  it('descarta líneas vacías', () => {
    const texto = 'AL30D\t1200\n\nGD35\t850,50\n'
    expect(parsePegado(texto)).toHaveLength(2)
  })

  it('devuelve una lista vacía para texto vacío', () => {
    expect(parsePegado('')).toEqual([])
    expect(parsePegado('   \n  ')).toEqual([])
  })
})

describe('parseCsv', () => {
  it('separa por coma en un CSV estándar', () => {
    const texto = 'Especie,Nominal\nAL30D,1200\nGD35,850.50'
    expect(parseCsv(texto)).toEqual([
      ['Especie', 'Nominal'],
      ['AL30D', '1200'],
      ['GD35', '850.50'],
    ])
  })

  it('separa por punto y coma cuando la muestra tiene más de esos', () => {
    const texto = 'Especie;Nominal\nAL30D;1.200,50'
    expect(parseCsv(texto)).toEqual([
      ['Especie', 'Nominal'],
      ['AL30D', '1.200,50'],
    ])
  })

  it('respeta comillas: una coma adentro de comillas no separa columnas', () => {
    const texto = 'Especie,Emisor,Nominal\nAL30D,"Argentina, República",1200'
    expect(parseCsv(texto)).toEqual([
      ['Especie', 'Emisor', 'Nominal'],
      ['AL30D', 'Argentina, República', '1200'],
    ])
  })
})
