/**
 * Lógica pura de `../lib/filtros.ts` — F-017.
 */

import { describe, expect, it } from 'vitest'

import {
  FILTROS_ARMADOR_VACIOS,
  LEY_NO_INFORMADA,
  contarPagosPorTicker,
  filtrarMeses,
  hayFiltrosActivos,
  pasaFiltros,
  percentilesDeLiquidez,
} from '../lib/filtros'
import type { Especie, InstrumentoDelMes, MesDelCalendario } from '../lib/schema'

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    sufijo_liquidacion: null,
    clase_activo: 'ON',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.1123,
    duracion: 3.2,
    vencimiento: '2030-07-09',
    ley: 'ARG',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 105,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: null,
    sector: 'Soberano',
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

function instrumento(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    fechas: ['2026-11-09'],
    pct_renta: 0.0075,
    pct_amortizacion: 0,
    renta: null,
    amortizacion: null,
    moneda: 'USD',
    rendimiento: 0.1123,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    vencimiento: '2030-07-09',
    ...extra,
  }
}

function mesVacio(indice: number): MesDelCalendario {
  return {
    anio: 2026,
    mes: indice + 1,
    etiqueta: `${String(indice + 1).padStart(2, '0')}/2026`,
    nombre: `Mes ${indice + 1}`,
    con_renta: 0,
    con_amortizacion: 0,
    sin_renta: true,
    renta: null,
    amortizacion: null,
    instrumentos: [],
  }
}

// --- hayFiltrosActivos -------------------------------------------------------------------------------

