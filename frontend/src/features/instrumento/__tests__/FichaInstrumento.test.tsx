/**
 * Los GWT de F-039 vistos desde la pantalla, más el criterio que sostiene las tres queries
 * separadas: una falla en el cronograma no puede tumbar la ficha de precios ni las condiciones.
 *
 * Mismo patrón que `features/estado-dato/__tests__/BarraEstadoDato.test.tsx`: se mockea
 * `@/lib/supabase` (sin sesión) y `fetch` con `vi.stubGlobal`, despachando por la ruta exacta que
 * pide cada uno de los tres hooks.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { FichaInstrumento } from '../FichaInstrumento'
import type { Condiciones, Cronograma, EspecieFicha, Ficha, PagoCronograma } from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

// --- Fixtures --------------------------------------------------------------------------------------

function especie(ticker: string, extra: Partial<EspecieFicha> = {}): EspecieFicha {
  return {
    ticker,
    emision: 'AL30',
    sufijo_liquidacion: ticker === 'AL30' ? null : ticker.slice(-1),
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.12,
    duracion: 3.5,
    vencimiento: '2030-07-09',
    ley: 'Ley Argentina',
    moneda_cupon: 'USD',
    emisor: 'Gobierno Argentino',
    precio: 65_000,
    moneda_cotizacion: 'ARS',
    volumen: 1_000_000,
    volumen_usd: 650,
    paridad: 0.875,
    dato_sano: true,
    ...extra,
  }
}

function ficha(ticker: string, hermanas: EspecieFicha[] = []): Ficha {
  return { ticker, especie: especie(ticker), hermanas }
}

function condiciones(detalle: Condiciones['condiciones']): Condiciones {
  return { ticker: 'AL30D', condiciones: detalle }
}

function condicionDetalleVacia(): NonNullable<Condiciones['condiciones']> {
  return {
    ticker: 'AL30D',
    ley: null,
    ley_origen: null,
    ley_fecha: null,
    moneda_pago: null,
    moneda_pago_origen: null,
    moneda_pago_fecha: null,
    lamina: null,
    lamina_origen: null,
    lamina_fecha: null,
    calificacion: null,
    calificacion_origen: null,
    calificacion_fecha: null,
    sector: null,
    sector_origen: null,
    sector_fecha: null,
    underlying: null,
    underlying_origen: null,
    underlying_fecha: null,
  }
}

function pago(extra: Partial<PagoCronograma> = {}): PagoCronograma {
  return { fecha: '2028-01-09', interes: 1.5, amortizacion: 0, moneda: 'USD', ...extra }
}

function cronograma(pagos: PagoCronograma[]): Cronograma {
  return { ticker: 'AL30D', pagos }
}

const CONTRATO_ERROR = (mensaje: string) => ({
  error: { code: 'not_found', message: mensaje, details: null, request_id: null },
})

interface Ruta {
  status?: number
  body: unknown
}

/** Un `fetch` falso que despacha por la ruta exacta que pide cada uno de los tres hooks.
 *  `Ruta | undefined` porque `rutasOk` construye el mapa combinando claves fijas con
 *  `overrides: Partial<Record<...>>`, y el spread deja esas claves como posiblemente ausentes
 *  aunque en runtime siempre estén — el guard de abajo ya cubre ese caso. */
