/**
 * `useArmadoAsistido` — F-019. Mock de `fetch` directo, mismo patrón que `useCargarLamina.test.ts`
 * (F-025): lo que importa acá es el contrato con `apiFetch` y que el éxito reemplace la cartera del
 * store, no el render de un panel.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { useArmadoAsistido } from '../hooks/useArmadoAsistido'
import { ArmadorProvider, useArmador } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockFetch(status: number, cuerpo: unknown) {
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(
      QueryClientProvider,
      { client: cliente },
      createElement(ArmadorProvider, null, children),
    )
}

const RESULTADO_OK = {
  posiciones: [
    { ticker: 'GD35', pct_cartera: 60, monto: 60000, clase: 'renta_fija' },
    { ticker: 'AL30', pct_cartera: 40, monto: 40000, clase: 'renta_fija' },
  ],
  mix_aplicado: { usd_hard: 100 },
  origen_mix: 'cobertura devaluacion',
  perfil: 'moderado',
  sectores: { presentes: 2, minimo: 3, suficiente: false },
  pct_rv_aplicado: 0,
  alertas: [
    {
      codigo: 'diversificacion_sectorial_insuficiente',
      mensaje: 'la cartera tiene 2 sectores y el perfil pide al menos 3',
      severidad: 'advertencia',
      accion_requerida: null,
      detalle: {},
    },
  ],
}

describe('useArmadoAsistido', () => {
  it('en éxito, reemplaza la cartera del store con las posiciones mapeadas', async () => {
    mockFetch(200, RESULTADO_OK)
    const cliente = crearQueryClient()

    const { result } = renderHook(
      () => ({ mutacion: useArmadoAsistido(), armador: useArmador() }),
      { wrapper: envolver(cliente) },
    )

    await act(async () => {
      await result.current.mutacion.mutateAsync({
        monto: 100_000,
        moneda: 'usd',
        cobertura: 'devaluacion',
        perfil: 'moderado',
        horizonte: 'medio',
      })
    })

    expect(result.current.armador.pos).toEqual([
      { ticker: 'GD35', peso: 60, clase: 'renta_fija' },
      { ticker: 'AL30', peso: 40, clase: 'renta_fija' },
    ])
  })

  it('reemplaza la cartera aunque ya hubiera posiciones cargadas -- es un punto de partida', async () => {
    mockFetch(200, RESULTADO_OK)
    const cliente = crearQueryClient()

    const { result } = renderHook(
      () => ({ mutacion: useArmadoAsistido(), armador: useArmador() }),
      { wrapper: envolver(cliente) },
    )

    await act(async () => {
      await result.current.mutacion.mutateAsync({
        monto: 50_000,
        moneda: 'todas',
        cobertura: 'mixta',
        perfil: 'conservador',
        horizonte: 'corto',
      })
    })

    expect(result.current.armador.pos).toHaveLength(2)
  })

  it('un 500 real se propaga como error de la mutación', async () => {
    mockFetch(500, { error: { code: 'internal_error', message: 'boom' } })
    const cliente = crearQueryClient()

    const { result } = renderHook(
      () => ({ mutacion: useArmadoAsistido(), armador: useArmador() }),
      { wrapper: envolver(cliente) },
    )

    await act(async () => {
      await result.current.mutacion
        .mutateAsync({
          monto: 100_000,
          moneda: 'todas',
          cobertura: 'mixta',
          perfil: 'moderado',
          horizonte: 'medio',
        })
        .catch(() => undefined)
    })

    // `mutateAsync().catch()` resuelve antes de que React confirme el estado de la mutación
    // (mismo patrón que `useCargarLamina.test.ts`): se espera el estado, no se lo asume resuelto
    // apenas la promesa se asienta.
    await waitFor(() => expect(result.current.mutacion.isError).toBe(true))
    expect(result.current.armador.pos).toEqual([])
  })

  it('respeta la clase que manda el backend: una acción no entra como bono', async () => {
    // Tanda 13: el armado asistido también elige acciones. Antes se forzaba `renta_fija` en todas,
    // y una acción marcada así habría entrado al resolver de bonos y salido con nominales sin
    // sentido — se compra por unidad entera, no por lámina.
    mockFetch(200, {
      ...RESULTADO_OK,
      posiciones: [
        { ticker: 'GD35', pct_cartera: 75, monto: 75000, clase: 'renta_fija' },
        { ticker: 'GGAL', pct_cartera: 25, monto: 25000, clase: 'renta_variable' },
      ],
      pct_rv_aplicado: 25,
    })
    const cliente = crearQueryClient()

    const { result } = renderHook(
      () => ({ mutacion: useArmadoAsistido(), armador: useArmador() }),
      { wrapper: envolver(cliente) },
    )

    await act(async () => {
      await result.current.mutacion.mutateAsync({
        monto: 100_000,
        moneda: 'usd',
        cobertura: 'mixta',
        perfil: 'moderado',
        horizonte: 'medio',
        pct_rv: 25,
      })
    })

    expect(result.current.armador.pos).toEqual([
      { ticker: 'GD35', peso: 75, clase: 'renta_fija' },
      { ticker: 'GGAL', peso: 25, clase: 'renta_variable' },
    ])
  })
})
