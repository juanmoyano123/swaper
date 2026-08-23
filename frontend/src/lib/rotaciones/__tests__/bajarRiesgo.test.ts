/**
 * F-033 — los cuatro GWT de la ficha más los edge case explícitos: sin dato en un eje, crédito y
 * moneda como primario ("no medible"), moneda nunca como motivo de descarte, y distinto emisor
 * descartado por crédito cuando crédito no es el primario.
 *
 * Toda la aritmética de los seis ejes la resuelve `vectorDeRiesgo()` de F-031 (`../../cartera/riesgo`):
 * acá no se reimplementa duración/legislación/liquidez/concentración, sólo se arman los fixtures y
 * se llama a la lib de esta feature con datos reales de `vectorDeRiesgo`.
 */

import { describe, expect, it } from 'vitest'

import type { Concentracion } from '../../cartera/esquemaConcentracion'
import { vectorDeRiesgo, type EspecieRiesgo, type PosicionConPeso } from '../../cartera/riesgo'
import {
  BANDA_RENDIMIENTO_PP,
  EJE_PRIMARIO_DEFAULT,
  claveCandidata,
  evaluarBajarRiesgo,
} from '../bajarRiesgo'
import type { Candidata } from '../esquemaRotaciones'

// --- Fixtures ------------------------------------------------------------------------------------

function especie(overrides: Partial<EspecieRiesgo> & { ticker: string }): EspecieRiesgo {
  return {
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    clase_activo: 'bono_soberano',
    duracion: null,
    ley: null,
    volumen_usd: null,
    calificacion: null,
    dato_sano: true,
    ...overrides,
  }
}

function especieRotacion(ticker: string, overrides: Record<string, unknown> = {}) {
  return {
    ticker,
    emisor: 'República Argentina',
    rendimiento: 0.11,
    duracion: 3.5,
    moneda_cupon: 'USD',
    ley: 'Ley N.Y.',
    calificacion: null,
    lamina: 1,
    frecuencia_cupon: 'semestral',
    volumen_usd: 100_000,
    ...overrides,
  }
}

function candidata(overrides: {
  origen?: Record<string, unknown>
  destino?: Record<string, unknown>
  deltaRendPp?: number
  mismoEmisor?: boolean
} = {}): Candidata {
  const origen = especieRotacion('AL30D', { duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000, ...overrides.origen })
  const destino = especieRotacion('GD30D', { duracion: 2.5, ley: 'Ley N.Y.', volumen_usd: 300_000, ...overrides.destino })
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen,
    destino,
    delta: { rendimiento_pp: overrides.deltaRendPp ?? 0.2, duracion: destino.duracion! - origen.duracion! },
    flags: {
      mismo_emisor: overrides.mismoEmisor ?? true,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    // Explícito aunque F-033 no lo lea: desde F-034 el contrato lo declara, y un fixture que lo
    // omitiera dejaría de describir lo que el backend realmente manda.
    costo: null,
  } as Candidata
}

function concentracion(pesoMaximo: number): Concentracion {
  return {
    perfil: 'moderado',
    limites: { tope_rend_usd: 0.15, percentil_liquidez: 25, max_emisor: 15, max_soberano: 65, max_sector: 40, min_sectores: 3 },
    topes: [
      { tipo: 'emisor', clave: 'ARG', nombre: 'República Argentina', peso: pesoMaximo, tope: 15, excedido: pesoMaximo > 15, exceso: Math.max(0, pesoMaximo - 15) },
    ],
    excedidos: pesoMaximo > 15 ? 1 : 0,
    distribucion: { sector: [], ley: [], naturaleza: [] },
    sectores: { presentes: ['Soberano'], cantidad: 1, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    fci: [],
    alertas: [],
  }
}

const POSICIONES_ACTUALES: PosicionConPeso[] = [{ ticker: 'AL30D', peso: 100 }]

const PORTICKER_BASE = new Map<string, EspecieRiesgo>([
  ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
  ['GD30D', especie({ ticker: 'GD30D', duracion: 2.5, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
])

/** Siempre se llama con el MISMO `porTicker` que después se le pasa a `evaluarBajarRiesgo`: el
 *  percentil de liquidez se calcula sobre todo el universo (`porTicker.values()`), así que si acá
 *  se usara un universo más chico que el de la evaluación, "actual" y "simulado" quedarían medidos
 *  contra dos pools distintos. */
function vectorActualBase(concentracionActual: Concentracion, porTicker: ReadonlyMap<string, EspecieRiesgo> = PORTICKER_BASE) {
  return vectorDeRiesgo(POSICIONES_ACTUALES, porTicker, concentracionActual)
}

function mapaConcentracion(candidata: Candidata, concentracionSimulada: Concentracion | null) {
  return new Map<string, Concentracion | null>([[claveCandidata(candidata), concentracionSimulada]])
}

// --- GWT-1: preselección de duración -------------------------------------------------------------

describe('GWT-1: eje primario por defecto', () => {
  it('duración es el default, y es uno de los seis elegibles', () => {
    expect(EJE_PRIMARIO_DEFAULT).toBe('duracion')
  })
})

// --- GWT-2: sube concentración → se descarta -------------------------------------------------------

describe('GWT-2: baja duración pero sube concentración', () => {
  it('se descarta: empeora uno de los otros cinco ejes', () => {
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual)
    const c = candidata()
    const concentracionSimuladaPeor = concentracion(70) // sube: empeora

    const resultado = evaluarBajarRiesgo(
      [c],
      'duracion',
      vectorActual,
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracionSimuladaPeor),
    )

    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'concentracion', motivo: 'empeora' }])
  })
})

