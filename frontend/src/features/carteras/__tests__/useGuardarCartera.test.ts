import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

interface ResultadoMock {
  data: unknown
  error: { message: string } | null
}

let resultado: ResultadoMock = { data: { id: 'c1' }, error: null }
let ultimoInsert: unknown = null

function crearBuilder() {
  const builder: Record<string, unknown> = {}
  builder.insert = vi.fn((valores: unknown) => {
    ultimoInsert = valores
    return builder
  })
  builder.select = vi.fn(() => builder)
  builder.single = vi.fn(() => Promise.resolve(resultado))
  return builder
}

const fromMock = vi.fn((_tabla: string) => crearBuilder())

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (tabla: string) => fromMock(tabla) },
}))

import { crearQueryClient } from '@/app/queryClient'
import { claves } from '@/lib/api/queryKeys'

import { useGuardarCartera } from '../hooks/useGuardarCartera'

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: cliente }, children)
}

const snapshotCargada = {
  version: 1 as const,
  origen: 'cargada' as const,
  tipoDeCambio: 1050,
  perfil: 'moderado' as const,
  posiciones: [],
  valuadas: [],
  excluidas: [],
  totalInvertidoUsd: 700,
  plan: { aceptadas: [], descartadas: [] },
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useGuardarCartera', () => {
  it('inserta sin mandar user_id: lo completa PostgREST desde el JWT', async () => {
    resultado = { data: { id: 'c1' }, error: null }
    const cliente = crearQueryClient()

    const { result } = renderHook(() => useGuardarCartera(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current.mutateAsync({
        nombre: 'Renta USD',
        descripcion: null,
        origen: 'cargada',
        monedaReferencia: 'usd',
        monto: 700,
        resumen: '1 posición',
        snapshotEn: '2026-08-10T12:00:00Z',
        snapshot: snapshotCargada,
      })
    })

    expect(ultimoInsert).not.toHaveProperty('user_id')
    expect(ultimoInsert).toMatchObject({ nombre: 'Renta USD', origen: 'cargada', monto: 700 })
  })

  it('en éxito, invalida el listado de carteras', async () => {
    resultado = { data: { id: 'c1' }, error: null }
    const cliente = crearQueryClient()
    const invalidar = vi.spyOn(cliente, 'invalidateQueries')

    const { result } = renderHook(() => useGuardarCartera(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current.mutateAsync({
        nombre: 'x',
        descripcion: null,
        origen: 'cargada',
        monedaReferencia: 'usd',
        monto: 1,
        resumen: '1 posición',
        snapshotEn: '2026-08-10T12:00:00Z',
        snapshot: snapshotCargada,
      })
    })

    expect(invalidar).toHaveBeenCalledWith({ queryKey: claves.carteras.todas })
  })

  it('un error de PostgREST (ej. RLS) se propaga declarado', async () => {
    resultado = { data: null, error: { message: 'new row violates row-level security policy' } }
    const cliente = crearQueryClient()

    const { result } = renderHook(() => useGuardarCartera(), { wrapper: envolver(cliente) })

    await act(async () => {
      await result.current
        .mutateAsync({
          nombre: 'x',
          descripcion: null,
          origen: 'cargada',
          monedaReferencia: 'usd',
          monto: 1,
          resumen: '1 posición',
          snapshotEn: '2026-08-10T12:00:00Z',
          snapshot: snapshotCargada,
        })
        .catch(() => undefined)
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect((result.current.error as Error).message).toContain('row-level security')
  })
})
