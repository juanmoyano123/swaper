/**
 * El panel "Estados contables · SEC" de la ficha de renta variable (14/08/2026) — el cuarto bloque
 * de F-053, sólo para CEDEARs.
 *
 * Archivo aparte de `FichaRentaVariable.test.tsx` a propósito: ese ya es el más pesado de la
 * carpeta, y estos casos son todos del mismo bloque. Mismo andamiaje de mocking que el resto de la
 * carpeta — `fetch` mockeado por ruta exacta, sin sesión de Supabase.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { FichaDelActivo } from '../FichaDelActivo'
import type {
  BloqueHistorico,
  BloquePropio,
  BloqueSec,
  FichaRentaVariable as Ficha,
  RatioSec,
  RatiosSec,
} from '../lib/schemaRentaVariable'

afterEach(() => {
  vi.unstubAllGlobals()
})

const TICKER = 'AAPL'
const RUTA_RV = (t: string) => `/api/v1/renta-variable/${t}/ficha`

function propio(extra: Partial<BloquePropio> = {}): BloquePropio {
  return {
    fuente: 'BYMA',
    ticker: TICKER,
    clase_activo: 'cedear',
    precio: 43000,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 42000,
    variacion: 0.0238,
    volumen: 2_000_000,
    volumen_usd: 2_000_000,
    px_bid: 42900,
    px_ask: 43100,
    operaciones: 30,
    precio_apertura: 42500,
    precio_maximo: 43200,
    precio_minimo: 42400,
    vwap: 42950,
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    ...extra,
  }
}

function historicoVacio(): BloqueHistorico {
  return { fuente: 'data912', disponible: false, motivo: 'sin serie para este símbolo', puntos: [] }
}

function ratio(extra: Partial<RatioSec> = {}): RatioSec {
  return { valor: 0.4, unidad: null, periodo: '2025-09-27', ...extra }
}

function ratios(extra: Partial<RatiosSec> = {}): RatiosSec {
  return {
    roe: ratio({ valor: 0.4 }),
    margen_operativo: ratio({ valor: 0.32 }),
    crecimiento_ingresos: ratio({ valor: 0.18 }),
    eps: ratio({ valor: 1.25, unidad: 'USD/shares' }),
    deuda_patrimonio: ratio({ valor: 0.8 }),
    liquidez_corriente: ratio({ valor: 2.0 }),
    ...extra,
  }
}

function sec(extra: Partial<BloqueSec> = {}): BloqueSec {
  return {
    fuente: 'SEC EDGAR',
    disponible: true,
    motivo_ausente: null,
    solo_anual: false,
    nota_solo_anual: null,
    cik: '320193',
    filings: [
      { form: '10-K', fecha: '2025-10-31', url_documento: 'https://www.sec.gov/aapl-10k.htm' },
      { form: '10-Q', fecha: '2025-08-01', url_documento: 'https://www.sec.gov/aapl-10q.htm' },
    ],
    ratios: ratios(),
    ...extra,
  }
}

function fichaRV(extra: Partial<Ficha> = {}): Ficha {
  return {
    ticker: TICKER,
    propio: propio(),
    historico: historicoVacio(),
    sec: sec(),
    ...extra,
  }
}

function mockearRuta(body: unknown) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url !== RUTA_RV(TICKER)) throw new Error(`ruta no mockeada en el test: ${url}`)
    return Promise.resolve(
      new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar() {
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <FichaDelActivo ticker={TICKER} />
    </QueryClientProvider>,
  )
}

it('un filer doméstico trimestral muestra los seis ratios con su período y los filings como links', async () => {
  mockearRuta(fichaRV())
  renderizar()

  expect(await screen.findByText('Estados contables · SEC EDGAR')).toBeInTheDocument()
  expect(screen.getByText('40,00%')).toBeInTheDocument() // ROE
  expect(screen.getByText('32,00%')).toBeInTheDocument() // margen operativo
  expect(screen.getByText('18,00%')).toBeInTheDocument() // crecimiento de ingresos
  expect(screen.getByText('0,80x')).toBeInTheDocument() // deuda/patrimonio
  expect(screen.getByText('2,00x')).toBeInTheDocument() // liquidez corriente
  expect(screen.getByText('USD/shares')).toBeInTheDocument() // EPS con su unidad, nunca pelado
  expect(screen.getAllByText('27/09/2025').length).toBeGreaterThan(0) // período de cada ratio

  const linkAnual = screen.getByRole('link', { name: /10-K/ })
  expect(linkAnual).toHaveAttribute('href', 'https://www.sec.gov/aapl-10k.htm')
  expect(linkAnual).toHaveAttribute('target', '_blank')
  expect(linkAnual).toHaveAttribute('rel', expect.stringContaining('noopener'))
  expect(screen.getByRole('link', { name: /10-Q/ })).toBeInTheDocument()
})

it('un FPI sólo-anual muestra la nota explícita antes de los ratios', async () => {
  mockearRuta(
    fichaRV({
      sec: sec({
        solo_anual: true,
        nota_solo_anual:
          'Esta empresa reporta ante la SEC como emisor privado extranjero: sus estados sólo se ' +
          'publican con detalle anual, sin trimestral consistente.',
      }),
    }),
  )
  renderizar()

  expect(await screen.findByText(/emisor privado extranjero/)).toBeInTheDocument()
})

it('un banco FPI sin margen operativo, EPS ni crecimiento los muestra ausentes sin romper el resto', async () => {
  mockearRuta(
    fichaRV({
      sec: sec({
        ratios: ratios({ margen_operativo: null, crecimiento_ingresos: null, eps: null }),
      }),
    }),
  )
  renderizar()

  expect(await screen.findByText('Margen operativo')).toBeInTheDocument()
  // ROE y deuda/patrimonio siguen calculándose: que falten otros ratios no los afecta.
  expect(screen.getByText('40,00%')).toBeInTheDocument()
  expect(screen.getByText('0,80x')).toBeInTheDocument()
  expect(screen.getAllByText('s/d').length).toBeGreaterThan(0)
})

it('un ticker que no es CEDEAR muestra el panel con el motivo declarado, sin ratios', async () => {
  mockearRuta(
    fichaRV({
      propio: propio({ clase_activo: 'accion' }),
      sec: sec({
        disponible: false,
        motivo_ausente: 'no es un CEDEAR: el paquete de estados contables sólo cubre CEDEARs',
        solo_anual: false,
        cik: null,
        filings: [],
        ratios: null,
      }),
    }),
  )
  renderizar()

  expect(await screen.findByText('Estados contables · SEC EDGAR')).toBeInTheDocument()
  expect(screen.getByText(/no es un CEDEAR/)).toBeInTheDocument()
  expect(screen.queryByText('ROE')).not.toBeInTheDocument()
})

it('un backend anterior sin la clave sec no rompe el resto de la ficha', async () => {
  const { sec: _sec, ...sinSec } = fichaRV()
  mockearRuta(sinSec)
  renderizar()

  expect((await screen.findAllByText('43.000,00')).length).toBeGreaterThan(0)
  expect(screen.queryByText('Estados contables · SEC EDGAR')).not.toBeInTheDocument()
})
