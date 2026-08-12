import { describe, expect, it } from 'vitest'

import type { PosicionArmador } from '../store/carteraStore'
import { mixPedido, sumaPesos } from '../lib/mix'

function pos(peso: number, clase: PosicionArmador['clase'] = 'renta_fija'): PosicionArmador {
  return { ticker: `T${peso}`, peso, clase }
}

describe('sumaPesos', () => {
  it('suma el peso de una lista vacía como 0', () => {
    expect(sumaPesos([])).toBe(0)
  })

  it('suma el peso pedido de todas las posiciones, sin distinguir clase', () => {
    expect(sumaPesos([pos(30), pos(20, 'renta_variable'), pos(10, 'fci')])).toBe(60)
  })
})

describe('mixPedido', () => {
  it('separa renta fija (con FCI) de renta variable', () => {
    const mix = mixPedido([pos(40), pos(10, 'fci'), pos(50, 'renta_variable')])
    expect(mix).toEqual({ rf: 50, rv: 50 })
  })

  it('sin posiciones de renta variable, rv es 0 y no s/d', () => {
    expect(mixPedido([pos(100)])).toEqual({ rf: 100, rv: 0 })
  })

  it('cartera vacía: los dos en 0', () => {
    expect(mixPedido([])).toEqual({ rf: 0, rv: 0 })
  })
})
