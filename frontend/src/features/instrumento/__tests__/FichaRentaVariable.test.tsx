/**
 * Los GWT de F-053 vistos desde la pantalla, más la decisión de qué ficha se muestra.
 *
 * Mismo andamiaje que `FichaInstrumento.test.tsx`: se mockea `@/lib/supabase` (sin sesión) y
 * `fetch` con `vi.stubGlobal`, despachando por la ruta exacta que pide cada hook. Un pedido a una
 * ruta no mockeada revienta el test a propósito — así "el drawer pidió la ficha equivocada" se ve
 * como un fallo y no como una pantalla vacía.
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
  BloqueExterno,
  BloquePropio,
  CotizacionExterna,
  FichaRentaVariable as Ficha,
  PerfilExterno,
  ValuacionExterna,
} from '../lib/schemaRentaVariable'

afterEach(() => {
  vi.unstubAllGlobals()
})

// --- Fixtures ---------------------------------------------------------------------------------

const TICKER = 'GGAL'
const RUTA_RV = (t: string) => `/api/v1/renta-variable/${t}/ficha`
const RUTA_RF = (t: string) => `/api/v1/instrumentos/${t}`
const RUTA_CONDICIONES = (t: string) => `/api/v1/instrumentos/${t}/condiciones`
const RUTA_CRONOGRAMA = (t: string) => `/api/v1/instrumentos/${t}/cronograma`
const RUTA_SENSIBILIDAD = (t: string) => `/api/v1/instrumentos/${t}/sensibilidad`

function propio(extra: Partial<BloquePropio> = {}): BloquePropio {
  return {
    fuente: 'BYMA',
    ticker: TICKER,
    clase_activo: 'accion',
    precio: 5000,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 4850,
    variacion: 0.030927835,
    volumen: 1_500_000_000,
    volumen_usd: null,
    px_bid: 4995,
    px_ask: 5005,
    operaciones: 120,
    ...extra,
  }
}

function cotizacion(extra: Partial<CotizacionExterna> = {}): CotizacionExterna {
  return {
    simbolo: 'GGAL.BA',
    bolsa: 'BUE',
    bolsa_nombre: 'Buenos Aires',
    moneda: 'ARS',
    nombre_largo: 'Grupo Financiero Galicia S.A.',
    nombre_corto: 'GRUPO FINANCIERO GALICIA',
    tipo_instrumento: 'EQUITY',
    precio: 5010,
    cierre_previo: 4850,
    maximo_dia: 5100,
    minimo_dia: 4900,
    maximo_52_semanas: 7000,
    minimo_52_semanas: 3000,
    volumen: 1_500_000,
    historico: [
      { fecha: '2026-08-05', cierre: 4800 },
      { fecha: '2026-08-06', cierre: 4850 },
      { fecha: '2026-08-07', cierre: 5000 },
    ],
    capturado_en: '2026-08-08T14:30:00+00:00',
    ...extra,
  }
}

function perfil(extra: Partial<PerfilExterno> = {}): PerfilExterno {
  return {
    pais: 'Argentina',
    sector: 'Financial Services',
    industria: 'Banks - Regional',
    sitio: 'https://www.gfgsa.com',
    empleados: 12000,
    capturado_en: '2026-08-08T14:30:00+00:00',
    ...extra,
  }
}

function valuacion(extra: Partial<ValuacionExterna> = {}): ValuacionExterna {
  return {
    per_trailing: 8.4,
    per_forward: 7.7,
    precio_sobre_libros: 1.37,
    beta: 0.315,
    ganancia_por_accion: { valor: 53.4, moneda: 'ARS' },
    valor_empresa: { valor: 4.66e15, moneda: 'ARS' },
    capitalizacion: null,
    montos_sin_moneda: [],
    capturado_en: '2026-08-08T14:30:00+00:00',
    ...extra,
  }
}

function externo(extra: Partial<BloqueExterno> = {}): BloqueExterno {
  return {
    fuente: 'Yahoo Finance',
    simbolo_consultado: 'GGAL.BA',
    disponible: true,
    motivo: null,
    cotizacion: cotizacion(),
    perfil: perfil(),
    valuacion: valuacion(),
    perfil_motivo: null,
    ...extra,
  }
}

function fichaRV(extra: Partial<Ficha> = {}): Ficha {
  return { ticker: TICKER, propio: propio(), externo: externo(), ...extra }
}

const CONTRATO_ERROR = (mensaje: string) => ({
  error: { code: 'not_found', message: mensaje, details: null, request_id: null },
})

interface Ruta {
  status?: number
  body: unknown
}

function mockearRutas(mapa: Record<string, Ruta | undefined>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const ruta = mapa[url]
    if (!ruta) throw new Error(`ruta no mockeada en el test: ${url}`)
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

/** Las cuatro rutas de la ficha de renta fija, en su estado más barato. */
function rutasRentaFija(ticker: string): Record<string, Ruta> {
  return {
    [RUTA_RF(ticker)]: {
      status: 404,
      body: CONTRATO_ERROR(`${ticker} no está en el universo de hoy`),
    },
    [RUTA_CONDICIONES(ticker)]: { body: { ticker, condiciones: null } },
    [RUTA_CRONOGRAMA(ticker)]: { body: { ticker, pagos: [] } },
    [RUTA_SENSIBILIDAD(ticker)]: {
      body: {
        ticker,
        tir_actual: null,
        naturaleza: null,
        naturaleza_nombre: null,
        calculable: false,
        motivo: 'sin TIR vigente',
        escenarios: [],
        omitidos_bps: [],
      },
    },
  }
}

