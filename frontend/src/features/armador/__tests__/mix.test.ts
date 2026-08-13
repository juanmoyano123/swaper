import { describe, expect, it } from 'vitest'

import type { PosicionArmador } from '../store/carteraStore'
import { desvioContraObjetivo, mixPedido, objetivoMix, sumaPesos } from '../lib/mix'

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

describe('objetivoMix', () => {
  it('abre el objetivo en sus dos lados', () => {
    expect(objetivoMix(30)).toEqual({ rf: 70, rv: 30 })
  })

  it('sin objetivo declarado devuelve null, no un mix en cero', () => {
    expect(objetivoMix(null)).toBeNull()
  })

  it('un objetivo de 0 en renta variable es un mandato, no una ausencia', () => {
    expect(objetivoMix(0)).toEqual({ rf: 100, rv: 0 })
  })
})

describe('desvioContraObjetivo', () => {
  it('sin objetivo declarado no hay desvío que reportar', () => {
    expect(desvioContraObjetivo(null, { rf: 90, rv: 10 })).toBeNull()
  })

  it('la cartera que cumple el objetivo no queda fuera de tolerancia', () => {
    const d = desvioContraObjetivo(30, { rf: 70, rv: 30 })
    expect(d?.desvioRv).toBe(0)
    expect(d?.fueraDeTolerancia).toBe(false)
  })

  it('marca de más cuando sobra renta variable', () => {
    const d = desvioContraObjetivo(30, { rf: 60, rv: 40 })
    expect(d?.desvioRv).toBe(10)
    expect(d?.fueraDeTolerancia).toBe(true)
  })

  it('marca de menos cuando falta renta variable, con signo negativo', () => {
    const d = desvioContraObjetivo(30, { rf: 85, rv: 15 })
    expect(d?.desvioRv).toBe(-15)
    expect(d?.fueraDeTolerancia).toBe(true)
  })

  it('el redondeo de pesos a un decimal no dispara el aviso', () => {
    // `normalizarA100` reparte el residuo y deja diferencias de décimas: marcarlas sería gritar
    // por la aritmética de la propia pantalla.
    const d = desvioContraObjetivo(30, { rf: 69.7, rv: 30.3 })
    expect(d?.fueraDeTolerancia).toBe(false)
  })

  it('conserva objetivo y logrado para que la pantalla muestre los dos', () => {
    const d = desvioContraObjetivo(25, { rf: 80, rv: 20 })
    expect(d?.objetivo).toEqual({ rf: 75, rv: 25 })
    expect(d?.logrado).toEqual({ rf: 80, rv: 20 })
  })
})
