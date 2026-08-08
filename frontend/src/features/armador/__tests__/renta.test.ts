/**
 * El motor de F-021, aislado: sin red, sin store, sin React — mismo criterio que
 * `resolver.test.ts`. Los GWT de la spec (`plan.md`, Bloque G) se cubren acá a nivel de cálculo
 * puro; la vuelta completa por la pantalla vive en `PanelRenta.test.tsx`.
 */

import { describe, expect, it } from 'vitest'

import {
  calcularRentaAnualPorMoneda,
  columnasDeCordillera,
  invertidoPorMoneda,
  picoDeColumnas,
} from '../lib/renta'
import type { InstrumentoDelMes, MesDelCalendario } from '../lib/schema'

function instrumento(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    fechas: ['2026-09-09'],
    pct_renta: 0.01,
    pct_amortizacion: 0,
    renta: 100,
    amortizacion: null,
    moneda: 'usd',
    rendimiento: 0.11,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    vencimiento: '2030-07-09',
    ...extra,
  }
}

function mes(extra: Partial<MesDelCalendario> = {}): MesDelCalendario {
  return {
    anio: 2026,
    mes: 9,
    etiqueta: '09/2026',
    nombre: 'Septiembre 2026',
    con_renta: 0,
    con_amortizacion: 0,
    sin_renta: true,
    renta: null,
    amortizacion: null,
    instrumentos: [],
    ...extra,
  }
}

/** Doce meses vacíos, para no repetir el boilerplate en cada test que sólo necesita completar
 *  algunos meses puntuales. */
function docesMeses(sobrescribir: Record<number, Partial<MesDelCalendario>> = {}): MesDelCalendario[] {
  return Array.from({ length: 12 }, (_, indice) =>
    mes({ etiqueta: `${String(indice + 1).padStart(2, '0')}/2026`, nombre: `Mes ${indice + 1}`, ...sobrescribir[indice] }),
  )
}

describe('columnasDeCordillera', () => {
  it('filtra los instrumentos por moneda de cobro: un mes con dólares y pesos no mezcla las dos barras', () => {
    const meses = docesMeses({
      2: {
        renta: { usd: 100, ars: 50000 },
        instrumentos: [
          instrumento({ ticker: 'AL30', moneda: 'usd', renta: 100 }),
          instrumento({ ticker: 'TX26', moneda: 'ars', renta: 50000 }),
        ],
      },
    })

    const usd = columnasDeCordillera(meses, 'usd')
    expect(usd[2].total).toBe(100)
    expect(usd[2].segmentos).toEqual([{ ticker: 'AL30', monto: 100 }])

    const ars = columnasDeCordillera(meses, 'ars')
    expect(ars[2].total).toBe(50000)
    expect(ars[2].segmentos).toEqual([{ ticker: 'TX26', monto: 50000 }])
  })

  it('un mes sin renta en esa moneda queda en cero explícito, con cero segmentos', () => {
    const meses = docesMeses()
    const usd = columnasDeCordillera(meses, 'usd')
    expect(usd.every((c) => c.total === 0 && c.segmentos.length === 0)).toBe(true)
  })

  it('la suma de los segmentos de un mes es igual al total del mes, por construcción', () => {
    const meses = docesMeses({
      5: {
        renta: { usd: 300 },
        instrumentos: [
          instrumento({ ticker: 'AL30', moneda: 'usd', renta: 120 }),
          instrumento({ ticker: 'GD30', moneda: 'usd', renta: 180 }),
        ],
      },
    })
    const [columna] = columnasDeCordillera(meses, 'usd').slice(5, 6)
    const sumaSegmentos = columna.segmentos.reduce((acc, s) => acc + s.monto, 0)
    expect(sumaSegmentos).toBe(columna.total)
  })

  it('trae la amortización del mes en esa moneda, aparte de la renta', () => {
    const meses = docesMeses({ 0: { amortizacion: { usd: 250 } } })
    const usd = columnasDeCordillera(meses, 'usd')
    expect(usd[0].amortizacion).toBe(250)
  })
})

describe('picoDeColumnas', () => {
  it('es el mayor total entre las doce columnas', () => {
    const meses = docesMeses({ 1: { renta: { usd: 50 } }, 7: { renta: { usd: 300 } } })
    const columnas = columnasDeCordillera(meses, 'usd')
    expect(picoDeColumnas(columnas)).toBe(300)
  })

  it('es 0 cuando ningún mes cobra nada en esa moneda — cordillera plana, no un error', () => {
    expect(picoDeColumnas(columnasDeCordillera(docesMeses(), 'usd'))).toBe(0)
  })
})

