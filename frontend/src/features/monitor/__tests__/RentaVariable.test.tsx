/**
 * Los GWT de F-052 (renta variable en el monitor) vistos desde la pantalla.
 *
 * Mismo patrón que `MonitorPage.test.tsx`: el segmento renta fija por defecto (`usd_hard`) trae
 * una sola especie mínima —hace falta para que la pestaña por defecto tenga algo que mostrar—, y
 * el foco de este archivo está en lo que pasa al activar la pestaña de acciones o CEDEARs.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import { MonitorPage } from '../MonitorPage'
import type { Especie } from '../lib/schema'

// jsdom no calcula layout: sin esto, `@tanstack/react-virtual` mide un contenedor de alto cero y
// no renderiza ninguna fila. El alto fijo espeja el `ALTO_CONTENEDOR` de `TablaRentaVariable`.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 520 })
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 800 })
})

afterAll(() => {
  Reflect.deleteProperty(HTMLElement.prototype, 'offsetHeight')
  Reflect.deleteProperty(HTMLElement.prototype, 'offsetWidth')
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function especieRentaFija(): Especie {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.1,
    duracion: 2.5,
    vencimiento: '2030-07-09',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'Tesoro Nacional',
    precio: 62.5,
    moneda_cotizacion: 'USD',
    volumen: 1_000_000,
    volumen_usd: 1_000_000,
    paridad: 0.875,
    dato_sano: true,
    hermanas: [],
  }
}

function especieRV(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  return {
    ticker: 'GGAL',
    clase_activo: 'accion',
    precio: 1000.0,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 950.0,
    variacion: (1000.0 - 950.0) / 950.0,
    volumen: 1_500_000_000,
    volumen_usd: 1_000_000,
    px_bid: 995.0,
    px_ask: 1005.0,
    operaciones: 50,
    ...extra,
  }
}

// GGAL en ARS: volumen crudo enorme pero volumen_usd de 1,0 MM. LOMA en USD: crudo y volumen_usd
// coinciden (2,0 MM), y son ~750 veces menores que el crudo de GGAL — es lo que prueba que el
// orden usa `volumen_usd` y no el nominal. PAMP no tiene cierre anterior ni puntas ni volumen USD:
// es el caso "cero" declarado en la nota de cobertura.
const GGAL = especieRV()
const LOMA = especieRV({
  ticker: 'LOMA',
  precio: 43.0,
  moneda_cotizacion: 'USD',
  cierre_anterior: 42.0,
  variacion: (43.0 - 42.0) / 42.0,
  volumen: 2_000_000,
  volumen_usd: 2_000_000,
  px_bid: 42.9,
  px_ask: 43.1,
  operaciones: 30,
})
const PAMP = especieRV({
  ticker: 'PAMP',
  precio: 500.0,
  cierre_anterior: null,
  variacion: null,
  volumen: 100_000,
  volumen_usd: null,
  px_bid: null,
  px_ask: null,
  operaciones: 5,
})

function respuestaJson(cuerpo: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  )
}

function pagina<T>(items: T[], next_cursor: string | null = null) {
  return { items, next_cursor }
}

function mockearApi() {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')

    if (url.pathname === '/api/v1/universo/segmentos') {
      return respuestaJson({
        segmentos: [
          {
            clave: 'usd_hard',
            nombre: 'Hard dollar',
            naturaleza: 'tir_usd',
            naturaleza_nombre: 'TIR en dólares (hard dollar)',
            especies: 1,
          },
        ],
        renta_variable: 3,
        sin_segmento: 535,
      })
    }

    if (url.pathname === '/api/v1/universo/emisiones/especies') {
      return respuestaJson(pagina([especieRentaFija()]))
    }

    if (url.pathname === '/api/v1/renta-variable/especies') {
      const clase = url.searchParams.get('clase')
      if (clase === 'accion') return respuestaJson(pagina([GGAL, LOMA, PAMP]))
      if (clase === 'cedear') return respuestaJson(pagina([]))
    }

    throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function FichaFalsa() {
  const { ticker } = useParams()
  return <div>ficha de {ticker}</div>
}

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={['/monitor']}>
        <Routes>
          <Route path="/monitor" element={<MonitorPage />} />
          <Route path="/instrumento/:ticker" element={<FichaFalsa />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function irALaPestanaDeAcciones() {
  const resultado = renderizar()
  await userEvent.click(await screen.findByRole('button', { name: 'Acciones' }))
  await screen.findByText('3 de 3 especies')
  return resultado
}

// --- GWT-1: columnas de renta variable, sin rendimiento ni nada en su lugar ----------------------

describe('GWT-1: las pestañas de renta variable no tienen columna de rendimiento', () => {
  it('las columnas son precio, variación, volumen USD, compra y venta — sin rendimiento ni TIR', async () => {
    mockearApi()
    await irALaPestanaDeAcciones()

    expect(screen.getByRole('button', { name: /precio/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /variación/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /volumen usd/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /compra/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /venta/i })).toBeInTheDocument()
    expect(screen.queryByText(/rendimiento/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/TIR/)).not.toBeInTheDocument()
  })
})

// --- GWT-2: el orden usa volumen_usd, nunca el crudo ---------------------------------------------

describe('GWT-2: orden por volumen usa el normalizado a dólares, no el nominal', () => {
  it('orden desc por "volumen USD" deja a LOMA antes que GGAL, y el s/d de PAMP al final', async () => {
    mockearApi()
    const { container } = await irALaPestanaDeAcciones()

    const cabeceraVolumen = screen.getByRole('button', { name: /volumen usd/i })
    await userEvent.click(cabeceraVolumen) // asc
    await userEvent.click(cabeceraVolumen) // desc

    const tickerDeCadaFila = () =>
      Array.from(container.querySelectorAll('div[role="button"]')).map((fila) => fila.textContent?.slice(0, 4))
    expect(tickerDeCadaFila()).toEqual(['LOMA', 'GGAL', 'PAMP'])
  })
})

// --- GWT-3: lo que BYMA no publica queda vacío y contado ------------------------------------------

describe('GWT-3: un campo que BYMA no publica queda vacío y contado en la nota de cobertura', () => {
  it('PAMP muestra s/d en variación y puntas, y la nota declara los faltantes', async () => {
    mockearApi()
    await irALaPestanaDeAcciones()

    const filaPampa = screen.getByText('PAMP').closest('div[role="button"]')
    expect(filaPampa).not.toBeNull()
    // Variación, compra y venta: tres s/d en la fila de PAMP.
    expect(within(filaPampa as HTMLElement).getAllByText('s/d').length).toBeGreaterThanOrEqual(3)

    expect(await screen.findByText(/1 sin cierre anterior \(sin variación\)/)).toBeInTheDocument()
    expect(screen.getByText(/1 sin puntas/)).toBeInTheDocument()
  })
})

// --- GWT-4: los sin_segmento siguen declarados ----------------------------------------------------

describe('GWT-4: lo excluido se declara aunque se esté mirando renta variable', () => {
  it('el texto de sin_segmento sigue visible con la pestaña de acciones activa', async () => {
    mockearApi()
    await irALaPestanaDeAcciones()

    expect(await screen.findByText(/535 sin segmento no se muestran acá/)).toBeInTheDocument()
  })
})

// --- Mecánica heredada: clic en una fila navega, el conteo está visible --------------------------

describe('mecánica heredada de la grilla', () => {
  it('clic en una fila navega a la ficha del instrumento', async () => {
    mockearApi()
    await irALaPestanaDeAcciones()

    await userEvent.click(screen.getByText('GGAL'))

    expect(await screen.findByText('ficha de GGAL')).toBeInTheDocument()
  })
})

// --- Una clase sin filas hoy: "0 de 0", no error ni pantalla rota --------------------------------

describe('una clase sin filas hoy', () => {
  it('la pestaña de CEDEARs sin datos declara la etiqueta de la pestaña activa', async () => {
    mockearApi()
    renderizar()
    await userEvent.click(await screen.findByRole('button', { name: 'CEDEARs' }))

    expect(await screen.findByText('0 de 0 especies')).toBeInTheDocument()
    expect(screen.getByText('No hay CEDEARs en el universo de hoy.')).toBeInTheDocument()
  })
})
