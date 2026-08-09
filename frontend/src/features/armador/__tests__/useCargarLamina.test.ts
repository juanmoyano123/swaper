/**
 * `useCargarLamina` — F-025. Mock de `fetch` directo (patrón de `CarteraEditable.test.tsx`), sin
 * montar componentes: lo que importa acá es el contrato con `apiFetch`/`ApiError`, no el render.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { useCargarLamina } from '../hooks/useCargarLamina'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockFetch(status: number, cuerpo: unknown) {
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: cliente }, children)
}

describe('useCargarLamina', () => {
  it('en éxito, invalida la query del universo entero', async () => {
    mockFetch(200, {
      guardado: true,
      ticker: 'AL30',
      lamina: 100,
      lamina_origen: 'carga manual',
      lamina_fecha: '2026-08-08',
    })
    const cliente = crearQueryClient()
    const invalidar = vi.spyOn(cliente, 'invalidateQueries')

    const { result } = renderHook(() => useCargarLamina(), { wrapper: envolver(cliente) })

    let resultado: unknown
    await act(async () => {
      resultado = await result.current.mutateAsync({ ticker: 'AL30', valor: 100 })
    })

    expect(invalidar).toHaveBeenCalledWith({ queryKey: ['mercado', 'universo', 'todas'] })
    expect(resultado).toEqual({ guardado: true, lamina: 100 })
  })

  it('en 409, expone el conflicto en vez de lanzar una excepción no manejada', async () => {
    mockFetch(409, {
      guardado: false,
      ticker: 'AL30',
      conflicto: { campo: 'lamina', emision: 'AL30', valores: { AL30: 1000, AL30D: 500 } },
    })
    const cliente = crearQueryClient()
    const invalidar = vi.spyOn(cliente, 'invalidateQueries')

    const { result } = renderHook(() => useCargarLamina(), { wrapper: envolver(cliente) })

    const resultado = await act(async () => result.current.mutateAsync({ ticker: 'AL30', valor: 1000 }))

    expect(result.current.isError).toBe(false)
    expect(resultado).toEqual({
      guardado: false,
      conflicto: { campo: 'lamina', emision: 'AL30', valores: { AL30: 1000, AL30D: 500 } },
    })
    // Un conflicto no propaga la lámina: nada que refrescar en el universo.
    expect(invalidar).not.toHaveBeenCalled()
  })

  it('un 500 real sigue propagándose como error de la mutación', async () => {
    mockFetch(500, { error: { code: 'internal_error', message: 'boom' } })
    const cliente = crearQueryClient()

    const { result } = renderHook(() => useCargarLamina(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current.mutateAsync({ ticker: 'AL30', valor: 100 }).catch(() => undefined)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})
