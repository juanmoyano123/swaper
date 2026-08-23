/**
 * `Comparador` — F-067. Dos fondos de monedas distintas se muestran lado a lado tal cual, sin
 * convertir ni calcular una diferencia entre monedas (regla 3).
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { Comparador } from '../Comparador'

const RUTA_FONDOS = '/api/v1/fci/fondos?limit=200'

afterEach(() => {
  vi.unstubAllGlobals()
})

function fondo(extra: Record<string, unknown> = {}) {
  return {
    codigo_cafci: '1',
    fondo: 'Fondo Uno',
    codigo_cnv: null,
    seccion: 'Renta Variable Peso Argentina',
    tipo_renta: 'renta_variable',
    naturaleza: 'variacion_cuotaparte',
    naturaleza_nombre: 'Variación de cuotaparte',
    moneda: 'ARS',
    region: 'Arg',
    horizonte: 'Lar',
    fecha_vcp: '2026-08-21',
    vcp: 1500.0,
    vcp_anterior: 1490.0,
    var_diaria_pct: 0.67,
    var_mes_pct: 5.2,
    var_anio_pct: 40.1,
    var_12m_pct: 55.3,
    cuotapartes: 100.0,
    cuotapartes_anterior: 99.0,
    patrimonio: 1_000_000.0,
    patrimonio_anterior: 990_000.0,
    market_share: 1.2,
    gerente: 'Gainvest S.A.',
    depositaria: 'Banco X',
    calificacion: 'EF-3',
    calificado: 'Si',
    tipo_dinero: 'Ahorro',
    comision_ingreso: 0,
    honorarios_adm_sg: 2.0,
    honorarios_adm_sd: 0.3,
    gastos_ord_gestion: 0.1,
    comision_rescate: 0,
    comision_transferencia: 0,
    honorarios_exito: 0,
    moneda_fondo: 'ARS',
    discrepancia_moneda: false,
    plazo_liq: 1,
    dias_para_rescatar: 1,
    minimo_inversion: 1000.0,
    advertencia_distribucion: 'Los rendimientos no consideran distribución de utilidades.',
    ...extra,
  }
}

const FONDO_ARS = fondo({ codigo_cafci: '1', fondo: 'Fondo Pesos Uno', moneda: 'ARS', patrimonio: 1_000_000 })
const FONDO_USD = fondo({ codigo_cafci: '2', fondo: 'Fondo Dolares Dos', moneda: 'USD', patrimonio: 2_000_000 })

function mockearFetch(items: unknown[]) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith(RUTA_FONDOS)) {
      return Promise.resolve(
        new Response(JSON.stringify({ items, next_cursor: null }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }
    throw new Error(`ruta no mockeada en el test: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar() {
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <Comparador />
    </QueryClientProvider>,
  )
}

it('dos fondos de distinta moneda se muestran lado a lado sin convertir', async () => {
  mockearFetch([FONDO_ARS, FONDO_USD])
  const user = userEvent.setup()
  renderizar()

  const busqueda = await screen.findByPlaceholderText('Buscar fondo por nombre…')
  await user.type(busqueda, 'Fondo')

  await user.click(await screen.findByText(/Fondo Pesos Uno/))
  await user.type(await screen.findByPlaceholderText('Buscar fondo por nombre…'), 'Fondo')
  await user.click(await screen.findByText(/Fondo Dolares Dos/))

  const tabla = await screen.findByRole('table')
  expect(tabla).toHaveTextContent('Fondo Pesos Uno')
  expect(tabla).toHaveTextContent('Fondo Dolares Dos')
  expect(tabla).toHaveTextContent('ARS')
  expect(tabla).toHaveTextContent('USD')
  // Ningún valor convertido ni spread calculado entre las dos monedas.
  expect(tabla).not.toHaveTextContent('spread')
  expect(tabla).not.toHaveTextContent('diferencia')
})

it('con un solo fondo elegido pide elegir al menos dos', async () => {
  mockearFetch([FONDO_ARS, FONDO_USD])
  const user = userEvent.setup()
  renderizar()

  const busqueda = await screen.findByPlaceholderText('Buscar fondo por nombre…')
  await user.type(busqueda, 'Fondo')
  await user.click(await screen.findByText(/Fondo Pesos Uno/))

  expect(await screen.findByText(/Elegí al menos 2 fondos/)).toBeInTheDocument()
  expect(screen.queryByRole('table')).not.toBeInTheDocument()
})

it('se puede quitar un fondo ya elegido', async () => {
  mockearFetch([FONDO_ARS, FONDO_USD])
  const user = userEvent.setup()
  renderizar()

  const busqueda = await screen.findByPlaceholderText('Buscar fondo por nombre…')
  await user.type(busqueda, 'Fondo')
  await user.click(await screen.findByText(/Fondo Pesos Uno/))

  await user.click(await screen.findByLabelText('Quitar Fondo Pesos Uno de la comparación'))

  expect(await screen.findByText(/Elegí al menos 2 fondos/)).toBeInTheDocument()
})
