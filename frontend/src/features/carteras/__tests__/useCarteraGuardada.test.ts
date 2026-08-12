import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

interface ResultadoMock {
  data: unknown
  error: { message: string } | null
}

let resultado: ResultadoMock = { data: null, error: null }

function crearBuilder() {
  const builder: Record<string, unknown> = {}
  builder.select = vi.fn(() => builder)
  builder.eq = vi.fn(() => builder)
  builder.single = vi.fn(() => Promise.resolve(resultado))
  return builder
}

const fromMock = vi.fn((_tabla: string) => crearBuilder())

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (tabla: string) => fromMock(tabla) },
}))

import { crearQueryClient } from '@/app/queryClient'

import { useCarteraGuardada } from '../hooks/useCarteraGuardada'

function envolver(cliente: ReturnType<typeof crearQueryClient>) {
  return ({ children }: { children: ReactNode }) =>
    createElement(QueryClientProvider, { client: cliente }, children)
}

const snapshotArmador = {
  version: 1,
  origen: 'armador',
  tipoDeCambio: 1050,
  montoTotalUsd: 10_000,
  posiciones: [],
  resueltas: [],
  totalInvertidoUsd: 9000,
}

afterEach(() => {
  vi.clearAllMocks()
})

describe('useCarteraGuardada', () => {
  it('trae la fila entera y valida el snapshot contra el schema', async () => {
    resultado = {
      data: {
        id: 'c1',
        nombre: 'x',
        descripcion: null,
        origen: 'armador',
        moneda_referencia: 'usd',
        monto: 9000,
        resumen: '1 posición',
        snapshot_en: '2026-08-10T12:00:00Z',
        snapshot: snapshotArmador,
      },
      error: null,
    }

    const { result } = renderHook(() => useCarteraGuardada('c1'), { wrapper: envolver(crearQueryClient()) })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.snapshot?.origen).toBe('armador')
  })

  it('un snapshot que no valida contra ningún schema se declara null, no rompe el detalle', async () => {
    resultado = {
      data: {
        id: 'c1',
        nombre: 'x',
        descripcion: null,
        origen: 'armador',
        moneda_referencia: 'usd',
        monto: 9000,
        resumen: '1 posición',
        snapshot_en: '2026-08-10T12:00:00Z',
        snapshot: { version: 99, algoDesconocido: true },
      },
      error: null,
    }

    const { result } = renderHook(() => useCarteraGuardada('c1'), { wrapper: envolver(crearQueryClient()) })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.snapshot).toBeNull()
    expect(result.current.data?.nombre).toBe('x')
  })

  it('no dispara la consulta con un id vacío', () => {
    renderHook(() => useCarteraGuardada(''), { wrapper: envolver(crearQueryClient()) })
    expect(fromMock).not.toHaveBeenCalled()
  })
})
