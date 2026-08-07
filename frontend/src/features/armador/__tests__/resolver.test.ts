/**
 * El motor `resolver`, aislado: sin red, sin store, sin React. Los cuatro GWT de F-018 se cubren
 * acá a nivel de cálculo puro; la vuelta completa por la pantalla vive en `CarteraEditable.test.tsx`
 * y la mecánica del store (pesos que no se tocan, equiponderar) en `carteraStore.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import { resolver, resumenAjuste, type EntradaResolver } from '../lib/resolver'

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
    const resueltas = resolver([entrada({ lamina: null })], 1000, null)
    const [resuelta] = resueltas

    // 500 / 1.05 exacto, sin redondeo a lámina.
    expect(resuelta.vn).toBeCloseTo(476.190476, 5)
    expect(resuelta.laminaConocida).toBe(false)

    // F-024: sin lámina en la única posición ajustable, no hay total ajustado que declarar.
    const resumen = resumenAjuste(resueltas)
    expect(resumen.sinLamina).toBe(1)
    expect(resumen.totalAjustadoUsd).toBeNull()
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

// --- F-024: resumenAjuste, el redondeo por lámina y su declaración de cobertura ------------------

describe('F-024 GWT-1: peso pedido al 16,5% con lámina informada', () => {
  it('redondea al múltiplo de la lámina, y peso pedido y peso real viajan los dos y difieren', () => {
    // objetivo = 10.000 * 16,5 / 100 = 1.650 USD; a 105 cada 100 VN, 1.650 / 1,05 = 1.571,43 VN.
    // floor a múltiplo de 100 → 1.500 (nunca 1.600, que redondearía para arriba).
    const [resuelta] = resolver([entrada({ peso: 16.5, lamina: 100 })], 10_000, null)

    expect(resuelta.vn).toBe(1500)
    expect(resuelta.laminaConocida).toBe(true)
    expect(resuelta.peso).toBe(16.5)
    // Única posición de la cartera: su peso real es 100%, y por eso difiere del 16,5% pedido — la
    // pantalla no los hace coincidir.
    expect(resuelta.pesoReal).not.toBeCloseTo(16.5, 1)
  })
})

describe('F-024 GWT-3: cartera de siete posiciones, dos sin lámina', () => {
  it('resumenAjuste separa ajustables, sinLamina, totalAjustadoUsd y pctSinAjustar', () => {
    const conLamina = ['A1', 'A2', 'A3', 'A4', 'A5'].map((ticker) =>
      entrada({ ticker, peso: 10, precio: 100, lamina: 10 }),
    )
    const sinLaminaInformada = ['B1', 'B2'].map((ticker) =>
      entrada({ ticker, peso: 10, precio: 100, lamina: null }),
    )
    const resueltas = resolver([...conLamina, ...sinLaminaInformada], 10_000, null)
    const resumen = resumenAjuste(resueltas)

    expect(resumen.ajustables).toBe(7)
    expect(resumen.sinLamina).toBe(2)
    // Cada una de las cinco con lámina invierte exactamente 1.000 USD (sin remanente en este caso).
    expect(resumen.totalAjustadoUsd).toBeCloseTo(5000, 6)
    // Σ invertidoUsd = 7.000; las dos sin lámina son 1.000 cada una → 2.000/7.000 * 100.
    expect(resumen.pctSinAjustar).toBeCloseTo((2000 / 7000) * 100, 6)
  })
})

describe('F-024: el caso real de los 255 tickers sin lámina (823 curados − 568 con lámina)', () => {
  it('ninguna posición trae lámina: nada se redondea, sinLamina === ajustables, totalAjustadoUsd es null (no 0)', () => {
    const posiciones = ['AL30', 'GD30', 'AE38'].map((ticker) =>
      entrada({ ticker, peso: 33.3, precio: 100, lamina: null }),
    )
    const resueltas = resolver(posiciones, 10_000, null)
    const resumen = resumenAjuste(resueltas)

    expect(resumen.sinLamina).toBe(resumen.ajustables)
    expect(resumen.totalAjustadoUsd).toBeNull()
    expect(resumen.pctSinAjustar).toBeCloseTo(100, 6)
  })
})

describe('F-024: cero explicado, las dos puntas', () => {
  it('todas las posiciones con lámina informada: sinLamina y pctSinAjustar son cero, no null', () => {
    const posiciones = [
      entrada({ ticker: 'AL30', peso: 50, precio: 105, lamina: 100 }),
      entrada({ ticker: 'GD30', peso: 50, precio: 100, lamina: 100 }),
    ]
    const resumen = resumenAjuste(resolver(posiciones, 10_000, null))

    expect(resumen.sinLamina).toBe(0)
    expect(resumen.pctSinAjustar).toBe(0) // cero real, no un faltante
    expect(resumen.totalAjustadoUsd).not.toBeNull()
  })

  it('sólo FCI en la cartera: no cuenta como "lámina no informada"', () => {
    const resueltas = resolver(
      [entrada({ ticker: 'FCI-X', esFci: true, precio: null, lamina: null })],
      10_000,
      null,
    )
    const resumen = resumenAjuste(resueltas)

    expect(resumen.ajustables).toBe(0)
    expect(resumen.sinLamina).toBe(0)
    expect(resumen.totalAjustadoUsd).toBeNull()
  })
})

describe('F-024: posición sin lámina y además sin resolver', () => {
  it('cuenta en sinLamina, pero no aporta a pctSinAjustar porque su pesoReal es null', () => {
    const resueltas = resolver(
      [
        entrada({ ticker: 'AL30', peso: 50, precio: 105, lamina: 100 }),
        entrada({ ticker: 'GD30', peso: 50, precio: null, lamina: null }), // sin precio: sin resolver
      ],
      10_000,
      null,
    )
    const resumen = resumenAjuste(resueltas)
    const gd30 = resueltas.find((r) => r.ticker === 'GD30')!

    expect(resumen.sinLamina).toBe(1)
    expect(gd30.pesoReal).toBeNull()
    // AL30 sí se resolvió, así que hay cartera medible sobre la que declarar el 0 — no es null.
    expect(resumen.pctSinAjustar).toBe(0)
  })
})
