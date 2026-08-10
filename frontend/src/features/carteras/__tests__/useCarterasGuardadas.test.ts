/**
 * `useCarterasGuardadas` — F-041. Mock del cliente de Supabase con un builder encadenable que
 * resuelve `{data, error}` al final de la cadena (`select().order()`), mismo criterio que el mock
 * de `fetch` de `useCargarLamina.test.ts` pero para PostgREST en vez de la API propia.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

interface ResultadoMock {
  data: unknown
  error: { message: string } | null
}

let resultado: ResultadoMock = { data: [], error: null }

function crearBuilder() {
  const builder: Record<string, unknown> = {}
  builder.select = vi.fn(() => builder)
  builder.order = vi.fn(() => builder)
  builder.then = (resolve: (v: ResultadoMock) => void, reject?: (e: unknown) => void) =>
    Promise.resolve(resultado).then(resolve, reject)
  return builder
}

const fromMock = vi.fn((_tabla: string) => crearBuilder())

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (tabla: string) => fromMock(tabla) },
}))

import { crearQueryClient } from '@/app/queryClient'

import { useCarterasGuardadas } from '../hooks/useCarterasGuardadas'

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: cliente }, children)
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useCarterasGuardadas', () => {
  it('parsea las filas del listado, ordenadas por fecha de snapshot', async () => {
    resultado = {
      data: [
        {
          id: 'c1',
          nombre: 'Renta USD · perfil moderado',
          descripcion: null,
          origen: 'cargada',
          moneda_referencia: 'usd',
          monto: 700,
          resumen: '1 posición',
          snapshot_en: '2026-08-10T12:00:00Z',
        },
      ],
      error: null,
    }

    const { result } = renderHook(() => useCarterasGuardadas(), { wrapper: envolver(crearQueryClient()) })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([
      {
        id: 'c1',
        nombre: 'Renta USD · perfil moderado',
        descripcion: null,
        origen: 'cargada',
        moneda_referencia: 'usd',
        monto: 700,
        resumen: '1 posición',
        snapshot_en: '2026-08-10T12:00:00Z',
      },
    ])
    expect(fromMock).toHaveBeenCalledWith('carteras')
  })

  it('un error de PostgREST se propaga declarado, no en silencio', async () => {
    resultado = { data: null, error: { message: 'permission denied for table carteras' } }

    const { result } = renderHook(() => useCarterasGuardadas(), { wrapper: envolver(crearQueryClient()) })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect((result.current.error as Error).message).toContain('permission denied')
  })
})
