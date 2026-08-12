import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
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

vi.mock('@/lib/supabase', () => ({
  supabase: { from: (_tabla: string) => crearBuilder() },
}))

import { crearQueryClient } from '@/app/queryClient'

import { GuardarCartera } from '../components/GuardarCartera'
import type { SnapshotCartera } from '../lib/esquemaSnapshot'

afterEach(() => {
  vi.clearAllMocks()
})

const snapshot: SnapshotCartera = {
  version: 1,
  origen: 'cargada',
  tipoDeCambio: 1050,
  perfil: 'moderado',
  posiciones: [],
  valuadas: [{ ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, pesoReal: 100 }],
  excluidas: [],
  totalInvertidoUsd: 700,
  plan: { aceptadas: [], descartadas: [] },
}

function renderizar() {
  const cliente = crearQueryClient()
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter>
        <GuardarCartera snapshot={snapshot} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('GuardarCartera', () => {
  it('sin nombre, el botón queda deshabilitado', () => {
    renderizar()
    expect(screen.getByRole('button', { name: 'Guardar cartera' })).toBeDisabled()
  })

  it('al guardar, no manda user_id y muestra el link al detalle', async () => {
    resultado = { data: { id: 'c1' }, error: null }
    const usuario = userEvent.setup()
    renderizar()

    await usuario.type(screen.getByLabelText('Nombre de la cartera'), 'Renta USD · perfil moderado')
    await usuario.click(screen.getByRole('button', { name: 'Guardar cartera' }))

    expect(await screen.findByText(/Cartera guardada\./)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Verla en Mis carteras/ })).toHaveAttribute('href', '/carteras/c1')
    expect(ultimoInsert).not.toHaveProperty('user_id')
    expect(ultimoInsert).toMatchObject({ nombre: 'Renta USD · perfil moderado', origen: 'cargada' })
  })

  it('un error de PostgREST (ej. RLS) se muestra, no se traga en silencio', async () => {
    resultado = { data: null, error: { message: 'new row violates row-level security policy' } }
    const usuario = userEvent.setup()
    renderizar()

    await usuario.type(screen.getByLabelText('Nombre de la cartera'), 'x')
    await usuario.click(screen.getByRole('button', { name: 'Guardar cartera' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('row-level security')
  })
})
