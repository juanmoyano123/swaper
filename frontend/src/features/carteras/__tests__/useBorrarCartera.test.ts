import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

interface ResultadoMock {
  error: { message: string } | null
}

let resultado: ResultadoMock = { error: null }

function crearBuilder() {
  const builder: Record<string, unknown> = {}
  builder.delete = vi.fn(() => builder)
  builder.eq = vi.fn(() => builder)
  builder.then = (resolve: (v: ResultadoMock) => void, reject?: (e: unknown) => void) =>
    Promise.resolve(resultado).then(resolve, reject)
  return builder
}

const fromMock = vi.fn((_tabla: string) => crearBuilder())

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (tabla: string) => fromMock(tabla) },
}))

import { crearQueryClient } from '@/app/queryClient'
import { claves } from '@/lib/api/queryKeys'

import { useBorrarCartera } from '../hooks/useBorrarCartera'

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: cliente }, children)
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useBorrarCartera', () => {
  it('en éxito, invalida el listado y saca el detalle del caché', async () => {
    resultado = { error: null }
    const cliente = crearQueryClient()
    const invalidar = vi.spyOn(cliente, 'invalidateQueries')
    const remover = vi.spyOn(cliente, 'removeQueries')

    const { result } = renderHook(() => useBorrarCartera(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current.mutateAsync('c1')
    })

    expect(invalidar).toHaveBeenCalledWith({ queryKey: claves.carteras.todas })
    expect(remover).toHaveBeenCalledWith({ queryKey: claves.carteras.detalle('c1') })
  })

  it('un error de PostgREST se propaga declarado', async () => {
    resultado = { error: { message: 'permission denied' } }
    const cliente = crearQueryClient()

    const { result } = renderHook(() => useBorrarCartera(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current.mutateAsync('c1').catch(() => undefined)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect((result.current.error as Error).message).toContain('permission denied')
  })
})
