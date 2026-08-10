/**
 * `useEfectoCalendario` — F-036. Verifica el cableado (dos POST a `/calendario/cartera`, una por
 * cartera) y el atajo de moneda no convertible; el criterio de diff en sí ya se prueba entero en
 * `lib/rotaciones/__tests__/efectoCalendario.test.ts`.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { crearQueryClient } from '@/app/queryClient'
import type { CalendarioUniverso } from '@/lib/cartera/esquemaCalendario'

import type { Candidata } from '../../esquemaRotaciones'
import { useEfectoCalendario } from '../useEfectoCalendario'

afterEach(() => {
  vi.unstubAllGlobals()
})

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: {
      ticker: origenTicker,
      emisor: 'X',
      rendimiento: 0.1,
      duracion: 3,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 100_000,
    },
    destino: {
      ticker: destinoTicker,
      emisor: 'X',
      rendimiento: 0.12,
      duracion: 4,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 200_000,
    },
    delta: { rendimiento_pp: 2, duracion: 1 },
    flags: {
      mismo_emisor: false,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'nota',
    costo: null,
  }
}

function calendarioCon(renta: Record<string, number>): CalendarioUniverso {
  return {
    resumen: {
      hoy: '2026-08-10',
      desde: '2026-08-10',
      hasta: '2027-07-10',
      con_montos: true,
      monedas: ['usd'],
      instrumentos: 1,
      meses_sin_renta: [],
      renta_anual: { usd: 0 },
      amortizacion_anual: { usd: 0 },
      pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses: [
      {
        anio: 2026,
        mes: 9,
        etiqueta: '2026-09',
        nombre: '2026-09',
        con_renta: renta.usd > 0 ? 1 : 0,
        con_amortizacion: 0,
        sin_renta: renta.usd === 0,
        renta,
        amortizacion: { usd: 0 },
        instrumentos: [],
      },
    ],
    alertas: [],
  }
}

function mockFetch() {
  const fetchMock = vi.fn((_entrada: RequestInfo | URL, init?: RequestInit) => {
    const cuerpo = JSON.parse((init?.body as string) ?? '{}')
    const tickers = (cuerpo.posiciones as { ticker: string }[]).map((p) => p.ticker)
    const respuesta = tickers.includes('B') ? calendarioCon({ usd: 50 }) : calendarioCon({ usd: 0 })
    return Promise.resolve(
      new Response(JSON.stringify(respuesta), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function envolver() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return ({ children }: { children: ReactNode }) => createElement(QueryClientProvider, { client: cliente }, children)
}

describe('useEfectoCalendario', () => {
  it('pide el calendario actual y el simulado, y declara el mes que se llena', async () => {
    const fetchMock = mockFetch()
    const { result } = renderHook(
      () => useEfectoCalendario([{ ticker: 'A', monto: 1000 }], candidata('A', 'B'), () => 'usd', null),
      { wrapper: envolver() },
    )

    await waitFor(() => expect(result.current.cargando).toBe(false))
    expect(result.current.efecto?.calculable).toBe(true)
    expect(result.current.efecto?.seLlenan).toEqual([{ etiqueta: '2026-09', nombre: '2026-09', moneda: 'usd' }])
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('sin tipo de cambio y monedas distintas, declara no calculable sin pedir el calendario simulado', async () => {
    mockFetch()
    const monedaDe = (ticker: string) => ticker === 'A' ? ('ars' as const) : ('usd' as const)
    const { result } = renderHook(
      () => useEfectoCalendario([{ ticker: 'A', monto: 1000 }], candidata('A', 'B'), monedaDe, null),
      { wrapper: envolver() },
    )

    await waitFor(() => expect(result.current.efecto).not.toBeNull())
    expect(result.current.efecto?.calculable).toBe(false)
    expect(result.current.efecto?.motivoNoCalculable).toContain('B')
  })
})