function mockearRutas(mapa: Record<string, Ruta | undefined>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const ruta = mapa[url]
    if (!ruta) {
      throw new Error(`ruta no mockeada en el test: ${url}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(ruta.body), {
        status: ruta.status ?? 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar(ticker: string | undefined) {
  const cliente = crearQueryClient()
  return render(
    <QueryClientProvider client={cliente}>
      <FichaInstrumento ticker={ticker} />
    </QueryClientProvider>,
  )
}

const RUTA_FICHA = (t: string) => `/api/v1/instrumentos/${t}`
const RUTA_CONDICIONES = (t: string) => `/api/v1/instrumentos/${t}/condiciones`
const RUTA_CRONOGRAMA = (t: string) => `/api/v1/instrumentos/${t}/cronograma`

/** Las tres rutas resolviendo en éxito, con datos mínimos — el punto de partida de la mayoría de
 * los tests, que después pisan sólo la que les interesa. */
function rutasOk(ticker: string, overrides: Partial<Record<string, Ruta>> = {}) {
  return {
    [RUTA_FICHA(ticker)]: { body: ficha(ticker) },
    [RUTA_CONDICIONES(ticker)]: { body: condiciones(null) },
    [RUTA_CRONOGRAMA(ticker)]: { body: cronograma([]) },
    ...overrides,
  }
}

// --- GWT-1: el mismo papel en las tres monedas, sin sumarse ni promediarse ------------------------

describe('el bloque de las tres monedas', () => {
  it('renderiza una tarjeta por la especie pedida y por cada hermana, con las puntas en s/d', async () => {
    const hermanas = [especie('AL30', { sufijo_liquidacion: null }), especie('AL30C')]
    mockearRutas(rutasOk('AL30D', { [RUTA_FICHA('AL30D')]: { body: ficha('AL30D', hermanas) } }))

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(screen.getByText('AL30')).toBeInTheDocument()
    expect(screen.getByText('AL30C')).toBeInTheDocument()

    const puntas = screen.getAllByTitle('las puntas no viajan por la fuente hoy')
    expect(puntas).toHaveLength(3)
    for (const bloque of puntas) {
      expect(bloque).toHaveTextContent('compra s/d')
      expect(bloque).toHaveTextContent('venta s/d')
    }

    expect(screen.getByText(/no se suman ni se convierten entre sí/)).toBeInTheDocument()
  })

  it('sin hermanas muestra una sola tarjeta', async () => {
    mockearRutas(rutasOk('S30J6'))

    renderizar('S30J6')

    await screen.findByText('S30J6')
    expect(screen.getAllByTitle('las puntas no viajan por la fuente hoy')).toHaveLength(1)
  })
})

// --- Un ticker que no está en el universo de hoy --------------------------------------------------

describe('un ticker fuera del universo', () => {
  it('muestra un mensaje explícito y no una pantalla en blanco', async () => {
    mockearRutas({
      ...rutasOk('NOEXISTE'),
      [RUTA_FICHA('NOEXISTE')]: {
        status: 404,
        body: CONTRATO_ERROR('NOEXISTE no está en el universo de hoy'),
      },
    })

    renderizar('NOEXISTE')

    expect(await screen.findByText('NOEXISTE no está en el universo de hoy.')).toBeInTheDocument()
  })
})

// --- GWT-2: calificación ausente → "no informado", nunca vacío ni inferido -------------------------

describe('condiciones de emisión', () => {
  it('sin fila curada, los seis campos dicen "no informado"', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    await screen.findByText('AL30D')
    expect(screen.getAllByText('no informado')).toHaveLength(6)
  })

  it('un campo presente muestra su valor y trae origen y fecha en el título', async () => {
    const detalle = {
      ...condicionDetalleVacia(),
      ley: 'Ley Argentina',
      ley_origen: 'condiciones_emision.csv (curado)',
      ley_fecha: '2026-08-05',
    }
    mockearRutas(
      rutasOk('AL30D', { [RUTA_CONDICIONES('AL30D')]: { body: condiciones(detalle) } }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    // La ficha (fuera de condiciones) también dice "Ley Argentina" — el título distingue cuál es
    // el campo de condiciones curado.
    const valor = await screen.findByTitle(/condiciones_emision\.csv/)
    expect(valor).toHaveTextContent('Ley Argentina')
    expect(valor.getAttribute('title')).toContain('05/08/2026')
    // El resto de los campos de esta ficha sigue "no informado": no se contagia entre campos.
    expect(screen.getAllByText('no informado')).toHaveLength(5)
  })
})

// --- Renta variable: "no aplica", no "s/d" --------------------------------------------------------

describe('un instrumento de renta variable', () => {
  it('muestra "no aplica" en rendimiento y duración', async () => {
    const accion = especie('GGAL', { clase_activo: 'accion', rendimiento: 0.5, duracion: 1 })
    mockearRutas(rutasOk('GGAL', { [RUTA_FICHA('GGAL')]: { body: { ...ficha('GGAL'), especie: accion } } }))

    renderizar('GGAL')

    await screen.findByText('GGAL')
    expect(screen.getAllByText('no aplica')).toHaveLength(2)
  })
})

// --- GWT-3: el cronograma completo, interés separado de amortización -------------------------------

describe('el cronograma', () => {
  it('separa interés de amortización en filas distintas cuando el pago trae los dos', async () => {
    const pagos = [
      pago({ fecha: '2028-01-09', interes: 1.5, amortizacion: 0 }),
      pago({ fecha: '2030-07-09', interes: 1.5, amortizacion: 100 }),
    ]
    mockearRutas(
      rutasOk('AL30D', { [RUTA_CRONOGRAMA('AL30D')]: { body: cronograma(pagos) } }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    const filas = await screen.findAllByRole('row')
    // Encabezado + 1 fila de renta pura + 2 filas del pago de vencimiento (renta y amortización).
    expect(filas).toHaveLength(4)
    expect(screen.getAllByText('renta')).toHaveLength(2)
    expect(screen.getByText('amortización')).toBeInTheDocument()
  })

  it('sin pagos declara que no hay cronograma cargado, no un error', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    expect(
      await screen.findByText('Sin cronograma cargado para esta emisión.'),
    ).toBeInTheDocument()
  })
})

// --- Tres queries independientes: una en error no tumba a las otras dos ----------------------------

describe('las tres queries son independientes', () => {
  it('un cronograma que falla no tapa la ficha de precios ni las condiciones', async () => {
    const detalle = { ...condicionDetalleVacia(), sector: 'Soberano' }
    mockearRutas({
      ...rutasOk('AL30D', { [RUTA_CONDICIONES('AL30D')]: { body: condiciones(detalle) } }),
      [RUTA_CRONOGRAMA('AL30D')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(await screen.findByText('Soberano')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('condiciones que fallan no tapan la ficha de precios ni el cronograma', async () => {
    mockearRutas({
      ...rutasOk('AL30D', {
        [RUTA_CRONOGRAMA('AL30D')]: { body: cronograma([pago()]) },
      }),
      [RUTA_CONDICIONES('AL30D')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(await screen.findByText('renta')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

// --- El contrato de tipos existente: `ticker` puede no llegar todavía ------------------------------

describe('sin ticker', () => {
  it('mantiene el estado vacío original, sin disparar ningún fetch', () => {
    const fetchMock = mockearRutas({})

    renderizar(undefined)

    expect(screen.getByText('No hay datos de este instrumento todavía.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
