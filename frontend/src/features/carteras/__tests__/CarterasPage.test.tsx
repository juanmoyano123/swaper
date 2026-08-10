import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
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

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (_tabla: string) => crearBuilder() },
}))

import { crearQueryClient } from '@/app/queryClient'

import { CarterasPage } from '../CarterasPage'

afterEach(() => {
  vi.clearAllMocks()
})

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={['/carteras']}>
        <Routes>
          <Route path="/carteras" element={<CarterasPage />} />
          <Route path="/carteras/:id" element={<div>detalle de la cartera</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CarterasPage', () => {
  it('sin carteras guardadas, muestra el estado vacío', async () => {
    resultado = { data: [], error: null }
    renderizar()
    expect(await screen.findByText('Todavía no hay carteras guardadas.')).toBeInTheDocument()
  })

  it('con carteras guardadas, muestra nombre, monto y resumen de cada una', async () => {
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
    renderizar()

    expect(await screen.findByText('Renta USD · perfil moderado')).toBeInTheDocument()
    expect(screen.getByText(/1 posición/)).toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Renta USD/ })).toHaveAttribute('href', '/carteras/c1')
  })

  it('un error de PostgREST se declara, no se esconde', async () => {
    resultado = { data: null, error: { message: 'permission denied' } }
    renderizar()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})
