/**
 * `CarteraGuardadaPage` — F-041, GWT-1: por defecto muestra sólo el snapshot, sin pedir nada al
 * mercado. Se verifica afirmando que `fetch` no se llamó hasta que el asesor hace click en
 * "Revaluar a hoy" — recién ahí se montan las queries de `useCarteraCargadaValuada`. `supabase` se
 * mockea aparte (builder encadenable, mismo patrón que `useCarteraGuardada.test.ts`) porque el
 * detalle sale de PostgREST, no de `fetch`.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

interface ResultadoMock {
  data: unknown
  error: { message: string } | null
}

let resultadoDetalle: ResultadoMock = { data: null, error: null }
let resultadoBorrar: { error: { message: string } | null } = { error: null }

function crearBuilder(tabla: string) {
  const builder: Record<string, unknown> = {}
  if (tabla !== 'carteras') throw new Error(`tabla no mockeada: ${tabla}`)
  builder.select = vi.fn(() => builder)
  builder.eq = vi.fn(() => builder)
  builder.single = vi.fn(() => Promise.resolve(resultadoDetalle))
  builder.delete = vi.fn(() => builder)
  builder.then = (resolve: (v: unknown) => void, reject?: (e: unknown) => void) =>
    Promise.resolve(resultadoBorrar).then(resolve, reject)
  return builder
}

vi.mock('@/lib/supabase', () => ({
  supabase: {
    from: (tabla: string) => crearBuilder(tabla),
    auth: { getSession: () => Promise.resolve({ data: { session: null } }) },
  },
}))

import { crearQueryClient } from '@/app/queryClient'

import { CarteraGuardadaPage } from '../CarteraGuardadaPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

function especie(overrides: Record<string, unknown> = {}) {
  return {
    ticker: 'AL30D',
    emision: 'AL30',
    sufijo_liquidacion: 'D',
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.12,
    duracion: 3.5,
    vencimiento: '2030-07-09',
    periodicidad: 'semestral',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 75,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: 1,
    sector: 'Soberano',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    ...overrides,
  }
}

function mockFetch() {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/posiciones/resolver')) {
      cuerpo = {
        posiciones: [
          {
            id: 'p1',
            fila: 1,
            ticker_declarado: 'AL30D',
            nominal: 1000,
            monto: null,
            resuelta: true,
            ticker: 'AL30D',
            emision: 'AL30',
            sufijo_liquidacion: 'D',
            moneda_cotizacion: 'USD',
            plazo_liquidacion: '2',
            clase_activo: 'bono_soberano',
            segmento: 'usd_hard',
            naturaleza: 'tir_usd',
            dato_sano: true,
            motivo: null,
            motivo_descripcion: null,
            fondo_fci: null,
          },
        ],
        cobertura: {
          posiciones: 1,
          resueltas: 1,
          no_resueltas: 0,
          posiciones_con_monto: 0,
          posiciones_sin_monto: 1,
          posiciones_sin_monto_no_resueltas: 0,
          monto_declarado: 0,
          monto_no_resuelto: 0,
          porcentaje_no_resuelto: null,
        },
        alertas: [],
      }
    } else if (url.includes('/emisiones/especies')) {
      cuerpo = { items: [especie()], next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: { valor: 1100, disponible: true }, alertas: [] }
    } else if (url.includes('/renta-variable')) {
      cuerpo = { items: [], next_cursor: null }
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const snapshotCargada = {
  version: 1 as const,
  origen: 'cargada' as const,
  tipoDeCambio: 1050,
  perfil: 'moderado' as const,
  posiciones: [{ id: 'p1', fila: 1, tickerDeclarado: 'AL30D', nominal: 1000, monto: null, valida: true, motivo: null }],
  valuadas: [{ ticker: 'AL30D', moneda: 'usd' as const, invertido: 700, invertidoUsd: 700, pesoReal: 100 }],
  excluidas: [],
  totalInvertidoUsd: 700,
  plan: { aceptadas: [], descartadas: [] },
}

const snapshotArmador = {
  version: 1 as const,
  origen: 'armador' as const,
  tipoDeCambio: 1050,
  montoTotalUsd: 700,
  posiciones: [{ ticker: 'AL30D', peso: 100, clase: 'renta_fija' as const }],
  resueltas: [
    { ticker: 'AL30D', clase: 'renta_fija' as const, peso: 100, moneda: 'usd' as const, precio: 70, vn: 1000, cantidad: null, invertido: 700, invertidoUsd: 700 },
  ],
  totalInvertidoUsd: 700,
}

function filaDetalle(snapshot: unknown, origen: string) {
  return {
    id: 'c1',
    nombre: 'Renta USD',
    descripcion: null,
    origen,
    moneda_referencia: 'usd',
    monto: 700,
    resumen: '1 posición',
    snapshot_en: '2026-08-10T12:00:00Z',
    snapshot,
  }
}

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={['/carteras/c1']}>
        <Routes>
          <Route path="/carteras/:id" element={<CarteraGuardadaPage />} />
          <Route path="/carteras" element={<div>listado de carteras</div>} />
          <Route path="/armador" element={<div>pantalla del armador</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('CarteraGuardadaPage — GWT-1: por defecto, sin pedir nada al mercado', () => {
  it('muestra lo congelado sin llamar a fetch', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotCargada, 'cargada'), error: null }
    const fetchMock = mockFetch()

    renderizar()

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('al hacer click en «Revaluar a hoy», recién ahí se piden los precios de hoy', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotCargada, 'cargada'), error: null }
    const fetchMock = mockFetch()
    const usuario = userEvent.setup()

    renderizar()
    await screen.findByText('AL30D')
    expect(fetchMock).not.toHaveBeenCalled()

    await usuario.click(screen.getByRole('button', { name: 'Revaluar a hoy' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(await screen.findByLabelText('Revaluación a hoy')).toBeInTheDocument()
  })
})

describe('CarteraGuardadaPage — snapshot corrupto', () => {
  it('declara que no se pudo leer el snapshot, no rompe la pantalla', async () => {
    resultadoDetalle = { data: filaDetalle({ version: 99, algo: true }, 'cargada'), error: null }
    mockFetch()

    renderizar()

    expect(await screen.findByText('No se pudo leer el snapshot de esta cartera.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Descargar Excel' })).not.toBeInTheDocument()
  })
})

describe('CarteraGuardadaPage — F-042: exportar', () => {
  it('con snapshot legible, ofrece descargar Excel y PDF', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotCargada, 'cargada'), error: null }
    mockFetch()

    renderizar()
    await screen.findByText('AL30D')

    expect(screen.getByRole('button', { name: 'Descargar Excel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Descargar PDF' })).toBeInTheDocument()
  })
})

describe('CarteraGuardadaPage — origen', () => {
  it('«Abrir en el armador» sólo aparece para origen armador', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotCargada, 'cargada'), error: null }
    mockFetch()

    renderizar()
    await screen.findByText('AL30D')

    expect(screen.queryByRole('button', { name: 'Abrir en el armador' })).not.toBeInTheDocument()
  })

  it('«Abrir en el armador» navega a /armador para origen armador', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotArmador, 'armador'), error: null }
    mockFetch()
    const usuario = userEvent.setup()

    renderizar()
    const boton = await screen.findByRole('button', { name: 'Abrir en el armador' })
    await usuario.click(boton)

    expect(await screen.findByText('pantalla del armador')).toBeInTheDocument()
  })
})

describe('CarteraGuardadaPage — borrar', () => {
  it('pide confirmación antes de borrar, y navega al listado al confirmar', async () => {
    resultadoDetalle = { data: filaDetalle(snapshotCargada, 'cargada'), error: null }
    resultadoBorrar = { error: null }
    mockFetch()
    const usuario = userEvent.setup()

    renderizar()
    await screen.findByText('AL30D')

    await usuario.click(screen.getByRole('button', { name: 'Borrar' }))
    expect(screen.getByText('¿Borrar esta cartera guardada?')).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(await screen.findByText('listado de carteras')).toBeInTheDocument()
  })
})
