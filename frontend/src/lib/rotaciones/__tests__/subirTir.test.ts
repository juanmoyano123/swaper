/**
 * F-034 — los cuatro GWT de la ficha (`plan.md:1650`) más los casos que fijan la política: qué
 * mata una fila, qué se declara, y qué candidatas ni siquiera son de este modo.
 *
 * Como en `bajarRiesgo.test.ts`, toda la aritmética de los seis ejes la resuelve `vectorDeRiesgo()`
 * de F-031: acá se arman fixtures y se llama a la lib con datos reales del vector, sin
 * reimplementar duración/legislación/liquidez/concentración.
 */

import { describe, expect, it } from 'vitest'

import type { Concentracion } from '../../cartera/esquemaConcentracion'
import { vectorDeRiesgo, type EspecieRiesgo, type IdDeEje, type PosicionConPeso } from '../../cartera/riesgo'
import { claveCandidata } from '../ejes'
import type { Candidata } from '../esquemaRotaciones'
import { contrapartidasDe, evaluarSubirTir, type EvaluacionEje } from '../subirTir'

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

function candidata(
  overrides: {
    origen?: Record<string, unknown>
    destino?: Record<string, unknown>
    deltaRendPp?: number
    deltaDuracion?: number | null
    mismoEmisor?: boolean
    tipo?: 'mejora_rendimiento' | 'mejora_perfil'
  } = {},
): Candidata {
  const origen = especieRotacion('AL30D', { duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000, ...overrides.origen })
  const destino = especieRotacion('GD30D', { duracion: 5.8, ley: 'Ley N.Y.', volumen_usd: 300_000, ...overrides.destino })
  const deltaDuracion =
    overrides.deltaDuracion !== undefined
      ? overrides.deltaDuracion
      : destino.duracion !== null && origen.duracion !== null
        ? (destino.duracion as number) - (origen.duracion as number)
        : null
  return {
    tipo: overrides.tipo ?? 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen,
    destino,
    delta: { rendimiento_pp: overrides.deltaRendPp ?? 1.8, duracion: deltaDuracion },
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
  ['GD30D', especie({ ticker: 'GD30D', duracion: 5.8, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
])

/** Siempre con el MISMO `porTicker` que después recibe `evaluarSubirTir`: el percentil de liquidez
 *  se calcula sobre todo el universo (`porTicker.values()`), así que un universo más chico acá
 *  mediría "actual" y "simulado" contra dos pools distintos. */
function vectorActualBase(
  concentracionActual: Concentracion,
  porTicker: ReadonlyMap<string, EspecieRiesgo> = PORTICKER_BASE,
  posiciones: PosicionConPeso[] = POSICIONES_ACTUALES,
) {
  return vectorDeRiesgo(posiciones, porTicker, concentracionActual)
}

function mapaConcentracion(c: Candidata, concentracionSimulada: Concentracion | null) {
  return new Map<string, Concentracion | null>([[claveCandidata(c), concentracionSimulada]])
}

function ejeDe(ejes: EvaluacionEje[], id: IdDeEje): EvaluacionEje {
  return ejes.find((e) => e.eje === id)!
}

// --- GWT-1: la fila declara la mejora y todos los deltas ------------------------------------------

describe('GWT-1: mejora de rendimiento con su contrapartida en la misma fila', () => {
  it('declara duración, cambio de ley y su unidad, juntos', () => {
    // Sube 1,8pp de rendimiento, alarga la duración de 3,5 a 5,8 años y pasa de Ley N.Y. a Ley
    // Argentina: el caso textual de la spec.
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['AE38', especie({ ticker: 'AE38', duracion: 5.8, ley: 'Ley Argentina', volumen_usd: 300_000 })],
    ])
    const c = candidata({ destino: { ticker: 'AE38', duracion: 5.8, ley: 'Ley Argentina', volumen_usd: 300_000 } })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.hayPropuesta).toBe(true)
    const [propuesta] = resultado.propuestas

    const duracion = ejeDe(propuesta.ejes, 'duracion')
    expect(duracion.estado).toBe('empeora')
    expect(duracion.valorActual).toBe(3.5)
    expect(duracion.valorSimulado).toBe(5.8)
    expect(duracion.unidad).toBe('años')

    // El valor del eje es el peso bajo ley extranjera: pasar todo a ley local lo lleva de 100 a 0.
    const legislacion = ejeDe(propuesta.ejes, 'legislacion')
    expect(legislacion.estado).toBe('empeora')
    expect(legislacion.valorActual).toBe(100)
    expect(legislacion.valorSimulado).toBe(0)
    expect(legislacion.nota).toBe('Ley N.Y. → Ley Argentina')

    expect(propuesta.ningunEjeEmpeora).toBe(false)
    expect(propuesta.candidata.delta.rendimiento_pp).toBe(1.8)
  })

  it('devuelve siempre los seis ejes, aunque sólo dos empeoren — regla 7', () => {
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.propuestas[0].ejes.map((e) => e.eje)).toEqual([
      'duracion',
      'credito',
      'legislacion',
      'liquidez',
      'concentracion',
      'moneda',
    ])
  })
})

