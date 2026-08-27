/**
 * Lógica pura de `../lib/filtros.ts` — F-017, extendido con TIR mínima y "sólo con cupones".
 */

import { describe, expect, it } from 'vitest'

import {
  aniosHastaVencimiento,
  CALIFICACION_NO_INFORMADA,
  FILTROS_ARMADOR_INICIALES,
  FILTROS_ARMADOR_VACIOS,
  LEY_NO_INFORMADA,
  contarPagosPorTicker,
  facetarFiltros,
  filtrarMeses,
  hayFiltrosActivos,
  pasaFiltros,
  percentilesDeLiquidez,
  tickersConCupon,
  type FiltrosArmador,
} from '../lib/filtros'
import type { Especie, InstrumentoDelMes, MesDelCalendario } from '../lib/schema'

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    periodicidad: 'semestral',
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
    calificacion: null,
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

/** Datos de renglón por defecto para `pasaFiltros`: TIR USD con dato, paga cupón — mismos
 *  valores por defecto que `instrumento()`, para que las pruebas de los otros filtros no se vean
 *  afectadas por `tirMin`/`soloConCupones` cuando esos filtros están inactivos. */
function datoBase(extra: Partial<Parameters<typeof pasaFiltros>[0]> = {}) {
  return {
    especie: especie(),
    pagos: 1,
    percentil: 50,
    rendimiento: 0.1123,
    naturaleza: 'tir_usd',
    tieneCupon: true,
    ...extra,
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
    expect(hayFiltrosActivos({ ...FILTROS_ARMADOR_VACIOS, tirMin: '6' })).toBe(true)
    expect(hayFiltrosActivos({ ...FILTROS_ARMADOR_VACIOS, soloConCupones: true })).toBe(true)
    expect(
      hayFiltrosActivos({ ...FILTROS_ARMADOR_VACIOS, calificaciones: ['AAA(arg) (FIX)'] }),
    ).toBe(true)
  })

  it('es verdadero con el default de fábrica (TIR ≥ 6% y cupones)', () => {
    expect(hayFiltrosActivos(FILTROS_ARMADOR_INICIALES)).toBe(true)
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

// --- tickersConCupon: conjunto, no conteo ---------------------------------------------------------------

describe('tickersConCupon', () => {
  it('incluye un ticker que paga renta en al menos un mes de la ventana', () => {
    const meses = [mesVacio(0), mesVacio(1)]
    meses[0] = { ...meses[0], instrumentos: [instrumento({ ticker: 'AL30', pct_renta: 0.0075 })] }
    meses[1] = { ...meses[1], instrumentos: [instrumento({ ticker: 'AL30', pct_renta: 0 })] }

    expect(tickersConCupon(meses).has('AL30')).toBe(true)
  })

  it('deja afuera un bullet que sólo amortiza, sin pagar cupón en ningún mes', () => {
    const meses = [mesVacio(0)]
    meses[0] = {
      ...meses[0],
      instrumentos: [instrumento({ ticker: 'BULLET', pct_renta: 0, pct_amortizacion: 1 })],
    }

    expect(tickersConCupon(meses).has('BULLET')).toBe(false)
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
    const pasa = pasaFiltros(datoBase(), FILTROS_ARMADOR_VACIOS)
    expect(pasa).toBe(true)
  })

  // --- Plazo (vencimientoMax) -------------------------------------------------------------
  //
  // El reloj entra por parámetro para que el filtro sea determinístico: sin eso, un test que
  // pasa hoy empieza a fallar solo cuando el vencimiento de prueba queda atrás.
  const HOY = new Date('2026-08-13T00:00:00Z')

  it('plazo: deja pasar lo que vence dentro del tope y descarta lo que vence después', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, vencimientoMax: '5' }
    const cerca = especie({ vencimiento: '2029-08-13' })
    const lejos = especie({ vencimiento: '2038-01-09' })

    expect(pasaFiltros(datoBase({ especie: cerca }), filtros, HOY)).toBe(true)
    expect(pasaFiltros(datoBase({ especie: lejos }), filtros, HOY)).toBe(false)
  })

  it('plazo: una especie sin vencimiento declarado no pasa el filtro activo, pero sin filtro sí', () => {
    const sinVencimiento = especie({ vencimiento: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, vencimientoMax: '5' }

    expect(pasaFiltros(datoBase({ especie: sinVencimiento }), filtros, HOY)).toBe(false)
    expect(pasaFiltros(datoBase({ especie: sinVencimiento }), FILTROS_ARMADOR_VACIOS, HOY)).toBe(true)
  })

  it('plazo: es independiente de la duración — un amortizing largo con duración corta se filtra por fecha', () => {
    // Duración 2 años (cupones grandes al principio) pero vence en 2038: quien pide "nada más
    // allá de 5 años" está hablando de la fecha, no de la sensibilidad al precio.
    const amortizing = especie({ duracion: 2, vencimiento: '2038-01-09' })

    expect(
      pasaFiltros(datoBase({ especie: amortizing }), { ...FILTROS_ARMADOR_VACIOS, duracionMax: '5' }, HOY),
    ).toBe(true)
    expect(
      pasaFiltros(datoBase({ especie: amortizing }), { ...FILTROS_ARMADOR_VACIOS, vencimientoMax: '5' }, HOY),
    ).toBe(false)
  })

  it('plazo: un ticker sin cruce en el universo no pasa, porque el filtro depende del universo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, vencimientoMax: '5' }
    expect(pasaFiltros(datoBase({ especie: undefined }), filtros, HOY)).toBe(false)
  })

  // --- Periodicidad de cupón ----------------------------------------------------------------

  it('periodicidad: deja pasar sólo las frecuencias marcadas', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, periodicidades: ['mensual', 'trimestral'] }

    expect(pasaFiltros(datoBase({ especie: especie({ periodicidad: 'mensual' }) }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ especie: especie({ periodicidad: 'trimestral' }) }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ especie: especie({ periodicidad: 'semestral' }) }), filtros)).toBe(false)
  })

  it('periodicidad: una emisión sin cronograma no pasa el filtro activo, pero sin filtro se muestra', () => {
    const sinCronograma = especie({ periodicidad: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, periodicidades: ['semestral'] }

    expect(pasaFiltros(datoBase({ especie: sinCronograma }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ especie: sinCronograma }), FILTROS_ARMADOR_VACIOS)).toBe(true)
  })

  it('periodicidad: es independiente de `pagos`, que cuenta meses de la ventana', () => {
    // Un semestral paga dos veces en doce meses: las dos preguntas se pueden combinar, y ninguna
    // se deriva de la otra.
    const semestral = especie({ periodicidad: 'semestral' })

    expect(
      pasaFiltros(datoBase({ especie: semestral, pagos: 2 }), {
        ...FILTROS_ARMADOR_VACIOS,
        periodicidades: ['semestral'],
        pagos: '2',
      }),
    ).toBe(true)
    expect(
      pasaFiltros(datoBase({ especie: semestral, pagos: 2 }), {
        ...FILTROS_ARMADOR_VACIOS,
        periodicidades: ['semestral'],
        pagos: '4',
      }),
    ).toBe(false)
  })

  it('duración: especie sin dato no pasa un filtro activo, pero sin filtro se muestra igual', () => {
    const sinDuracion = especie({ duracion: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, duracionMax: '5' }

    expect(pasaFiltros(datoBase({ especie: sinDuracion }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ especie: sinDuracion }), FILTROS_ARMADOR_VACIOS)).toBe(true)
  })

  it('duración: pasa si la especie está en el máximo o por debajo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, duracionMax: '3.2' }
    expect(pasaFiltros(datoBase({ especie: especie({ duracion: 3.2 }) }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ especie: especie({ duracion: 3.3 }) }), filtros)).toBe(false)
  })

  it('liquidez: percentil undefined (volumen_usd null) no pasa un filtro activo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, liquidezMin: '50' as const }
    expect(pasaFiltros(datoBase({ percentil: undefined }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ percentil: 50 }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ percentil: 49 }), filtros)).toBe(false)
  })

  it('sector: null no pasa un filtro de sector activo, pero sin filtro se muestra igual', () => {
    const sinSector = especie({ sector: null })
    const filtros = { ...FILTROS_ARMADOR_VACIOS, sector: 'O&G' }

    expect(pasaFiltros(datoBase({ especie: sinSector }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ especie: sinSector }), FILTROS_ARMADOR_VACIOS)).toBe(true)
  })

  it('sector: exige coincidencia exacta con el sector de la especie', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, sector: 'Financiera' }
    expect(pasaFiltros(datoBase({ especie: especie({ sector: 'Financiera' }) }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ especie: especie({ sector: 'O&G' }) }), filtros)).toBe(false)
  })

  it('ley: null matchea sólo LEY_NO_INFORMADA, nunca una ley concreta', () => {
    const sinLey = especie({ ley: null })

    expect(pasaFiltros(datoBase({ especie: sinLey }), { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' })).toBe(
      false,
    )
    expect(
      pasaFiltros(datoBase({ especie: sinLey }), { ...FILTROS_ARMADOR_VACIOS, ley: LEY_NO_INFORMADA }),
    ).toBe(true)
    expect(
      pasaFiltros(datoBase({ especie: especie({ ley: 'ARG' }) }), {
        ...FILTROS_ARMADOR_VACIOS,
        ley: LEY_NO_INFORMADA,
      }),
    ).toBe(false)
  })

  it('calificaciones: multiselect por valor literal, sin ordenar ni traducir', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, calificaciones: ['AAA(arg) (FIX)', 'AA(arg) (FIX)'] }

    expect(
      pasaFiltros(datoBase({ especie: especie({ calificacion: 'AAA(arg) (FIX)' }) }), filtros),
    ).toBe(true)
    expect(
      pasaFiltros(datoBase({ especie: especie({ calificacion: 'B2 (Moodys)' }) }), filtros),
    ).toBe(false)
  })

  it('calificaciones: CALIFICACION_NO_INFORMADA matchea sólo calificacion: null', () => {
    const sinCalificacion = especie({ calificacion: null })
    const filtroSinInformada = { ...FILTROS_ARMADOR_VACIOS, calificaciones: [CALIFICACION_NO_INFORMADA] }

    expect(pasaFiltros(datoBase({ especie: sinCalificacion }), filtroSinInformada)).toBe(true)
    expect(
      pasaFiltros(
        datoBase({ especie: especie({ calificacion: 'AAA(arg) (FIX)' }) }),
        filtroSinInformada,
      ),
    ).toBe(false)
    expect(
      pasaFiltros(datoBase({ especie: sinCalificacion }), {
        ...FILTROS_ARMADOR_VACIOS,
        calificaciones: ['AAA(arg) (FIX)'],
      }),
    ).toBe(false)
  })

  it('calificaciones: array vacío no filtra nada', () => {
    expect(
      pasaFiltros(datoBase({ especie: especie({ calificacion: null }) }), FILTROS_ARMADOR_VACIOS),
    ).toBe(true)
  })

  it('pagos: exige coincidencia exacta con la cantidad observada', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, pagos: '3' }
    expect(pasaFiltros(datoBase({ pagos: 3 }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ pagos: 2 }), filtros)).toBe(false)
  })

  it('ticker sin cruce: no pasa ningún filtro que dependa del universo, pero sí el de pagos', () => {
    const conFiltroDeUniverso = { ...FILTROS_ARMADOR_VACIOS, ley: 'ARG' }
    expect(
      pasaFiltros(datoBase({ especie: undefined, pagos: 3, percentil: undefined }), conFiltroDeUniverso),
    ).toBe(false)

    const conFiltroDePagos = { ...FILTROS_ARMADOR_VACIOS, pagos: '3' }
    expect(
      pasaFiltros(datoBase({ especie: undefined, pagos: 3, percentil: undefined }), conFiltroDePagos),
    ).toBe(true)
    expect(
      pasaFiltros(datoBase({ especie: undefined, pagos: 2, percentil: undefined }), conFiltroDePagos),
    ).toBe(false)

    // Sin ningún filtro activo, el ticker sin cruce pasa igual.
    expect(
      pasaFiltros(datoBase({ especie: undefined, pagos: 0, percentil: undefined }), FILTROS_ARMADOR_VACIOS),
    ).toBe(true)
  })

  it('ticker sin cruce: tirMin y soloConCupones se evalúan igual, sin depender del universo', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, tirMin: '6' }
    expect(
      pasaFiltros(
        datoBase({ especie: undefined, percentil: undefined, rendimiento: 0.08, naturaleza: 'tir_usd' }),
        filtros,
      ),
    ).toBe(true)
    expect(
      pasaFiltros(
        datoBase({ especie: undefined, percentil: undefined, rendimiento: 0.04, naturaleza: 'tir_usd' }),
        filtros,
      ),
    ).toBe(false)
  })

  it('tirMin: pasa con rendimiento igual o mayor al umbral, en puntos porcentuales', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, tirMin: '6' }
    expect(pasaFiltros(datoBase({ rendimiento: 0.08 }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ rendimiento: 0.06 }), filtros)).toBe(true) // igual al umbral, pasa
    expect(pasaFiltros(datoBase({ rendimiento: 0.04 }), filtros)).toBe(false)
  })

  it('tirMin: un rendimiento null no pasa el filtro activo, aunque sin filtro se muestre', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, tirMin: '6' }
    expect(pasaFiltros(datoBase({ rendimiento: null }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ rendimiento: null }), FILTROS_ARMADOR_VACIOS)).toBe(true)
  })

  it('tirMin: sólo aplica a naturalezas de TIR; CER y TNA quedan afuera', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, tirMin: '6' }
    expect(pasaFiltros(datoBase({ rendimiento: 0.5, naturaleza: 'tasa_real_cer' }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ rendimiento: 0.5, naturaleza: 'tna_nominal_ars' }), filtros)).toBe(false)
    expect(pasaFiltros(datoBase({ rendimiento: 0.08, naturaleza: 'tir_dolar_linked' }), filtros)).toBe(
      true,
    )
    // Tanda 2 (26/08/2026): la tasa fija en pesos declara TIR efectiva anual, así que el umbral sí
    // es su unidad y el filtro la evalúa en vez de dejarla afuera por no tener TIR.
    expect(pasaFiltros(datoBase({ rendimiento: 0.5, naturaleza: 'tir_ea_ars' }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ rendimiento: 0.02, naturaleza: 'tir_ea_ars' }), filtros)).toBe(false)
  })

  it('tirMin vacío no filtra: cualquier naturaleza y rendimiento pasan', () => {
    expect(
      pasaFiltros(datoBase({ rendimiento: null, naturaleza: 'tasa_real_cer' }), FILTROS_ARMADOR_VACIOS),
    ).toBe(true)
  })

  it('soloConCupones: exige que el ticker esté en el conjunto de cupones', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, soloConCupones: true }
    expect(pasaFiltros(datoBase({ tieneCupon: true }), filtros)).toBe(true)
    expect(pasaFiltros(datoBase({ tieneCupon: false }), filtros)).toBe(false)
    // Desactivado, no filtra.
    expect(pasaFiltros(datoBase({ tieneCupon: false }), FILTROS_ARMADOR_VACIOS)).toBe(true)
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

  it('con el default de fábrica, deja afuera TIR baja, sin dato y sin cupón', () => {
    const meses = [mesVacio(0)]
    meses[0] = {
      ...meses[0],
      instrumentos: [
        instrumento({ ticker: 'ALTA', rendimiento: 0.08, naturaleza: 'tir_usd', pct_renta: 0.01 }),
        instrumento({ ticker: 'BAJA', rendimiento: 0.02, naturaleza: 'tir_usd', pct_renta: 0.01 }),
        instrumento({ ticker: 'SD', rendimiento: null, naturaleza: 'tir_usd', pct_renta: 0.01 }),
        instrumento({
          ticker: 'BULLET',
          rendimiento: 0.08,
          naturaleza: 'tir_usd',
          pct_renta: 0,
          pct_amortizacion: 1,
        }),
      ],
    }
    const cruce = new Map<string, Especie>()

    const resultado = filtrarMeses(meses, cruce, FILTROS_ARMADOR_INICIALES)

    expect(resultado.meses[0].instrumentos.map((i) => i.ticker)).toEqual(['ALTA'])
    expect(resultado.visibles).toBe(1)
    expect(resultado.total).toBe(4)
  })
})

