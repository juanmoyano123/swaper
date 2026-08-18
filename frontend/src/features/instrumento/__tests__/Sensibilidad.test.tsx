/**
 * F-040: la tabla de sensibilidad como panel independiente de la ficha.
 *
 * Mismo patrón que `FichaInstrumento.test.tsx`: se mockea `@/lib/supabase` (sin sesión) y `fetch`
 * con `vi.stubGlobal`, despachando por la ruta exacta. Las fixtures de ficha/condiciones/cronograma
 * se reescriben localmente, mínimas — este archivo no toca `FichaInstrumento.test.tsx`, que es de
 * F-039.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import { UNIDAD_NATURALEZA } from '@/components/SelectorSegmento'

import { FichaInstrumento } from '../FichaInstrumento'
import type { Condiciones, Cronograma, EspecieFicha, Ficha, Sensibilidad } from '../lib/schema'

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
    fuente: null,
    ...extra,
  }
}

function ficha(ticker: string): Ficha {
  return { ticker, especie: especie(ticker), hermanas: [] }
}

function condiciones(): Condiciones {
  return { ticker: 'AL30D', condiciones: null }
}

function cronograma(): Cronograma {
  return {
    ticker: 'AL30D',
    pagos: [],
    resumen: {
      residual_vigente: null,
      valor_tecnico: null,
      cupon_corrido: null,
      paridad: null,
      coherente: true,
      motivo_ausente: 'sin cronograma de pagos en la fuente',
    },
  }
}

function sensibilidad(extra: Partial<Sensibilidad> = {}): Sensibilidad {
  return {
    ticker: 'AL30D',
    tir_actual: 0.121,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    calculable: true,
    motivo: null,
    escenarios: [
      { delta_bps: -500, tir_escenario: 0.071, retorno: 0.1834 },
      { delta_bps: -400, tir_escenario: 0.081, retorno: 0.14 },
      { delta_bps: -300, tir_escenario: 0.091, retorno: 0.1 },
      { delta_bps: -200, tir_escenario: 0.101, retorno: 0.06 },
      { delta_bps: -100, tir_escenario: 0.111, retorno: 0.03 },
      { delta_bps: 0, tir_escenario: 0.121, retorno: 0.0 },
      { delta_bps: 100, tir_escenario: 0.131, retorno: -0.028 },
      { delta_bps: 200, tir_escenario: 0.141, retorno: -0.054 },
    ],
    omitidos_bps: [],
    ...extra,
  }
}

const CONTRATO_ERROR = (mensaje: string) => ({
  error: { code: 'internal_error', message: mensaje, details: null, request_id: null },
})

interface Ruta {
  status?: number
  body: unknown
}

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

function renderizar(ticker: string) {
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
const RUTA_SENSIBILIDAD = (t: string) => `/api/v1/instrumentos/${t}/sensibilidad`
const RUTA_PROSPECTO = (t: string) => `/api/v1/instrumentos/${t}/prospecto`

/** Las cinco rutas resolviendo en éxito, con datos mínimos — pisadas por cada test según su caso.
 *  El prospecto (F-072) se pide siempre, sin importar la clase del ticker — el panel no se
 *  renderiza para un soberano, pero el hook igual dispara el fetch. */
function rutasOk(ticker: string, overrides: Partial<Record<string, Ruta>> = {}) {
  return {
    [RUTA_FICHA(ticker)]: { body: ficha(ticker) },
    [RUTA_CONDICIONES(ticker)]: { body: condiciones() },
    [RUTA_CRONOGRAMA(ticker)]: { body: cronograma() },
    [RUTA_SENSIBILIDAD(ticker)]: { body: sensibilidad() },
    [RUTA_PROSPECTO(ticker)]: {
      body: {
        ticker,
        aplica: false,
        emisor: null,
        cuit: null,
        url_emisor_cnv: null,
        grupos: [],
        motivo_ausente: 'no es una obligación negociable',
        fuente: 'CNV',
      },
    },
    ...overrides,
  }
}

// --- GWT-1: repricing completo, tabla con las ocho filas -------------------------------------------

describe('la tabla de sensibilidad', () => {
  it('muestra la tabla con la unidad del instrumento y los retornos formateados', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    expect(await screen.findByText('Sensibilidad')).toBeInTheDocument()
    expect(screen.getByText(`TIR escenario (${UNIDAD_NATURALEZA.tir_usd})`)).toBeInTheDocument()
    // 0.1834 -> "18,34%", con coma decimal (es-AR).
    expect(screen.getByText('18,34%')).toBeInTheDocument()
    expect(screen.getByText('0 bps')).toBeInTheDocument()
    expect(screen.getByText('+100 bps')).toBeInTheDocument()
    expect(screen.getByText('−500 bps')).toBeInTheDocument()
  })
})

// --- GWT-3: no calculable declara el motivo, sin tabla ni número derivado --------------------------

describe('un instrumento sin sensibilidad calculable', () => {
  it('muestra el motivo del backend y no renderiza ninguna tabla', async () => {
    mockearRutas(
      rutasOk('S30J6', {
        [RUTA_SENSIBILIDAD('S30J6')]: {
          body: sensibilidad({
            calculable: false,
            tir_actual: null,
            naturaleza: 'tna_nominal_ars',
            naturaleza_nombre: 'TNA nominal en pesos',
            motivo:
              'el rendimiento de este segmento es TNA nominal en pesos, no una tasa efectiva descontable: no se calcula',
            escenarios: [],
          }),
        },
      }),
    )

    renderizar('S30J6')

    expect(
      await screen.findByText('el rendimiento de este segmento es TNA nominal en pesos, no una tasa efectiva descontable: no se calcula'),
    ).toBeInTheDocument()
    expect(screen.queryAllByRole('row')).toHaveLength(0)
  })
})

// --- Query independiente: un 500 acá no tumba el resto de la ficha ---------------------------------

describe('la query de sensibilidad es independiente', () => {
  it('un 500 en sensibilidad no tapa la ficha de precios ni el cronograma', async () => {
    mockearRutas({
      ...rutasOk('AL30D'),
      [RUTA_SENSIBILIDAD('AL30D')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

// --- Escenarios omitidos por el piso de tasa se declaran --------------------------------------------

describe('escenarios omitidos', () => {
  it('la nota de escenarios omitidos está visible cuando omitidos_bps no está vacío', async () => {
    mockearRutas(
      rutasOk('AL30D', {
        [RUTA_SENSIBILIDAD('AL30D')]: { body: sensibilidad({ omitidos_bps: [-500] }) },
      }),
    )

    renderizar('AL30D')

    expect(await screen.findByText(/1 escenarios omitidos/)).toBeInTheDocument()
  })
})

// --- Contrato: una respuesta sin `escenarios` es un contract_mismatch, no un render a medias -------

describe('el contrato del schema', () => {
  it('sin el campo escenarios, la query cae en error y no se renderiza ninguna tabla', async () => {
    const { escenarios: _escenarios, ...sinEscenarios } = sensibilidad()
    mockearRutas(
      rutasOk('AL30D', {
        [RUTA_SENSIBILIDAD('AL30D')]: { body: sinEscenarios },
      }),
    )

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('18,34%')).not.toBeInTheDocument()
  })
})
