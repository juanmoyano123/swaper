/**
 * `TablaCategorias` — F-067. El caso testigo de toda la suite: un tipo de renta con fondos en
 * `ARS` y en `USD` nunca muestra un AUM único que las mezcle (regla 3).
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { TablaCategorias } from '../TablaCategorias'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockearFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar() {
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <TablaCategorias />
    </QueryClientProvider>,
  )
}

it('muestra el AUM roto por moneda y nunca un total que las mezcle', async () => {
  mockearFetch({
    categorias: [
      {
        tipo_renta: 'renta_variable',
        cantidad_fondos: 2,
        por_moneda: [
          {
            moneda: 'ARS',
            aum: 1_000_000,
            cantidad_fondos: 1,
            fondos: [{ codigo_cafci: '1', fondo: 'Fondo Uno', patrimonio: 1_000_000, participacion_pct: 100 }],
          },
          {
            moneda: 'USD',
            aum: 2_000_000,
            cantidad_fondos: 1,
            fondos: [{ codigo_cafci: '2', fondo: 'Fondo Dos', patrimonio: 2_000_000, participacion_pct: 100 }],
          },
        ],
      },
    ],
  })
  renderizar()

  expect(await screen.findByText(/ARS · AUM/)).toBeInTheDocument()
  expect(await screen.findByText(/USD · AUM/)).toBeInTheDocument()
  expect(screen.queryByText(/3\.000\.000/)).not.toBeInTheDocument()
})

it('un AUM ausente se declara s/d, no se muestra como cero', async () => {
  mockearFetch({
    categorias: [
      {
        tipo_renta: 'renta_fija',
        cantidad_fondos: 1,
        por_moneda: [
          {
            moneda: 'ARS',
            aum: null,
            cantidad_fondos: 1,
            fondos: [{ codigo_cafci: '1', fondo: 'Fondo Sin Patrimonio', patrimonio: null, participacion_pct: null }],
          },
        ],
      },
    ],
  })
  renderizar()

  expect(await screen.findByText(/ARS · AUM s\/d/)).toBeInTheDocument()
})

it('sin categorías declara que no hay fondos en la planilla de hoy', async () => {
  mockearFetch({ categorias: [] })
  renderizar()

  expect(await screen.findByText(/No hay fondos comunes en la planilla de hoy/)).toBeInTheDocument()
})