// --- GWT-2: sin deltas calculables, la fila no se muestra -----------------------------------------

describe('GWT-2: una propuesta sin deltas calculables no se muestra', () => {
  it('descarta y contabiliza cuando falta la duración de una punta', () => {
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: null, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
    ])
    const c = candidata({ destino: { duracion: null }, deltaDuracion: null })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.propuestas).toEqual([])
    expect(resultado.hayPropuesta).toBe(false)
    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'duracion', motivo: 'sin_dato' }])
    // Se evaluó: no desaparece del recuento por no haberse podido mostrar.
    expect(resultado.evaluadas).toBe(1)
  })

  it('descarta cuando falta la ley en una punta', () => {
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: 5.8, ley: null, volumen_usd: 300_000 })],
    ])
    const c = candidata({ destino: { ley: null } })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'legislacion', motivo: 'sin_dato' }])
  })

  it('descarta cuando falta el volumen del destino', () => {
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: 5.8, ley: 'Ley N.Y.', volumen_usd: null })],
    ])
    const c = candidata({ destino: { volumen_usd: null } })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'liquidez', motivo: 'sin_dato' }])
  })

  it('descarta cuando la concentración simulada no llegó', () => {
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, null),
    )

    expect(resultado.propuestas).toEqual([])
    expect(resultado.descartes).toEqual([{ candidata: c, eje: 'concentracion', motivo: 'sin_dato' }])
    expect(resultado.evaluadas).toBe(1)
  })
})

// --- GWT-3: sin contrapartida, se declara explícito -----------------------------------------------

describe('GWT-3: una rotación que no empeora ningún eje lo declara', () => {
  it('marca ningunEjeEmpeora cuando todo mejora o queda igual, con el mismo emisor', () => {
    // Destino con menos duración, más volumen, misma ley y misma concentración: nada empeora.
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: 2.5, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
    ])
    const c = candidata({ destino: { duracion: 2.5, volumen_usd: 300_000 } })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    const [propuesta] = resultado.propuestas
    expect(propuesta.ningunEjeEmpeora).toBe(true)
    expect(propuesta.ejes.filter((e) => e.estado === 'empeora')).toEqual([])
    expect(contrapartidasDe(propuesta)).toEqual([])
  })

  it('un cambio de emisor es contrapartida aunque ningún número empeore', () => {
    // El riesgo de crédito no tiene métrica escalar (regla 7): sin poder medirlo, "no empeoró" no
    // se puede afirmar, y el cambio de emisor se nombra como la contrapartida que es.
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['YPFD', especie({ ticker: 'YPFD', duracion: 2.5, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
    ])
    const c = candidata({
      destino: { ticker: 'YPFD', emisor: 'YPF S.A.', duracion: 2.5, volumen_usd: 300_000 },
      mismoEmisor: false,
    })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    const [propuesta] = resultado.propuestas
    expect(propuesta.ningunEjeEmpeora).toBe(false)
    expect(contrapartidasDe(propuesta).map((e) => e.eje)).toEqual(['credito'])
    expect(ejeDe(propuesta.ejes, 'credito').nota).toContain('cambia de emisor')
    expect(ejeDe(propuesta.ejes, 'credito').nota).toContain('República Argentina → YPF S.A.')
  })
})

// --- GWT-4: la cobertura parcial se declara junto al delta ----------------------------------------

