import { describe, expect, it } from 'vitest'

import { parseNumeroArg } from '../lib/parseNumero'

describe('parseNumeroArg', () => {
  it('interpreta coma decimal, formato argentino', () => {
    expect(parseNumeroArg('850,50')).toBe(850.5)
  })

  it('interpreta punto de miles y coma decimal juntos', () => {
    expect(parseNumeroArg('1.234.567,89')).toBe(1234567.89)
  })

  it('interpreta punto de miles solo, sin decimales', () => {
    expect(parseNumeroArg('3.000')).toBe(3000)
  })

  it('interpreta punto decimal cuando no hay tres dígitos después', () => {
    expect(parseNumeroArg('1234.5')).toBe(1234.5)
    expect(parseNumeroArg('1234.56')).toBe(1234.56)
  })

  it('interpreta formato en-US (coma de miles, punto decimal)', () => {
    expect(parseNumeroArg('1,234,567.89')).toBe(1234567.89)
  })

  it('interpreta un entero sin separadores', () => {
    expect(parseNumeroArg('1200')).toBe(1200)
  })

  it('descarta el símbolo de moneda', () => {
    expect(parseNumeroArg('US$ 1.200,50')).toBe(1200.5)
    expect(parseNumeroArg('$1200')).toBe(1200)
  })

  it('interpreta negativos, incluido el formato contable entre paréntesis', () => {
    expect(parseNumeroArg('-500,25')).toBe(-500.25)
    expect(parseNumeroArg('(500,25)')).toBe(-500.25)
  })

  it('devuelve null para texto que no es un número', () => {
    expect(parseNumeroArg('ABC')).toBeNull()
    expect(parseNumeroArg('1200x')).toBeNull()
    expect(parseNumeroArg('')).toBeNull()
    expect(parseNumeroArg('   ')).toBeNull()
  })
})
