/**
 * El motor `resolver`, aislado: sin red, sin store, sin React. Los cuatro GWT de F-018 se cubren
 * acá a nivel de cálculo puro; la vuelta completa por la pantalla vive en `CarteraEditable.test.tsx`
 * y la mecánica del store (pesos que no se tocan, equiponderar) en `carteraStore.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import { resolver, type EntradaResolver } from '../lib/resolver'

function entrada(extra: Partial<EntradaResolver> = {}): EntradaResolver {
  return {
    ticker: 'AL30',
    peso: 50,
    precio: 105,
    monedaCotizacion: 'usd',
    lamina: null,
    esFci: false,
    ...extra,
  }
}

describe('peso → VN con lámina conocida', () => {
  it('redondea siempre hacia abajo al múltiplo de la lámina, nunca hacia arriba', () => {
    // montoTotal 1000, peso 50 → objetivo 500 USD; a 105 cada 100 VN, 500/1.05 = 476,19 VN.
    // Con lámina 100: floor(4,7619) * 100 = 400, nunca 500 (que redondearía para arriba).
    const [resuelta] = resolver([entrada({ lamina: 100 })], 1000, null)

    expect(resuelta.vn).toBe(400)
    expect(resuelta.laminaConocida).toBe(true)
    expect(resuelta.invertido).toBeCloseTo(420, 6) // 400 * 105 / 100
    expect(resuelta.invertidoUsd).toBeCloseTo(420, 6)
  })
})

describe('sin lámina conocida', () => {
  it('no pisa a ningún múltiplo y declara la lámina como desconocida', () => {
    const [resuelta] = resolver([entrada({ lamina: null })], 1000, null)

    // 500 / 1.05 exacto, sin redondeo a lámina.
    expect(resuelta.vn).toBeCloseTo(476.190476, 5)
    expect(resuelta.laminaConocida).toBe(false)
  })
})

describe('FCI', () => {
  it('no participa del denominador de pesoReal de las demás posiciones (GWT-4)', () => {
    const resueltas = resolver(
      [
        entrada({ ticker: 'AL30', peso: 70, precio: 100 }),
        entrada({ ticker: 'FCI-X', peso: 30, esFci: true, precio: null }),
      ],
      1000,
      null,
    )

    const al30 = resueltas.find((r) => r.ticker === 'AL30')!
    const fci = resueltas.find((r) => r.ticker === 'FCI-X')!

    // Si el FCI entrara al denominador, pesoReal de AL30 sería menor a 100.
    expect(al30.pesoReal).toBeCloseTo(100, 6)
    expect(fci.vn).toBeNull()
    expect(fci.invertido).toBeNull()
    expect(fci.invertidoUsd).toBeNull()
    expect(fci.pesoReal).toBeNull()
    // El peso pedido de la línea de FCI sigue viajando: "suma al peso" (GWT-4).
    expect(fci.peso).toBe(30)
  })
})

describe('especie en ARS sin tipo de cambio', () => {
  it('no inventa un tipo de cambio externo: declara la posición sin resolver', () => {
    const [resuelta] = resolver([entrada({ monedaCotizacion: 'ars' })], 1000, null)

    expect(resuelta.vn).toBeNull()
    expect(resuelta.invertido).toBeNull()
    expect(resuelta.invertidoUsd).toBeNull()
    expect(resuelta.pesoReal).toBeNull()
  })

  it('con tipo de cambio disponible sí resuelve, normalizando a USD', () => {
    const [resuelta] = resolver([entrada({ monedaCotizacion: 'ars', precio: 1000 })], 1000, 1500)

    // objetivoUsd = 500; objetivo en ARS = 500 * 1500 = 750.000; vn = 750.000 / (1000/100) = 75.000
    expect(resuelta.vn).toBeCloseTo(75_000, 3)
    expect(resuelta.invertido).toBeCloseTo(750_000, 3) // en ARS, la moneda de cotización
    expect(resuelta.invertidoUsd).toBeCloseTo(500, 3) // normalizado de nuevo a USD
  })
})

describe('montoTotal en 0', () => {
  it('no hay objetivo que repartir: todo sale null', () => {
    const resueltas = resolver([entrada(), entrada({ ticker: 'GD30' })], 0, null)

    for (const r of resueltas) {
      expect(r.vn).toBeNull()
      expect(r.invertido).toBeNull()
      expect(r.invertidoUsd).toBeNull()
      expect(r.pesoReal).toBeNull()
    }
  })
})

// --- Los cuatro GWT de la spec, vistos desde el motor puro -------------------------------------

describe('GWT-1: cambiar el peso de una posición recalcula su monto', () => {
  it('el monto de la posición cambiada varía; las otras no se tocan', () => {
    const tres = [
      entrada({ ticker: 'AL30', peso: 33.3 }),
      entrada({ ticker: 'GD30', peso: 33.3, precio: 100 }),
      entrada({ ticker: 'AE38', peso: 33.4, precio: 100 }),
    ]
    const antes = resolver(tres, 1000, null)

    const conPesoCambiado = tres.map((p) => (p.ticker === 'AL30' ? { ...p, peso: 60 } : p))
    const despues = resolver(conPesoCambiado, 1000, null)

    expect(despues.find((r) => r.ticker === 'AL30')!.invertido).not.toBeCloseTo(
      antes.find((r) => r.ticker === 'AL30')!.invertido!,
      3,
    )
    expect(despues.find((r) => r.ticker === 'GD30')!.invertido).toBeCloseTo(
      antes.find((r) => r.ticker === 'GD30')!.invertido!,
      6,
    )
  })
})

describe('GWT-2: la suma de pesos pedidos no se normaliza', () => {
  it('resolver no toca el peso pedido de ninguna posición, sume lo que sume', () => {
    const posiciones = [
      entrada({ ticker: 'AL30', peso: 50 }),
      entrada({ ticker: 'GD30', peso: 47.4, precio: 100 }),
    ]
    const resueltas = resolver(posiciones, 1000, null)

    // Σ = 97,4: resolver devuelve cada `peso` tal cual llegó, no un valor normalizado a 100.
    const suma = resueltas.reduce((acc, r) => acc + r.peso, 0)
    expect(suma).toBeCloseTo(97.4, 6)
    expect(resueltas.find((r) => r.ticker === 'AL30')!.peso).toBe(50)
  })
})

describe('GWT-3: equiponderar iguala el peso pedido, no necesariamente el real', () => {
  it('con pesos pedidos iguales, la lámina puede seguir dejando el real distinto entre posiciones', () => {
    const equiponderadas = [
      entrada({ ticker: 'AL30', peso: 50, precio: 105, lamina: 100 }),
      entrada({ ticker: 'GD30', peso: 50, precio: 100, lamina: 100 }),
    ]
    // Con montoTotal chico, floor() a la lámina puede llevar el VN a 0 en las dos posiciones y
    // esconder la diferencia (0 y 0 "empatan"): 10.000 alcanza para que el redondeo de cada precio
    // deje un remanente distinto y sea visible.
    const resueltas = resolver(equiponderadas, 10_000, null)

    const al30 = resueltas.find((r) => r.ticker === 'AL30')!
    const gd30 = resueltas.find((r) => r.ticker === 'GD30')!

    expect(al30.peso).toBe(gd30.peso)
    expect(al30.pesoReal).not.toBeCloseTo(gd30.pesoReal!, 1)
  })
})

describe('GWT-4: FCI con peso y sin precio', () => {
  it('suma al peso, se declara sin precio, y no entra en el cálculo de renta ni rendimiento', () => {
    const [fci] = resolver([entrada({ ticker: 'FCI-Y', peso: 15, esFci: true, precio: null })], 1000, null)

    expect(fci.peso).toBe(15)
    expect(fci.vn).toBeNull()
    expect(fci.invertido).toBeNull()
    expect(fci.pesoReal).toBeNull()
  })
})