describe('aniosHastaVencimiento', () => {
  const HOY = new Date('2026-08-13T00:00:00Z')

  it('cuenta los años que faltan', () => {
    expect(aniosHastaVencimiento('2031-08-13', HOY)).toBeCloseTo(5, 1)
  })

  it('sin vencimiento declarado devuelve null: no se supone un plazo', () => {
    expect(aniosHastaVencimiento(null, HOY)).toBeNull()
  })

  it('una fecha ilegible devuelve null en vez de un número inventado', () => {
    expect(aniosHastaVencimiento('no es una fecha', HOY)).toBeNull()
  })

  it('un vencimiento ya pasado da negativo, no cero: el dato roto se ve', () => {
    expect(aniosHastaVencimiento('2020-01-01', HOY)).toBeLessThan(0)
  })
})

describe('facetarFiltros', () => {
  const HOY = new Date('2026-08-14T00:00:00Z')

  /** Cuatro ONs con los perfiles cruzados a propósito: dos sectores, cuatro emisores, una sin ley
   *  declarada y otra sin calificación. ONA es la única que paga dos veces en la ventana. */
  function universoFacetado() {
    const especies = [
      especie({ ticker: 'ONA', emision: 'ONA', sector: 'O&G', emisor: 'YPF', ley: 'Ley Argentina', calificacion: 'AAA(arg)' }),
      especie({ ticker: 'ONB', emision: 'ONB', sector: 'Financiera', emisor: 'Banco Galicia', ley: 'Ley Argentina', calificacion: 'AA(arg)' }),
      especie({ ticker: 'ONC', emision: 'ONC', sector: 'O&G', emisor: 'Vista', ley: 'Ley N.Y.', calificacion: null }),
      especie({ ticker: 'OND', emision: 'OND', sector: 'Financiera', emisor: 'Banco Macro', ley: null, calificacion: 'AA(arg)' }),
    ]
    const cruce = new Map(especies.map((e) => [e.ticker, e]))
    const meses = Array.from({ length: 12 }, (_, i) => mesVacio(i))
    meses[0].instrumentos = [
      instrumento({ ticker: 'ONA', emision: 'ONA', rendimiento: 0.12 }),
      instrumento({ ticker: 'ONB', emision: 'ONB', rendimiento: 0.08 }),
      instrumento({ ticker: 'ONC', emision: 'ONC', rendimiento: 0.04 }),
      instrumento({ ticker: 'OND', emision: 'OND', rendimiento: 0.1 }),
    ]
    meses[1].instrumentos = [instrumento({ ticker: 'ONA', emision: 'ONA', rendimiento: 0.12 })]
    return { cruce, meses }
  }

  function facetar(parcial: Partial<FiltrosArmador> = {}) {
    const { cruce, meses } = universoFacetado()
    return facetarFiltros(meses, cruce, { ...FILTROS_ARMADOR_VACIOS, ...parcial }, HOY)
  }

  it('sin filtros ofrece todo lo que hay en la ventana', () => {
    const { opciones } = facetar()
    expect([...opciones.sectores].sort()).toEqual(['Financiera', 'O&G'])
    expect([...opciones.emisores].sort()).toEqual(['Banco Galicia', 'Banco Macro', 'Vista', 'YPF'])
    expect([...opciones.leyes].sort()).toEqual(['Ley Argentina', 'Ley N.Y.'])
    expect(opciones.tieneLeyNoInformada).toBe(true)
    expect([...opciones.pagos].sort()).toEqual([1, 2])
  })

  it('elegir sector deja sólo los emisores que emiten en ese sector', () => {
    const { opciones } = facetar({ sector: 'O&G' })
    expect([...opciones.emisores].sort()).toEqual(['Vista', 'YPF'])
  })

  it('y la inversa: elegir emisor deja sólo su sector', () => {
    const { opciones } = facetar({ emisor: 'Vista' })
    expect(opciones.sectores).toEqual(['O&G'])
  })

  it('el select propio no se acota a sí mismo: siempre se puede cambiar de idea', () => {
    const { opciones } = facetar({ sector: 'O&G' })
    expect([...opciones.sectores].sort()).toEqual(['Financiera', 'O&G'])
  })

  it('un umbral también acota: con TIR mín. 6% el emisor de la ON al 4% desaparece', () => {
    const { opciones } = facetar({ tirMin: '6' })
    expect([...opciones.emisores].sort()).toEqual(['Banco Galicia', 'Banco Macro', 'YPF'])
  })

  it('"ley no informada" sólo se ofrece si alguna superviviente no la declara', () => {
    expect(facetar({ sector: 'O&G' }).opciones.tieneLeyNoInformada).toBe(false)
    expect(facetar({ sector: 'Financiera' }).opciones.tieneLeyNoInformada).toBe(true)
  })

  it('una selección sin respaldo se apaga y no envenena las opciones de las demás', () => {
    // Sin el punto fijo, el sector inexistente dejaría el select de emisor vacío: nadie pasa el
    // filtro, así que no habría ningún valor que ofrecer, y la barra quedaría muerta.
    const { opciones, efectivos } = facetar({ sector: 'Mineria' })
    expect(efectivos.sector).toBeNull()
    expect([...opciones.emisores].sort()).toEqual(['Banco Galicia', 'Banco Macro', 'Vista', 'YPF'])
  })

  it('de las calificaciones tildadas sobreviven las que el resto de los filtros respalda', () => {
    const { opciones, efectivos } = facetar({
      sector: 'O&G',
      calificaciones: ['AAA(arg)', 'AA(arg)'],
    })
    expect(opciones.calificaciones).toEqual(['AAA(arg)'])
    expect(efectivos.calificaciones).toEqual(['AAA(arg)'])
    expect(efectivos.sector).toBe('O&G')
  })

  it('los umbrales no se apagan nunca, ni cuando dejan la ventana en cero', () => {
    const { efectivos } = facetar({ tirMin: '99', soloConCupones: true })
    expect(efectivos.tirMin).toBe('99')
    expect(efectivos.soloConCupones).toBe(true)
  })

  it('declara lo que apagó, con el valor que el asesor había elegido', () => {
    const { apagadas } = facetar({ sector: 'Mineria', calificaciones: ['AAA(arg)', 'B(arg)'] })
    expect(apagadas).toEqual([
      { dimension: 'sector', valor: 'Mineria' },
      { dimension: 'calificaciones', valor: 'B(arg)' },
    ])
  })

  it('sin nada apagado no hay nada que declarar', () => {
    expect(facetar({ sector: 'O&G' }).apagadas).toEqual([])
  })

  it('sin nada que apagar los efectivos son los del store', () => {
    const filtros = { ...FILTROS_ARMADOR_VACIOS, sector: 'O&G', tirMin: '6' }
    const { cruce, meses } = universoFacetado()
    expect(facetarFiltros(meses, cruce, filtros, HOY).efectivos).toEqual(filtros)
  })

  it('entre dos selecciones incompatibles gana la más general y cae la más específica', () => {
    // 'Financiera' y 'YPF' no conviven: sin un orden de validación se invalidarían mutuamente y el
    // asesor perdería las dos.
    const { efectivos, apagadas } = facetar({ sector: 'Financiera', emisor: 'YPF' })
    expect(efectivos.sector).toBe('Financiera')
    expect(efectivos.emisor).toBeNull()
    expect(apagadas).toEqual([{ dimension: 'emisor', valor: 'YPF' }])
  })
})
