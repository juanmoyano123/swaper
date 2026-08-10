/**
 * El contrato de `POST /rotaciones` (F-032), con el bloque `costo` de F-035 ya declarado desde
 * F-034 (tanda 14) y `cupon` todavía tolerado sin declarar por el modo strip de Zod.
 *
 * El shape del costo sale de `backend/app/rotaciones/costos.py` (`CostoRotacion.como_dict()`),
 * leído directamente: las dos formas que emite el backend —verificable y no verificable— se
 * parsean acá, porque la diferencia entre las dos es lo que la UI tiene que declarar (un costo sin
 * puntas vivas no es cero, es no verificable).
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

/** El costo tal como lo emite `calcular_costo` cuando las dos patas tienen puntas vivas. */
function costoVerificable(extra: Record<string, unknown> = {}) {
  return {
    arancel_pct_por_pata: 0.75,
    spread_origen_pct: 1.2,
    spread_destino_pct: 0.8,
    total_pct: 2.5,
    verificable: true,
    elevado: false,
    payback_meses: 16.7,
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
    costo: costoVerificable(),
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
        codigo: 'percentil_liquidez_no_aplica',
        mensaje: 'El segmento tiene menos destinos operables que el mínimo para el percentil.',
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

  it('parsea el costo verificable de F-035 y lo deja llegar a la UI', () => {
    const resultado = esquemaRotaciones.parse(respuesta())
    expect(resultado.candidatas[0].costo).toEqual(costoVerificable())
  })

  it('parsea el costo no verificable sin convertir los faltantes en ceros', () => {
    // Falta la punta del destino: el backend manda el arancel (constante conocida) y deja el total,
    // el flag de elevado y el payback en null. Que sobrevivan como null es la condición para que la
    // UI pueda declarar "no verificable" en vez de mostrar un costo inventado (regla 1).
    const sinPuntaDestino = costoVerificable({
      spread_destino_pct: null,
      total_pct: null,
      verificable: false,
      elevado: null,
      payback_meses: null,
    })
    const resultado = esquemaRotaciones.parse(respuesta({ candidatas: [candidata({ costo: sinPuntaDestino })] }))
    expect(resultado.candidatas[0].costo).toEqual(sinPuntaDestino)
  })

  it('acepta "costo" en null: el motor puede correr sin el servicio que resuelve puntas', () => {
    const resultado = esquemaRotaciones.parse(respuesta({ candidatas: [candidata({ costo: null })] }))
    expect(resultado.candidatas[0].costo).toBeNull()
  })

  it('rechaza una candidata sin la clave "costo" — el backend siempre la emite', () => {
    const { costo: _costo, ...sinCosto } = candidata()
    expect(esquemaRotaciones.safeParse(respuesta({ candidatas: [sinCosto] })).success).toBe(false)
  })

  it('tolera "cupon" con o sin el campo "fecha" al no declararse en el esquema', () => {
    const conCupon = respuesta({
      candidatas: [candidata({ cupon: { dias: 10, pct: 0.02, nota: null, fecha: '2026-09-01' } })],
    })
    expect(esquemaRotaciones.safeParse(conCupon).success).toBe(true)
  })
})
