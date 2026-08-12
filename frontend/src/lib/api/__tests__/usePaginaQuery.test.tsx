/**
 * La colección paginada se recorre con el cursor tal como lo entrega el backend.
 *
 * Lo que se verifica de fondo es que el cliente nunca devuelva el conjunto completo de una: pide
 * una página, y la siguiente solo si se la piden.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'

import { crearQueryClient } from '@/app/queryClient'

import { usePaginaQuery } from '../usePaginaQuery'

const esquemaItem = z.object({ ticker: z.string() })

function envoltorio({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={crearQueryClient()}>{children}</QueryClientProvider>
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('usePaginaQuery', () => {
  it('trae la primera página y encadena el cursor sin interpretarlo', async () => {
    const urls: string[] = []
    const paginas = [
      { items: [{ ticker: 'AL30' }], next_cursor: 'eyJpZCI6MX0' },
      { items: [{ ticker: 'GD30' }], next_cursor: null },
    ]

    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        urls.push(url)
        const cuerpo = url.includes('cursor=') ? paginas[1] : paginas[0]
        return Promise.resolve(
          new Response(JSON.stringify(cuerpo), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )

    const { result } = renderHook(
      () =>
        usePaginaQuery({
          queryKey: ['prueba'],
          ruta: '/api/v1/instrumentos',
          esquemaItem,
          limit: 50,
        }),
      { wrapper: envoltorio },
    )

    await waitFor(() => expect(result.current.items).toHaveLength(1))
    // Primera página: sin cursor, y con el límite pedido. No se trajo la colección entera.
    expect(urls[0]).toContain('limit=50')
    expect(urls[0]).not.toContain('cursor=')
    expect(result.current.hayMas).toBe(true)

    result.current.cargarMas()

    await waitFor(() => expect(result.current.items).toHaveLength(2))
    // El cursor viaja exactamente como llegó: opaco, sin decodificar.
    expect(urls[1]).toContain('cursor=eyJpZCI6MX0')
    expect(result.current.items.map((i) => i.ticker)).toEqual(['AL30', 'GD30'])
    await waitFor(() => expect(result.current.hayMas).toBe(false))
  })
})
