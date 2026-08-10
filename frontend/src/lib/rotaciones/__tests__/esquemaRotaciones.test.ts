/**
 * F-033 — el contrato de `POST /rotaciones` tiene que tolerar el bloque `costo` que F-035 le
 * agrega en paralelo (tanda 13, mismo commit de base) sin declararlo: es la prueba de que el modo
 * strip por defecto de Zod no rompe el parseo exista o no ese campo todavía.
 */

import { describe, expect, it } from 'vitest'

import { esquemaRotaciones } from '../esquemaRotaciones'

function especie(extra: Record<string, unknown> = {}) {
  return {
    ticker: 'AL30D',
    emisor: 'República Argentina',
    rendimiento: 0.11,
    duracion: 3.5,
    moneda_cupon: 'USD',
    ley: 'Ley N.Y.',
    calificacion: null,
    lamina: 1,
    frecuencia_cupon: 'semestral',
    volumen_usd: 100_000,
    ...extra,
  }
}

function candidata(extra: Record<string, unknown> = {}) {
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: especie({ ticker: 'AL30D' }),
    destino: especie({ ticker: 'GD30D' }),
    delta: { rendimiento_pp: 0.3, duracion: 0.1 },
    flags: {
      mismo_emisor: true,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    ...extra,
  }
}

function respuesta(extra: Record<string, unknown> = {}) {
  return {
    perfil: 'moderado',
    candidatas: [candidata()],
    origenes_evaluados: ['AL30D'],
    fuera_del_universo: [],
    sin_rendimiento: [],
    alertas: [
      {
        codigo: 'costo_rotacion_no_calculado',
        mensaje: 'El costo real de rotar todavía no se calcula.',
        severidad: 'info',
        accion_requerida: null,
        detalle: {},
      },
    ],
    ...extra,
  }
}

describe('esquemaRotaciones', () => {
  it('parsea la respuesta real del backend', () => {
    const resultado = esquemaRotaciones.safeParse(respuesta())
    expect(resultado.success).toBe(true)
  })

  it('tolera un bloque "costo" no declarado en cada candidata (F-035, en paralelo)', () => {
    const conCosto = respuesta({
      candidatas: [
        candidata({
          costo: { arancel_pp: 0.05, spread_pp: 0.1, payback_dias: 40 },
        }),
      ],
    })
    const resultado = esquemaRotaciones.parse(conCosto)
    expect(resultado.candidatas[0]).not.toHaveProperty('costo')
  })

  it('tolera "cupon" con o sin el campo "fecha" al no declararse en el esquema', () => {
    const conCupon = respuesta({
      candidatas: [candidata({ cupon: { dias: 10, pct: 0.02, nota: null, fecha: '2026-09-01' } })],
    })
    expect(esquemaRotaciones.safeParse(conCupon).success).toBe(true)
  })
})
