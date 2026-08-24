/**
 * El enlace a la "COMPOSICIÓN DE CARTERA" pública de la CNV en la ficha de un FCI.
 *
 * Mismo andamiaje que `FichaRentaVariable.test.tsx`: `fetch` mockeado con `vi.stubGlobal`
 * despachando por ruta exacta.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { crearQueryClient } from '@/app/queryClient'

import { FichaFciContenido } from '../FichaFciContenido'

afterEach(() => {
  vi.unstubAllGlobals()
})

const CODIGO_CAFCI = '1031'
const RUTA_FICHA = `/api/v1/fci/${CODIGO_CAFCI}/ficha`

const FONDO_BASE = {
  codigo_cafci: CODIGO_CAFCI,
  fondo: 'Gainvest Renta Variable - Clase A',
  codigo_cnv: '500',
  seccion: 'Renta Variable Peso Argentina',
  tipo_renta: 'renta_variable',
  naturaleza: 'variacion_cuotaparte',
  naturaleza_nombre: 'Variación de cuotaparte',
  moneda: 'ARS',
  region: 'Arg',
  horizonte: 'Lar',
  fecha_vcp: '2026-08-21',
  vcp: 1500,
  vcp_anterior: 1490,
  var_diaria_pct: 0.67,
  var_mes_pct: 5.2,
  var_anio_pct: 40.1,
  var_12m_pct: 55.3,
  cuotapartes: 100,
  cuotapartes_anterior: 99,
  patrimonio: 10_000_000,
  patrimonio_anterior: 9_900_000,
  market_share: 1.2,
  gerente: 'Gainvest S.A.',
  depositaria: 'Banco X',
  calificacion: 'EF-3',
  calificado: 'Si',
  tipo_dinero: 'Ahorro',
  comision_ingreso: 0,
  honorarios_adm_sg: 2,
  honorarios_adm_sd: 0.3,
  gastos_ord_gestion: 0.1,
  comision_rescate: 0,
  comision_transferencia: 0,
  honorarios_exito: 0,
  moneda_fondo: 'ARS',
  discrepancia_moneda: false,
  plazo_liq: 1,
  dias_para_rescatar: 1,
  minimo_inversion: 1000,
  advertencia_distribucion: 'Los rendimientos... sin distribuciones.',
}

function mockearFicha(body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      if (url !== RUTA_FICHA) throw new Error(`ruta no mockeada en el test: ${url}`)
      return Promise.resolve(
        new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
      )
    }),
  )
}

function renderizar() {
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <FichaFciContenido codigoCafci={CODIGO_CAFCI} />
    </QueryClientProvider>,
  )
}

it('con enlace mapeado muestra el botón con el href y target correctos', async () => {
  mockearFicha({
    ...FONDO_BASE,
    enlace_composicion_cnv: 'https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/63918',
  })
  renderizar()

  const link = await screen.findByRole('link', { name: /Composición de cartera en CNV/ })
  expect(link).toHaveAttribute(
    'href',
    'https://www.cnv.gov.ar/SitioWeb/FondosComunesInversion/DetallesFCI/63918',
  )
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noopener noreferrer')
})

it('sin enlace mapeado declara que está pendiente de curación, sin ofrecer un link inventado', async () => {
  mockearFicha({ ...FONDO_BASE, enlace_composicion_cnv: null })
  renderizar()

  expect(
    await screen.findByText(/pendiente de curación/),
  ).toBeInTheDocument()
  expect(screen.queryByRole('link', { name: /Composición de cartera en CNV/ })).not.toBeInTheDocument()
})
