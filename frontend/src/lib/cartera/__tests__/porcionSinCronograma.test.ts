import { describe, expect, it } from 'vitest'

import { porcionSinCronograma, type PosicionParaPorcion } from '../porcionSinCronograma'

function pos(overrides: Partial<PosicionParaPorcion> = {}): PosicionParaPorcion {
  return { esFci: false, invertidoUsd: 1000, ...overrides }
}

describe('porcionSinCronograma', () => {
  it('suma sólo el invertido de las posiciones FCI, sobre el total de la cartera', () => {
    const resultado = porcionSinCronograma(
      [pos({ esFci: false, invertidoUsd: 700 }), pos({ esFci: true, invertidoUsd: 300 })],
      1000,
    )

    expect(resultado.montoFciUsd).toBe(300)
    expect(resultado.pctFci).toBeCloseTo(30, 6)
    expect(resultado.cantidadFci).toBe(1)
  })

  it('sin ningún FCI en la cartera, el monto es 0 explícito y no un dato faltante', () => {
    const resultado = porcionSinCronograma([pos({ esFci: false, invertidoUsd: 1000 })], 1000)

    expect(resultado.montoFciUsd).toBe(0)
    expect(resultado.pctFci).toBe(0)
    expect(resultado.cantidadFci).toBe(0)
  })

  it('un FCI sin resolver no aporta monto, pero sigue contando en cantidadFci', () => {
    const resultado = porcionSinCronograma(
      [pos({ esFci: false, invertidoUsd: 700 }), pos({ esFci: true, invertidoUsd: null })],
      700,
    )

    expect(resultado.montoFciUsd).toBe(0)
    expect(resultado.cantidadFci).toBe(1)
  })

  it('sin total invertido, el porcentaje es null y no cero', () => {
    const resultado = porcionSinCronograma([pos({ esFci: true, invertidoUsd: 100 })], 0)

    expect(resultado.pctFci).toBeNull()
  })

  it('cartera 100% en FCI: el porcentaje da 100, no se corta artificialmente', () => {
    const resultado = porcionSinCronograma([pos({ esFci: true, invertidoUsd: 500 })], 500)

    expect(resultado.pctFci).toBeCloseTo(100, 6)
  })
})