// --- GWT-3: fuera de banda -------------------------------------------------------------------------

describe('GWT-3: rendimiento fuera de la banda de ±0.5pp', () => {
  it('se descarta por fuera_de_banda, sin llegar a mirar los demás ejes', () => {
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual)
    const c = candidata({ deltaRendPp: 0.8 })

    const resultado = evaluarBajarRiesgo([c], 'duracion', vectorActual, POSICIONES_ACTUALES, PORTICKER_BASE, new Map())

    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'duracion', motivo: 'fuera_de_banda' }])
    expect(BANDA_RENDIMIENTO_PP).toBe(0.5)
  })
})

// --- GWT-4: ninguna candidata cumple ---------------------------------------------------------------

describe('GWT-4: ninguna candidata cumple', () => {
  it('declara que no hay propuesta, sin relajar la restricción', () => {
    const porTicker = new Map(PORTICKER_BASE).set('AE38D', especie({ ticker: 'AE38D', duracion: 2.0, ley: 'Ley N.Y.', volumen_usd: 300_000 }))
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual, porTicker)
    const fueraDeBanda = candidata({ deltaRendPp: 0.9 })
    const subeConcentracion = candidata({ destino: { ticker: 'AE38D' }, deltaRendPp: 0.1 })

    const mapa = new Map<string, Concentracion | null>([
      [claveCandidata(subeConcentracion), concentracion(80)],
    ])

    const resultado = evaluarBajarRiesgo(
      [fueraDeBanda, subeConcentracion],
      'duracion',
      vectorActual,
      POSICIONES_ACTUALES,
      porTicker,
      mapa,
    )

    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.propuestas).toEqual([])
    expect(resultado.descartes).toHaveLength(2)
  })
})

// --- Candidata que sí cumple, de punta a punta ------------------------------------------------------

describe('una candidata que mejora duración sin empeorar el resto', () => {
  it('aparece en propuestas, con el valor del eje primario actual y simulado', () => {
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual)
    const c = candidata()
    const concentracionSimuladaMejor = concentracion(20)

    const resultado = evaluarBajarRiesgo(
      [c],
      'duracion',
      vectorActual,
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracionSimuladaMejor),
    )

    expect(resultado.hayPropuesta).toBe(true)
    expect(resultado.propuestas).toHaveLength(1)
    expect(resultado.propuestas[0].candidata).toBe(c)
    expect(resultado.propuestas[0].valorActual).toBeCloseTo(3.5)
    expect(resultado.propuestas[0].valorSimulado).toBeCloseTo(2.5)
    expect(resultado.propuestas[0].unidad).toBe('años')
  })
})

// --- Sin dato en el destino -------------------------------------------------------------------------

describe('destino sin dato del eje primario', () => {
  it('legislación: destino sin ley informada se descarta por sin_dato', () => {
    const porTicker = new Map(PORTICKER_BASE).set('SINLEY', especie({ ticker: 'SINLEY', duracion: 2.0, ley: null, volumen_usd: 80_000 }))
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual, porTicker)
    const c = candidata({ destino: { ticker: 'SINLEY', ley: null } })

    const resultado = evaluarBajarRiesgo([c], 'legislacion', vectorActual, POSICIONES_ACTUALES, porTicker, new Map())

    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'legislacion', motivo: 'sin_dato' }])
  })

  it('liquidez: destino sin volumen_usd se descarta por sin_dato', () => {
    const porTicker = new Map(PORTICKER_BASE).set('SINVOL', especie({ ticker: 'SINVOL', duracion: 2.0, ley: 'Ley N.Y.', volumen_usd: null }))
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual, porTicker)
    const c = candidata({ destino: { ticker: 'SINVOL', volumen_usd: null } })

    const resultado = evaluarBajarRiesgo([c], 'liquidez', vectorActual, POSICIONES_ACTUALES, porTicker, new Map())

    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'liquidez', motivo: 'sin_dato' }])
  })
})