describe('hayFiltrosActivos', () => {
  it('es falso con FILTROS_ARMADOR_VACIOS', () => {
    expect(hayFiltrosActivos(FILTROS_ARMADOR_VACIOS)).toBe(false)
  })

  it('es verdadero si cualquier campo se aparta del vacío', () => {
    expect(hayFiltrosActivos({ ...FILTROS_ARMADOR_VACIOS, pagos: '2' })).toBe(true)
    expect(hayFiltrosActivos({ ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' })).toBe(true)
  })
})

// --- contarPagosPorTicker: sólo pct_renta > 0 ---------------------------------------------------------

describe('contarPagosPorTicker', () => {
  it('cuenta sólo los meses con pct_renta > 0, observados sobre la ventana', () => {
    const meses = [0, 1, 2].map(mesVacio)
    meses[0] = { ...meses[0], instrumentos: [instrumento({ ticker: 'AL30', pct_renta: 0.0075 })] }
    meses[1] = {
      ...meses[1],
      instrumentos: [
        instrumento({ ticker: 'AL30', pct_renta: 0 }), // amortiza pero no paga renta este mes
        instrumento({ ticker: 'GD30', pct_renta: 0.01 }),
      ],
    }
    meses[2] = { ...meses[2], instrumentos: [instrumento({ ticker: 'AL30', pct_renta: 0.0075 })] }

    const conteo = contarPagosPorTicker(meses)

    expect(conteo.get('AL30')).toBe(2) // meses 0 y 2, no el 1 (pct_renta: 0)
    expect(conteo.get('GD30')).toBe(1)
  })
})

// --- percentilesDeLiquidez: conjunto declarado, volumen_usd null afuera -------------------------------

describe('percentilesDeLiquidez', () => {
  it('calcula el percentil por rango sobre volumen_usd, dentro del conjunto pasado', () => {
    const especies = [
      especie({ ticker: 'BAJO', volumen_usd: 10 }),
      especie({ ticker: 'MEDIO', volumen_usd: 50 }),
      especie({ ticker: 'ALTO', volumen_usd: 100 }),
      especie({ ticker: 'TOPE', volumen_usd: 100 }),
    ]

    const percentiles = percentilesDeLiquidez(especies)

    expect(percentiles.get('BAJO')).toBe(25) // 1 de 4 <= 10
    expect(percentiles.get('MEDIO')).toBe(50) // 2 de 4 <= 50
    expect(percentiles.get('ALTO')).toBe(100) // 4 de 4 <= 100 (empate con TOPE)
    expect(percentiles.get('TOPE')).toBe(100)
  })

  it('deja afuera del conjunto (y sin entrada en el mapa) las especies con volumen_usd null', () => {
    const especies = [
      especie({ ticker: 'CON_DATO', volumen_usd: 10 }),
      especie({ ticker: 'SIN_DATO', volumen_usd: null }),
    ]

    const percentiles = percentilesDeLiquidez(especies)

    expect(percentiles.has('SIN_DATO')).toBe(false)
    // El conjunto declarado es sólo CON_DATO: único elemento, percentil 100.
    expect(percentiles.get('CON_DATO')).toBe(100)
  })
})

// --- pasaFiltros: null contra filtro activo no pasa; sin filtro sí -------------------------------------

describe('pasaFiltros', () => {
  it('sin filtros activos, cualquier dato con cruce pasa', () => {
    const pasa = pasaFiltros(
      { especie: especie(), pagos: 3, percentil: 50 },
      FILTROS_ARMADOR_VACIOS,
    )
    expect(pasa).toBe(true)
  })

  it('duración: especie sin dato no pasa un filtro activo, pero sin filtro se muestra igual', () => {
    const sinDuracion = especie({ duracion: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, duracionMax: '5' }

    expect(pasaFiltros({ especie: sinDuracion, pagos: 1, percentil: 50 }, filtros)).toBe(false)
    expect(pasaFiltros({ especie: sinDuracion, pagos: 1, percentil: 50 }, FILTROS_ARMADOR_VACIOS)).toBe(
      true,
    )
  })

  it('duración: pasa si la especie está en el máximo o por debajo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, duracionMax: '3.2' }
    expect(pasaFiltros({ especie: especie({ duracion: 3.2 }), pagos: 1, percentil: 50 }, filtros)).toBe(
      true,
    )
    expect(pasaFiltros({ especie: especie({ duracion: 3.3 }), pagos: 1, percentil: 50 }, filtros)).toBe(
      false,
    )
  })

  it('liquidez: percentil undefined (volumen_usd null) no pasa un filtro activo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, liquidezMin: '50' as const }
    expect(pasaFiltros({ especie: especie(), pagos: 1, percentil: undefined }, filtros)).toBe(false)
    expect(pasaFiltros({ especie: especie(), pagos: 1, percentil: 50 }, filtros)).toBe(true)
    expect(pasaFiltros({ especie: especie(), pagos: 1, percentil: 49 }, filtros)).toBe(false)
  })

  it('sector: null no pasa un filtro de sector activo, pero sin filtro se muestra igual', () => {
    const sinSector = especie({ sector: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, sector: 'O&G' }

    expect(pasaFiltros({ especie: sinSector, pagos: 1, percentil: 50 }, filtros)).toBe(false)
    expect(pasaFiltros({ especie: sinSector, pagos: 1, percentil: 50 }, FILTROS_ARMADOR_VACIOS)).toBe(
      true,
    )
  })

  it('sector: exige coincidencia exacta con el sector de la especie', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, sector: 'Financiera' }
    expect(
      pasaFiltros({ especie: especie({ sector: 'Financiera' }), pagos: 1, percentil: 50 }, filtros),
    ).toBe(true)
    expect(
      pasaFiltros({ especie: especie({ sector: 'O&G' }), pagos: 1, percentil: 50 }, filtros),
    ).toBe(false)
  })

  it('ley: null matchea sólo LEY_NO_INFORMADA, nunca una ley concreta', () => {
    const sinLey = especie({ ley: null })

    expect(
      pasaFiltros({ especie: sinLey, pagos: 1, percentil: 50 }, { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' }),
    ).toBe(false)
    expect(
      pasaFiltros(
        { especie: sinLey, pagos: 1, percentil: 50 },
        { ...FILTROS_ARMADOR_VACIOS, ley: LEY_NO_INFORMADA },
      ),
    ).toBe(true)
    expect(
      pasaFiltros(
        { especie: especie({ ley: 'ARG' }), pagos: 1, percentil: 50 },
        { ...FILTROS_ARMADOR_VACIOS, ley: LEY_NO_INFORMADA },
      ),
    ).toBe(false)
  })

  it('pagos: exige coincidencia exacta con la cantidad observada', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, pagos: '3' }
    expect(pasaFiltros({ especie: especie(), pagos: 3, percentil: 50 }, filtros)).toBe(true)
    expect(pasaFiltros({ especie: especie(), pagos: 2, percentil: 50 }, filtros)).toBe(false)
  })

  it('ticker sin cruce: no pasa ningún filtro que dependa del universo, pero sí el de pagos', () => {
    const conFiltroDeUniverso = { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' }
    expect(
      pasaFiltros({ especie: undefined, pagos: 3, percentil: undefined }, conFiltroDeUniverso),
    ).toBe(false)

    const conFiltroDePagos = { ...FILTROS_ARMADOR_VACIOS, pagos: '3' }
    expect(pasaFiltros({ especie: undefined, pagos: 3, percentil: undefined }, conFiltroDePagos)).toBe(
      true,
    )
    expect(pasaFiltros({ especie: undefined, pagos: 2, percentil: undefined }, conFiltroDePagos)).toBe(
      false,
    )

    // Sin ningún filtro activo, el ticker sin cruce pasa igual.
    expect(
      pasaFiltros({ especie: undefined, pagos: 0, percentil: undefined }, FILTROS_ARMADOR_VACIOS),
    ).toBe(true)
  })
})

// --- filtrarMeses: recalcula con_renta/con_amortizacion, no toca sin_renta, cuenta sinCruce -----------

describe('filtrarMeses', () => {
  it('recalcula con_renta y con_amortizacion sobre los sobrevivientes, sin tocar sin_renta', () => {
    const meses = [mesVacio(0)]
    meses[0] = {
      ...meses[0],
      con_renta: 2,
      con_amortizacion: 1,
      sin_renta: false, // deliberadamente distinto de lo que el recálculo daría, para probar que no se toca
      instrumentos: [
        instrumento({ ticker: 'AL30', pct_renta: 0.0075, pct_amortizacion: 0 }),
        instrumento({ ticker: 'GD30', pct_renta: 0, pct_amortizacion: 0.05 }),
      ],
    }
    const cruce = new Map([
      ['AL30', especie({ ticker: 'AL30', ley: 'ARG' })],
      ['GD30', especie({ ticker: 'GD30', ley: 'NY' })],
    ])
    const filtros = { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' } // deja pasar sólo AL30

    const resultado = filtrarMeses(meses, cruce, filtros)

    expect(resultado.meses[0].instrumentos.map((i) => i.ticker)).toEqual(['AL30'])
    expect(resultado.meses[0].con_renta).toBe(1) // recalculado sobre el sobreviviente
    expect(resultado.meses[0].con_amortizacion).toBe(0) // GD30 (el que amortizaba) quedó afuera
    expect(resultado.meses[0].sin_renta).toBe(false) // no se toca, describe el universo
  })

  it('cuenta sinCruce sin excluir esos tickers del resultado cuando no hay filtros activos', () => {
    const meses = [mesVacio(0)]
    meses[0] = {
      ...meses[0],
      instrumentos: [instrumento({ ticker: 'AL30' }), instrumento({ ticker: 'SIN_FICHA' })],
    }
    const cruce = new Map([['AL30', especie({ ticker: 'AL30' })]]) // SIN_FICHA no está en el universo

    const resultado = filtrarMeses(meses, cruce, FILTROS_ARMADOR_VACIOS)

    expect(resultado.sinCruce).toBe(1)
    expect(resultado.total).toBe(2)
    expect(resultado.visibles).toBe(2) // sin filtros activos, SIN_FICHA se muestra igual
    expect(resultado.meses[0].instrumentos.map((i) => i.ticker)).toEqual(['AL30', 'SIN_FICHA'])
  })

  it('con un filtro de universo activo, el ticker sin cruce queda afuera de visibles', () => {
    const meses = [mesVacio(0)]
    meses[0] = {
      ...meses[0],
      instrumentos: [instrumento({ ticker: 'AL30' }), instrumento({ ticker: 'SIN_FICHA' })],
    }
    const cruce = new Map([['AL30', especie({ ticker: 'AL30', ley: 'ARG' })]])
    const filtros = { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' }

    const resultado = filtrarMeses(meses, cruce, filtros)

    expect(resultado.visibles).toBe(1)
    expect(resultado.sinCruce).toBe(1)
    expect(resultado.meses[0].instrumentos.map((i) => i.ticker)).toEqual(['AL30'])
  })

  it('total y visibles cuentan tickers distintos de la ventana, no filas', () => {
    const meses = [mesVacio(0), mesVacio(1)]
    meses[0] = { ...meses[0], instrumentos: [instrumento({ ticker: 'AL30' })] }
    meses[1] = { ...meses[1], instrumentos: [instrumento({ ticker: 'AL30' })] } // mismo ticker, otro mes
    const cruce = new Map([['AL30', especie({ ticker: 'AL30' })]])

    const resultado = filtrarMeses(meses, cruce, FILTROS_ARMADOR_VACIOS)

    expect(resultado.total).toBe(1)
    expect(resultado.visibles).toBe(1)
  })
})
