/**
 * El contrato de los dos endpoints que consume el monitor — F-038.
 *
 * Igual que el resto de la API, un campo faltante tiene que fallar fuerte (`contract_mismatch`) y
 * no dejar pasar una especie a medias: una fila financiera incompleta es peor que ninguna fila.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { apiFetch } from '@/lib/api/client'
import { ApiError } from '@/lib/api/errors'
import { esquemaPagina } from '@/lib/api/schemas'

import { esquemaEspecie, esquemaSegmentos } from '../lib/schema'

function especieValida(): Record<string, unknown> {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    subtipo: 'global',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.1,
    duracion: 2.5,
    vencimiento: '2030-07-09',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'Tesoro Nacional',
    precio: 62.5,
    moneda_cotizacion: 'USD',
    volumen: 1_000_000,
    volumen_usd: 1_000_000,
    paridad: 0.875,
    residual: 100.0,
    valor_tecnico: 71.4,
    sector: null,
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    fuente: null,
    capturado_en: '2026-08-30T20:00:02.098529+00:00',
  }
}

function respuestaJson(cuerpo: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    ),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('el contrato de la vista viva', () => {
  it('acepta una especie con todos los campos', async () => {
    respuestaJson({ items: [especieValida()], next_cursor: null })

    await expect(apiFetch('/api/v1/x', esquemaPagina(esquemaEspecie))).resolves.toEqual({
      items: [especieValida()],
      next_cursor: null,
    })
  })

  it('un campo faltante falla fuerte con contract_mismatch, no con una fila a medias', async () => {
    const { paridad: _paridad, ...sinParidad } = especieValida()
    respuestaJson({ items: [sinParidad], next_cursor: null })

    const error = (await apiFetch('/api/v1/x', esquemaPagina(esquemaEspecie)).catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('contract_mismatch')
  })
})

describe('el contrato de /segmentos', () => {
  it('un segmento sin su conteo falla fuerte con contract_mismatch', async () => {
    respuestaJson({
      segmentos: [{ clave: 'usd_hard', nombre: 'Hard dollar', naturaleza: 'tir_usd', naturaleza_nombre: 'TIR en dólares' }],
      renta_variable: 1417,
      sin_segmento: 535,
    })

    const error = (await apiFetch('/api/v1/x', esquemaSegmentos).catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('contract_mismatch')
  })
})