// --- Crédito y moneda como primario: no medible ------------------------------------------------------

describe('crédito o moneda como eje primario', () => {
  it('crédito: declara que no es medible, sin evaluar candidatas', () => {
    const resultado = evaluarBajarRiesgo([candidata()], 'credito', [], POSICIONES_ACTUALES, PORTICKER_BASE, new Map())
    expect(resultado.noMedible).toBe(true)
    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.motivo).toMatch(/Crédito/)
  })

  it('moneda: declara que no es medible, sin evaluar candidatas', () => {
    const resultado = evaluarBajarRiesgo([candidata()], 'moneda', [], POSICIONES_ACTUALES, PORTICKER_BASE, new Map())
    expect(resultado.noMedible).toBe(true)
    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.motivo).toMatch(/Moneda/)
  })
})

// --- Distinto emisor: crédito como secundario ---------------------------------------------------------

describe('distinto emisor, con crédito como eje NO primario', () => {
  it('se descarta por crédito, sin_criterio_medible', () => {
    const porTicker = new Map(PORTICKER_BASE).set('AE38D', especie({ ticker: 'AE38D', duracion: 2.0, ley: 'Ley N.Y.', volumen_usd: 300_000 }))
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual, porTicker)
    const c = candidata({ destino: { ticker: 'AE38D' }, mismoEmisor: false })

    const resultado = evaluarBajarRiesgo([c], 'duracion', vectorActual, POSICIONES_ACTUALES, porTicker, new Map())

    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'credito', motivo: 'sin_criterio_medible' }])
  })
})

// --- Moneda nunca es motivo de descarte cuando no es primaria ------------------------------------------

describe('moneda nunca aparece como motivo de descarte', () => {
  it('con varias candidatas fallando por distintos motivos, ninguna trae eje "moneda"', () => {
    const porTicker = new Map(PORTICKER_BASE)
      .set('SINLEY', especie({ ticker: 'SINLEY', duracion: 2.0, ley: null, volumen_usd: 80_000 }))
      .set('AE38D', especie({ ticker: 'AE38D', duracion: 2.0, ley: 'Ley N.Y.', volumen_usd: 300_000 }))
    const actual = concentracion(40)
    const vectorActual = vectorActualBase(actual, porTicker)

    const fueraDeBanda = candidata({ deltaRendPp: 0.9 })
    const sinDatoLegislacion = candidata({ destino: { ticker: 'SINLEY', ley: null } })
    const distintoEmisor = candidata({ destino: { ticker: 'AE38D' }, mismoEmisor: false })
    const subeConcentracion = candidata()

    const resultado = evaluarBajarRiesgo(
      [fueraDeBanda, sinDatoLegislacion, distintoEmisor, subeConcentracion],
      'duracion',
      vectorActual,
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(subeConcentracion, concentracion(90)),
    )

    expect(resultado.descartes.length).toBeGreaterThan(0)
    expect(resultado.descartes.some((d) => d.eje === 'moneda')).toBe(false)
  })
})

// --- Legislación: la dirección de "mejora" está atada a mejora_ley del motor ----------------------------

describe('legislación como eje primario', () => {
  it('mejora estricta = pasar de ley local a ley extranjera (mismo sentido que mejora_ley del backend)', () => {
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley Argentina', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
    ])
    const actual = concentracion(10)
    const vectorActual = vectorDeRiesgo(POSICIONES_ACTUALES, porTicker, actual)
    const c = candidata({ origen: { ley: 'Ley Argentina' }, destino: { ley: 'Ley N.Y.' } })

    const resultado = evaluarBajarRiesgo(
      [c],
      'legislacion',
      vectorActual,
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(5)),
    )

    expect(resultado.hayPropuesta).toBe(true)
    expect(resultado.propuestas[0].valorActual).toBe(0) // 0% bajo ley extranjera
    expect(resultado.propuestas[0].valorSimulado).toBe(100) // 100% bajo ley extranjera
  })
})
