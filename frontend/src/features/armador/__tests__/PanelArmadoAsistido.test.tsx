/**
 * `PanelArmadoAsistido` — F-019. Mock de `fetch` directo, mismo patrón que
 * `useArmadoAsistido.test.ts`: lo que importa acá es que el formulario mande los cinco parámetros
 * del mandato y que las alertas de la respuesta se muestren.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelArmadoAsistido } from '../components/PanelArmadoAsistido'
import { ArmadorProvider, useArmador } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockFetch(status: number, cuerpo: unknown) {
  const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function CarteraVisible() {
  const { pos, montoTotal } = useArmador()
  return (
    <>
      <p data-testid="cartera">{pos.map((p) => `${p.ticker}:${p.peso}`).join(',')}</p>
      <p data-testid="montoTotal">{montoTotal}</p>
    </>
  )
}

function renderizar() {
  const cliente = crearQueryClient()
  return render(
    createElement(
      QueryClientProvider,
      { client: cliente },
      createElement(ArmadorProvider, null, createElement(PanelArmadoAsistido), createElement(CarteraVisible)),
    ),
  )
}

const RESULTADO_OK = {
  posiciones: [
    { ticker: 'GD35', pct_cartera: 70, monto: 70000 },
    { ticker: 'AL30', pct_cartera: 30, monto: 30000 },
  ],
  mix_aplicado: { usd_hard: 100 },
  origen_mix: 'cobertura devaluacion',
  perfil: 'moderado',
  sectores: { presentes: 2, minimo: 3, suficiente: false },
  alertas: [
    {
      codigo: 'diversificacion_sectorial_insuficiente',
      mensaje: 'la cartera tiene 2 sectores y el perfil pide al menos 3',
      severidad: 'advertencia',
      accion_requerida: null,
      detalle: {},
    },
  ],
}

describe('PanelArmadoAsistido', () => {
  it('envía los cinco parámetros del mandato al pedir el armado', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.selectOptions(screen.getByLabelText('Moneda de referencia'), 'usd')
    await userEvent.selectOptions(screen.getByLabelText('Objetivo de cobertura'), 'devaluacion')
    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'conservador')
    await userEvent.selectOptions(screen.getByLabelText('Horizonte'), 'largo')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toContain('/api/v1/armado')
    expect(JSON.parse(init?.body as string)).toEqual({
      monto: 100000,
      moneda: 'usd',
      cobertura: 'devaluacion',
      perfil: 'conservador',
      horizonte: 'largo',
    })
  })

  it('en éxito, precarga la cartera y muestra las alertas de la respuesta', async () => {
    mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    await waitFor(() =>
      expect(screen.getByTestId('cartera')).toHaveTextContent('GD35:70,AL30:30'),
    )
    expect(
      screen.getByText('la cartera tiene 2 sectores y el perfil pide al menos 3'),
    ).toBeInTheDocument()
  })

  it('el botón queda deshabilitado sin un monto válido', () => {
    renderizar()

    expect(screen.getByRole('button', { name: 'Armar cartera asistida' })).toBeDisabled()
  })

  it('el monto del asistido es el mismo capital que reparte la cartera, no un campo aparte', async () => {
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '80000')

    // Escribir acá mueve el `montoTotal` del store, que es el que usan los resolvers para
    // calcular nominales: antes eran dos números sin relación y cargar el capital en esta ficha
    // no cambiaba nada de lo que se veía más abajo.
    expect(screen.getByTestId('montoTotal')).toHaveTextContent('80000')
  })
})