function renderizar(ticker: string | undefined = TICKER) {
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <FichaDelActivo ticker={ticker} />
    </QueryClientProvider>,
  )
}

// --- GWT-1: la ficha de una acción -----------------------------------------------------------

it('muestra el nombre de la empresa de Yahoo, el precio de BYMA y la fuente de cada bloque', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Grupo Financiero Galicia S.A.')).toBeInTheDocument()
  // `getAllByText`: 5.000,00 es el precio de BYMA de la cabecera y también el último cierre de la
  // serie de Yahoo. Que coincidan es normal y no vuelve ambiguo lo que se está probando acá.
  expect(screen.getAllByText('5.000,00').length).toBeGreaterThan(0)
  expect(screen.getByText('La rueda de hoy · BYMA')).toBeInTheDocument()
  expect(screen.getByText('Resumen · Yahoo Finance')).toBeInTheDocument()
})

it('muestra las puntas y las operaciones de BYMA', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Compra')).toBeInTheDocument()
  expect(screen.getByText('4.995,00')).toBeInTheDocument()
  expect(screen.getByText('5.005,00')).toBeInTheDocument()
  expect(screen.getByText('120')).toBeInTheDocument()
})

// --- GWT-6: el vocabulario de la fuente no se traduce ------------------------------------------

it('muestra sector, industria y país tal como los declara la fuente', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Financial Services')).toBeInTheDocument()
  expect(screen.getByText('Banks - Regional')).toBeInTheDocument()
  expect(screen.getByText('Argentina')).toBeInTheDocument()
})

// --- GWT-5: la opinión de terceros no entra ----------------------------------------------------

it('no muestra recomendación, precio objetivo ni consenso de analistas', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  const { container } = renderizar()

  await screen.findByText('Grupo Financiero Galicia S.A.')
  const texto = container.textContent ?? ''
  expect(texto).not.toMatch(/recomendaci|precio objetivo|consenso|analista/i)
})

// --- GWT-4: la fuente externa puede faltar entera ----------------------------------------------

it('con Yahoo caído muestra igual lo de BYMA y declara el bloque externo ausente', async () => {
  const sinYahoo = fichaRV({
    externo: externo({
      disponible: false,
      motivo: 'Yahoo Finance no respondió la cotización: timeout',
      cotizacion: null,
      perfil: null,
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinYahoo } })
  renderizar()

  // Lo nuestro sigue: el precio de BYMA está en pantalla.
  expect(await screen.findByText('5.000,00')).toBeInTheDocument()
  // Y el bloque externo se declara, con el motivo de la fuente, en cada uno de sus cuatro paneles:
  // resumen, valuación, perfil e histórico. Ninguno se queda mudo.
  expect(
    screen.getAllByText('Yahoo Finance no está disponible para GGAL.BA.'),
  ).toHaveLength(4)
  expect(screen.getAllByText(/no respondió la cotización/)).not.toHaveLength(0)
})

it('sin nombre de empresa la cabecera dice el ticker, no un nombre inventado', async () => {
  const sinYahoo = fichaRV({
    externo: externo({ disponible: false, motivo: 'sin red', cotizacion: null, perfil: null }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinYahoo } })
  renderizar()

  expect(await screen.findByText('GGAL — nombre no disponible')).toBeInTheDocument()
})

// --- El nivel 2 degrada solo -------------------------------------------------------------------

it('con el perfil roto conserva la cotización y declara ausente sólo el perfil', async () => {
  const sinPerfil = fichaRV({
    externo: externo({
      perfil: null,
      perfil_motivo: 'Yahoo Finance no entregó el perfil de la empresa: HTTP 401',
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinPerfil } })
  renderizar()

  expect(await screen.findByText('Rango 52 semanas')).toBeInTheDocument()
  expect(screen.getByText('El perfil de la empresa no está disponible.')).toBeInTheDocument()
  expect(screen.getByText(/HTTP 401/)).toBeInTheDocument()
})

// --- La valuación -------------------------------------------------------------------------------

it('muestra los ratios de valuación y los montos con su moneda al lado', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('PER (forward)')).toBeInTheDocument()
  expect(screen.getByText('7,70')).toBeInTheDocument()
  expect(screen.getByText('0,315')).toBeInTheDocument()
  // El monto y su moneda salen juntos, en el mismo campo.
  expect(screen.getByText('Ganancia por acción').parentElement?.textContent).toContain('ARS')
})