describe('GWT-4: cobertura parcial declarada junto al delta', () => {
  it('marca la cobertura como parcial cuando una posición de la cartera no tiene duración', () => {
    // Una tercera posición sin duración: el delta agregado sigue siendo calculable —las dos puntas
    // de la rotación sí tienen dato—, así que la propuesta se muestra y lo que falta se declara.
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['GD30D', especie({ ticker: 'GD30D', duracion: 5.8, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
      ['SINDUR', especie({ ticker: 'SINDUR', duracion: null, ley: 'Ley N.Y.', volumen_usd: 50_000 })],
    ])
    const posiciones: PosicionConPeso[] = [
      { ticker: 'AL30D', peso: 50 },
      { ticker: 'SINDUR', peso: 50 },
    ]
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker, posiciones),
      posiciones,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    const duracion = ejeDe(resultado.propuestas[0].ejes, 'duracion')
    expect(duracion.valorActual).not.toBeNull()
    expect(duracion.cobertura).toEqual({ pctActual: 50, pctSimulada: 50, parcial: true })
  })

  it('no marca cobertura parcial cuando toda la cartera tiene el dato', () => {
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(ejeDe(resultado.propuestas[0].ejes, 'duracion').cobertura).toEqual({
      pctActual: 100,
      pctSimulada: 100,
      parcial: false,
    })
  })
})

// --- Política del modo ----------------------------------------------------------------------------

describe('alcance del modo', () => {
  it('ignora las candidatas de mejora de perfil: son el insumo del otro modo, no un descarte', () => {
    const c = candidata({ tipo: 'mejora_perfil' })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.propuestas).toEqual([])
    expect(resultado.descartes).toEqual([])
    expect(resultado.evaluadas).toBe(0)
  })

  it('una concentración que empeora se declara, no se filtra', () => {
    // La diferencia con F-033: allá esto descartaría la candidata; acá empeorar es lo que hay que
    // mostrar.
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(40)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracion(80)),
    )

    expect(resultado.hayPropuesta).toBe(true)
    const concentracionEje = ejeDe(resultado.propuestas[0].ejes, 'concentracion')
    expect(concentracionEje.estado).toBe('empeora')
    expect(concentracionEje.valorActual).toBe(40)
    expect(concentracionEje.valorSimulado).toBe(80)
  })

  it('crédito sin calificación en una punta se declara literal, no descarta la fila', () => {
    const porTicker = new Map<string, EspecieRiesgo>([
      ['AL30D', especie({ ticker: 'AL30D', duracion: 3.5, ley: 'Ley N.Y.', volumen_usd: 100_000 })],
      ['YPFD', especie({ ticker: 'YPFD', duracion: 5.8, ley: 'Ley N.Y.', volumen_usd: 300_000 })],
    ])
    const c = candidata({
      origen: { calificacion: 'AAA (FIX)' },
      destino: { ticker: 'YPFD', emisor: 'YPF S.A.', calificacion: null },
      mismoEmisor: false,
    })
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100), porTicker),
      POSICIONES_ACTUALES,
      porTicker,
      mapaConcentracion(c, concentracion(100)),
    )

    expect(resultado.hayPropuesta).toBe(true)
    // La calificación se muestra tal como la declara la fuente, y su ausencia se nombra: nunca se
    // ordena una contra otra (regla 7/11).
    expect(ejeDe(resultado.propuestas[0].ejes, 'credito').nota).toContain('AAA (FIX) → sin calificación')
  })

  it('moneda siempre se declara como no cambiante, sin calcularse', () => {
    const c = candidata()
    const resultado = evaluarSubirTir(
      [c],
      vectorActualBase(concentracion(100)),
      POSICIONES_ACTUALES,
      PORTICKER_BASE,
      mapaConcentracion(c, concentracion(100)),
    )

    const moneda = ejeDe(resultado.propuestas[0].ejes, 'moneda')
    expect(moneda.estado).toBe('cualitativo')
    expect(moneda.valorActual).toBeNull()
    expect(moneda.nota).toContain('la naturaleza de la tasa no cambia')
  })

  it('respeta el orden en que el motor mandó las candidatas', () => {
    const primera = candidata({ destino: { ticker: 'GD30D' } })
    const segunda = candidata({ origen: { ticker: 'GD30D', duracion: 5.8, volumen_usd: 300_000 }, destino: { ticker: 'AL30D', duracion: 3.5, volumen_usd: 100_000 } })
    const posiciones: PosicionConPeso[] = [
      { ticker: 'AL30D', peso: 50 },
      { ticker: 'GD30D', peso: 50 },
    ]
    const concentraciones = new Map<string, Concentracion | null>([
      [claveCandidata(primera), concentracion(100)],
      [claveCandidata(segunda), concentracion(100)],
    ])
    const resultado = evaluarSubirTir(
      [primera, segunda],
      vectorActualBase(concentracion(100), PORTICKER_BASE, posiciones),
      posiciones,
      PORTICKER_BASE,
      concentraciones,
    )

    expect(resultado.propuestas.map((p) => p.candidata.destino.ticker)).toEqual(['GD30D', 'AL30D'])
  })
})
