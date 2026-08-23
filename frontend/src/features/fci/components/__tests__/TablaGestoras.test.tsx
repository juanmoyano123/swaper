/**
 * `TablaGestoras` — F-067. El AUM por gestora nunca cruza monedas, y el flujo neto se muestra
 * siempre declarado como no disponible en vez de omitirse.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { TablaGestoras } from '../TablaGestoras'

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
      <TablaGestoras />
    </QueryClientProvider>,
  )
}

const MOTIVO_FLUJO_NETO =
  'requiere acumular planillas diarias; el producto no acumula series históricas (decisión del 23/08/2026)'

it('el flujo neto se muestra declarado como no disponible, nunca se omite', async () => {
  mockearFetch({
    gestoras: [
      {
        gerente: 'Gainvest S.A.',
        cantidad_fondos: 1,
        por_moneda: [{ moneda: 'ARS', aum: 1_000_000, cantidad_fondos: 1 }],
        market_share: 1.2,
        flujo_neto: { disponible: false, motivo: MOTIVO_FLUJO_NETO },
      },
    ],
  })
  renderizar()

  expect(await screen.findByText('Gainvest S.A.')).toBeInTheDocument()
  const flujoNeto = await screen.findByText(/Flujo neto: no disponible/)
  expect(flujoNeto).toHaveTextContent(MOTIVO_FLUJO_NETO)
})

it('el AUM de una gestora con fondos en dos monedas se muestra separado, nunca sumado', async () => {
  mockearFetch({
    gestoras: [
      {
        gerente: 'Delta S.A.',
        cantidad_fondos: 2,
        por_moneda: [
          { moneda: 'ARS', aum: 1_000_000, cantidad_fondos: 1 },
          { moneda: 'USB', aum: 500_000, cantidad_fondos: 1 },
        ],
        market_share: null,
        flujo_neto: { disponible: false, motivo: MOTIVO_FLUJO_NETO },
      },
    ],
  })
  renderizar()

  expect(await screen.findByText(/ARS:/)).toBeInTheDocument()
  expect(await screen.findByText(/USB:/)).toBeInTheDocument()
  expect(screen.queryByText(/1\.500\.000/)).not.toBeInTheDocument()
})

it('un gerente no informado se muestra como "sin gestora informada"', async () => {
  mockearFetch({
    gestoras: [
      {
        gerente: null,
        cantidad_fondos: 1,
        por_moneda: [{ moneda: 'ARS', aum: 100_000, cantidad_fondos: 1 }],
        market_share: null,
        flujo_neto: { disponible: false, motivo: MOTIVO_FLUJO_NETO },
      },
    ],
  })
  renderizar()

  expect(await screen.findByText('sin gestora informada')).toBeInTheDocument()
})