it('un monto sin moneda declarada no se muestra y el faltante se dice', async () => {
  const sinMoneda = fichaRV({
    externo: externo({
      valuacion: valuacion({
        ganancia_por_accion: null,
        valor_empresa: null,
        montos_sin_moneda: ['trailingEps', 'enterpriseValue'],
      }),
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinMoneda } })
  const { container } = renderizar()

  expect(await screen.findByText(/sin moneda declarada/)).toBeInTheDocument()
  expect(screen.getByText(/trailingEps, enterpriseValue/)).toBeInTheDocument()
  // Los ratios, que no dependen de ninguna moneda, siguen a la vista.
  expect(screen.getByText('1,37')).toBeInTheDocument()
  // Y el número sin unidad no aparece por ningún lado.
  expect(container.textContent ?? '').not.toContain('134.603')
})

it('sin módulo de valuación lo declara y el resto de la ficha sigue', async () => {
  const sinValuacion = fichaRV({ externo: externo({ valuacion: null }) })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinValuacion } })
  renderizar()

  expect(await screen.findByText('La valuación no está disponible.')).toBeInTheDocument()
  expect(screen.getByText('Financial Services')).toBeInTheDocument()
})

// --- El histórico -------------------------------------------------------------------------------

it('dibuja la serie de cierres con su rango y sus extremos', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  const { container } = renderizar()

  await screen.findByText('Mínimo de la serie')
  expect(container.querySelector('polyline')).not.toBeNull()
  expect(screen.getByRole('img', { name: /Cierres diarios desde/ })).toBeInTheDocument()
  // 4.800,00 es a la vez el mínimo de la serie y su primer cierre: aparece dos veces.
  expect(screen.getAllByText('4.800,00').length).toBeGreaterThan(0)
  expect(screen.getByText(/3 cierres publicados/)).toBeInTheDocument()
})

it('con un solo cierre no dibuja nada y dice cuántos vinieron', async () => {
  const serieCorta = fichaRV({
    externo: externo({ cotizacion: cotizacion({ historico: [{ fecha: '2026-08-07', cierre: 5000 }] }) }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: serieCorta } })
  const { container } = renderizar()

  expect(await screen.findByText('No hay serie de cierres para dibujar.')).toBeInTheDocument()
  expect(container.querySelector('polyline')).toBeNull()
})

// --- Qué ficha se muestra ------------------------------------------------------------------------

it('un ticker que no es renta variable cae en la ficha de renta fija', async () => {
  const fetchMock = mockearRutas({
    [RUTA_RV('AL30')]: {
      status: 404,
      body: CONTRATO_ERROR('AL30 no es renta variable del universo de hoy'),
    },
    ...rutasRentaFija('AL30'),
  })
  renderizar('AL30')

  // El texto es el de la ficha de renta fija cuando el ticker no está en el universo.
  expect(await screen.findByText('AL30 no está en el universo de hoy.')).toBeInTheDocument()
  const pedidas = fetchMock.mock.calls.map((llamada) => String(llamada[0]))
  expect(pedidas).toContain(RUTA_RF('AL30'))
})

it('una acción no pide la ficha de renta fija', async () => {
  const fetchMock = mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  await screen.findByText('Grupo Financiero Galicia S.A.')
  const pedidas = fetchMock.mock.calls.map((llamada) => String(llamada[0]))
  expect(pedidas).toEqual([RUTA_RV(TICKER)])
})