describe('invertidoPorMoneda', () => {
  it('suma el invertido de las posiciones según la moneda de cobro que declara el calendario', () => {
    const meses = docesMeses({
      0: {
        instrumentos: [instrumento({ ticker: 'AL30', moneda: 'usd' }), instrumento({ ticker: 'TX26', moneda: 'ars' })],
      },
    })
    const totales = invertidoPorMoneda(meses, [
      { ticker: 'AL30', invertido: 1000 },
      { ticker: 'TX26', invertido: 200000 },
    ])
    expect(totales).toEqual({ usd: 1000, ars: 200000 })
  })

  it('ignora las posiciones sin invertido resuelto y las que no aparecen en ningún mes del calendario', () => {
    const meses = docesMeses({ 0: { instrumentos: [instrumento({ ticker: 'AL30', moneda: 'usd' })] } })
    const totales = invertidoPorMoneda(meses, [
      { ticker: 'AL30', invertido: null },
      // FUERA_DEL_UNIVERSO: no se le adivina la moneda, no aporta a ningún total.
      { ticker: 'DESCONOCIDO', invertido: 500 },
    ])
    expect(totales).toEqual({})
  })
})

// --- GWT de la spec (plan.md, F-021) ---------------------------------------------------------

describe('calcularRentaAnualPorMoneda', () => {
  it('GWT: US$ 99.999,11 invertidos que cobran US$ 7.173,92 de cupones dan 7,17 % con la cuenta expuesta', () => {
    const meses = docesMeses({ 3: { renta: { usd: 7173.92 } } })
    const [resultado] = calcularRentaAnualPorMoneda(meses, { usd: 7173.92 }, { usd: 99999.11 })

    expect(resultado.rentaAnual).toBeCloseTo(7173.92, 6)
    expect(resultado.invertido).toBeCloseTo(99999.11, 6)
    expect(resultado.pct).toBeCloseTo(7.174, 2) // → "7,17%" al formatear con dos decimales
  })

  it('GWT-5: la amortización nunca entra al numerador — sólo se lee `renta`, nunca `amortizacion`', () => {
    // Un mes con amortización pero renta 0 no debe sumar nada a `mesesCubiertos` ni a la renta.
    const meses = docesMeses({ 4: { renta: { usd: 0 }, amortizacion: { usd: 5000 } } })
    const [resultado] = calcularRentaAnualPorMoneda(meses, { usd: 0 }, { usd: 10000 })

    expect(resultado.rentaAnual).toBe(0)
    expect(resultado.mesesCubiertos).toBe(0)
    expect(resultado.serie[4].monto).toBe(0)
  })

  it('sin ninguna posición resuelta que cobre en esa moneda, el denominador y el % quedan en null, no en 0', () => {
    const meses = docesMeses({ 0: { renta: { usd: 500 } } })
    const [resultado] = calcularRentaAnualPorMoneda(meses, { usd: 500 }, {})

    expect(resultado.invertido).toBeNull()
    expect(resultado.pct).toBeNull()
  })

  it('con renta anual 0, "parejo" queda en null: la fórmula divide por la renta anual', () => {
    const meses = docesMeses()
    const [resultado] = calcularRentaAnualPorMoneda(meses, { usd: 0 }, { usd: 1000 })
    expect(resultado.parejo).toBeNull()
  })

  it('mesesCubiertos cuenta los meses con renta > 0, y "parejo" da 1 cuando los doce meses cobran lo mismo', () => {
    const parejo = docesMeses({}).map((m, i) => ({ ...m, renta: { usd: 120 }, etiqueta: `${i}` }))
    const [resultado] = calcularRentaAnualPorMoneda(parejo, { usd: 1440 }, { usd: 10000 })

    expect(resultado.mesesCubiertos).toBe(12)
    expect(resultado.parejo).toBeCloseTo(1, 6)
  })

  it('identifica el mes más flaco y el más fuerte de la serie', () => {
    const meses = docesMeses({ 0: { renta: { usd: 10 } }, 6: { renta: { usd: 900 } } })
    const [resultado] = calcularRentaAnualPorMoneda(meses, { usd: 910 }, { usd: 10000 })

    // El mínimo es 0 y hay diez meses empatados en 0; se queda con el primero que encuentra
    // recorriendo la serie en orden — el mes 0 (US$ 10) no es el mínimo, así que no lo gana.
    expect(resultado.mesMasFlaco?.indice).toBe(1)
    expect(resultado.mesMasFlaco?.monto).toBe(0)
    expect(resultado.mesMasFuerte?.indice).toBe(6)
    expect(resultado.mesMasFuerte?.monto).toBe(900)
  })

  it('arma una tarjeta por cada moneda de `rentaAnual`, sin mezclarlas', () => {
    const meses = docesMeses({ 0: { renta: { usd: 100, ars: 50000 } } })
    const resultados = calcularRentaAnualPorMoneda(meses, { usd: 100, ars: 50000 }, { usd: 1000, ars: 500000 })

    expect(resultados).toHaveLength(2)
    expect(resultados.map((r) => r.moneda).sort()).toEqual(['ars', 'usd'])
  })
})
