import { describe, expect, it } from 'vitest'

import { nominalDesdeMonto } from '../lib/nominal'

describe('nominalDesdeMonto', () => {
  it('con lámina informada, redondea hacia abajo al múltiplo más cercano', () => {
    // 600 / (50/100) = 1200 nominal crudo; floor a la lámina de 1000 → 1000.
    expect(nominalDesdeMonto(600, 50, 1000)).toBe(1000)
  })

  it('nunca redondea hacia arriba, ni justo en el borde de un múltiplo', () => {
    // 999 unidades de nominal crudo con lámina 1000: no llega al múltiplo siguiente.
    expect(nominalDesdeMonto(499.5, 50, 1000)).toBe(0)
  })

  it('exacto en el múltiplo, no lo empuja al de abajo', () => {
    expect(nominalDesdeMonto(500, 50, 1000)).toBe(1000)
  })

  it('sin lámina informada, devuelve el nominal crudo sin redondear', () => {
    expect(nominalDesdeMonto(600, 50, null)).toBe(1200)
  })
})
