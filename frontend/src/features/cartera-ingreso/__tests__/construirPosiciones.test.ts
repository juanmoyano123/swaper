/**
 * Criterio 3: una fila con un valor no numérico en el nominal se marca inválida con el motivo, y
 * no se la descarta en silencio ni se la interpreta como cero.
 */

import { describe, expect, it } from 'vitest'

import { construirPosiciones } from '../lib/construirPosiciones'

const MAPEO_TICKER_NOMINAL = ['ticker', 'nominal'] as const

describe('construirPosiciones', () => {
  it('arma una posición válida a partir de una fila bien formada', () => {
    const [p] = construirPosiciones([['AL30D', '1.200,50']], [...MAPEO_TICKER_NOMINAL], 2)
    expect(p).toMatchObject({
      fila: 2,
      tickerDeclarado: 'AL30D',
      nominal: 1200.5,
      monto: null,
      valida: true,
      motivo: null,
    })
  })

  it('marca inválida una fila con nominal no numérico, sin descartarla ni ponerla en cero', () => {
    const [p] = construirPosiciones([['GD35', 'nsc']], [...MAPEO_TICKER_NOMINAL], 5)

    // No se descarta: sigue estando en la lista.
    expect(p).toBeDefined()
    // No se interpreta como cero.
    expect(p.nominal).toBeNull()
    expect(p.valida).toBe(false)
    // Trae el motivo, y el motivo cita el valor real que se recibió.
    expect(p.motivo).toContain('nsc')
    expect(p.motivo).toContain('no es un número')
    // El ticker declarado se conserva tal como vino.
    expect(p.tickerDeclarado).toBe('GD35')
  })

  it('nunca deriva ni modifica el ticker declarado', () => {
    const [p] = construirPosiciones([['  mr46o  ', '500']], [...MAPEO_TICKER_NOMINAL], 1)
    // Se recorta el espaciado accidental de la celda, pero no se toca mayúsculas ni sufijos.
    expect(p.tickerDeclarado).toBe('mr46o')
  })

  it('acepta que la fila traiga monto en vez de nominal', () => {
    const [p] = construirPosiciones([['AL30D', '', '15000']], ['ticker', 'nominal', 'monto'], 1)
    expect(p.valida).toBe(true)
    expect(p.nominal).toBeNull()
    expect(p.monto).toBe(15000)
  })

  it('marca inválida una fila sin ticker', () => {
    const [p] = construirPosiciones([['', '500']], [...MAPEO_TICKER_NOMINAL], 1)
    expect(p.valida).toBe(false)
    expect(p.motivo).toContain('falta el ticker')
  })

  it('marca inválida una fila sin nominal ni monto', () => {
    const [p] = construirPosiciones([['AL30D', '']], [...MAPEO_TICKER_NOMINAL], 1)
    expect(p.valida).toBe(false)
    expect(p.motivo).toContain('no trae nominal ni monto')
  })

  it('numera las filas con el offset recibido, para señalar la fila real de origen', () => {
    const filas = construirPosiciones(
      [
        ['AL30D', '100'],
        ['GD35', '200'],
      ],
      [...MAPEO_TICKER_NOMINAL],
      3,
    )
    expect(filas.map((f) => f.fila)).toEqual([3, 4])
  })
})
