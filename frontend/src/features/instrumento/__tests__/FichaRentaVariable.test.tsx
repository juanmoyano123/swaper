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
  BloqueHistorico as TipoBloqueHistorico,
  BloquePropio,
  FichaRentaVariable as Ficha,
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
    precio_apertura: 4900,
    precio_maximo: 5050,
    precio_minimo: 4880,
    vwap: 4990,
    // Sin clasificar por defecto: es el caso más común (la SEC cubre 74 % de los CEDEARs y 9 %
    // de las acciones argentinas). Los tests de "La empresa" lo sobreescriben.
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    // F-079: derivados del SIC, sin curado ni clasificación por defecto.
    sector_codigo: null,
    sector: null,
    rubro_especifico: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    // F-079, D3: geografía curada de ETFs, sin curado por defecto.
    etf_indice: null,
    etf_alcance: null,
    etf_pais: null,
    etf_region: null,
    etf_geo_fuente: null,
    etf_geo_verificado: null,
    ...extra,
  }
}

function historico(extra: Partial<TipoBloqueHistorico> = {}): TipoBloqueHistorico {
  return {
    fuente: 'data912',
    disponible: true,
    motivo: null,
    puntos: [
      { fecha: '2026-08-05', cierre: 4800 },
      { fecha: '2026-08-06', cierre: 4850 },
      { fecha: '2026-08-07', cierre: 5000 },
    ],
    ...extra,
  }
}

function fichaRV(extra: Partial<Ficha> = {}): Ficha {
  return { ticker: TICKER, propio: propio(), historico: historico(), ...extra }
}

/** Un papel que el job de clasificación ya alcanzó: es el único origen del nombre de la empresa. */
const PROPIO_CLASIFICADO = {
  nombre_largo: 'Grupo Financiero Galicia S.A.',
  perfil_fuente: 'SEC EDGAR',
  perfil_capturado_en: '2026-08-13T18:33:59+00:00',
} as const

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

// --- No regresión: una acción argentina navegada directo sigue resolviendo (14/08/2026) ------
//
// Las acciones dejaron de ser descubribles desde el Monitor y el Armador, pero el endpoint de
// ficha (`/renta-variable/{ticker}/ficha`) no filtra por clase — verificado en vivo contra GGAL
// real: sigue devolviendo 200 con `propio.clase_activo: "accion"`. Una posición vieja en una
// cartera guardada, o un link directo a `/instrumento/GGAL`, tienen que seguir mostrando la ficha
// de renta variable, no caer a la de renta fija ni romperse.

it('una acción navegada directo sigue mostrando la ficha de renta variable, no la de renta fija', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV({ propio: propio({ clase_activo: 'accion' }) }) } })
  renderizar()

  expect((await screen.findAllByText('5.000,00')).length).toBeGreaterThan(0)
  expect(screen.queryByText(/no está en el universo de hoy/)).not.toBeInTheDocument()
})

// --- GWT-1: la ficha de una acción -----------------------------------------------------------

it('muestra el nombre de la empresa, el precio de BYMA y la fuente de cada bloque', async () => {
  mockearRutas({
    [RUTA_RV(TICKER)]: { body: fichaRV({ propio: propio(PROPIO_CLASIFICADO) }) },
  })
  renderizar()

  expect(await screen.findByText('Grupo Financiero Galicia S.A.')).toBeInTheDocument()
  // `getAllByText`: 5.000,00 es el precio de BYMA de la cabecera y también el último cierre de la
  // serie de data912. Que coincidan es normal y no vuelve ambiguo lo que se está probando acá.
  expect(screen.getAllByText('5.000,00').length).toBeGreaterThan(0)
  expect(screen.getByText('La rueda de hoy · BYMA')).toBeInTheDocument()
  expect(screen.getByText('Cierres del último año · data912')).toBeInTheDocument()
})

// --- El OHLC de BYMA (13/08/2026) ---------------------------------------------------------------

it('muestra apertura, rango del día y VWAP en la rueda', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Apertura')).toBeInTheDocument()
  expect(screen.getByText('4.900,00')).toBeInTheDocument()
  expect(screen.getByText('4.880,00 – 5.050,00')).toBeInTheDocument()
  expect(screen.getByText('VWAP')).toBeInTheDocument()
  expect(screen.getByText('4.990,00')).toBeInTheDocument()
})

it('sin OHLC (fila anterior a la migración) declara vacío, no rompe la rueda', async () => {
  const sinOhlc = fichaRV({
    propio: propio({
      precio_apertura: null,
      precio_maximo: null,
      precio_minimo: null,
      vwap: null,
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinOhlc } })
  renderizar()

  await screen.findByText('Apertura')
  expect(screen.getAllByText('s/d').length).toBeGreaterThan(0)
})

// --- La empresa: la clasificación de la SEC ------------------------------------------------------

it('muestra la actividad, el rubro y el eslabón productivo de la SEC', async () => {
  const clasificado = fichaRV({
    propio: propio({
      nombre_largo: 'GRUPO FINANCIERO GALICIA SA',
      perfil_fuente: 'SEC EDGAR',
      perfil_capturado_en: '2026-08-13T18:33:59+00:00',
      sic_codigo: '6029',
      sic_titulo: 'Commercial Banks, NEC',
      sic_oficina: 'Office of Finance',
      division_cadena: 'Finanzas y seguros',
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: clasificado } })
  renderizar()

  expect(await screen.findByText('Commercial Banks, NEC')).toBeInTheDocument()
  expect(screen.getByText('Office of Finance')).toBeInTheDocument()
  expect(screen.getByText('Finanzas y seguros')).toBeInTheDocument()
  expect(screen.getByText('GRUPO FINANCIERO GALICIA SA')).toBeInTheDocument()
})

it('un fondo muestra su estrategia', async () => {
  const etf = fichaRV({
    propio: propio({
      ticker: 'GLD',
      nombre_largo: 'ETF SPDR GOLD TRUST',
      sic_codigo: '6221',
      estrategia_etf: 'activo_fisico',
      ratio_conversion: '50:1',
      mercado_origen: 'NYSE',
    }),
  })
  mockearRutas({ [RUTA_RV('GLD')]: { body: etf } })
  renderizar('GLD')

  expect(await screen.findByText('Estrategia')).toBeInTheDocument()
  expect(screen.getByText('activo físico')).toBeInTheDocument()
  expect(screen.getByText('50:1')).toBeInTheDocument()
})

it('sin clasificar declara que el job no pasó por este papel, no inventa un sector', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Todavía no se clasificó este papel.')).toBeInTheDocument()
})

// --- F-079: sector y rubro específico, la traducción curada del SIC en dos niveles -------------

it('muestra sector y rubro específico en ES, con el código de auditoría entre paréntesis', async () => {
  mockearRutas({
    [RUTA_RV(TICKER)]: {
      body: fichaRV({
        propio: propio({
          sic_codigo: '6029',
          sic_titulo: 'Commercial Banks, NEC',
          sector_codigo: '60',
          sector: 'Finanzas',
          rubro_especifico: 'Bancos comerciales',
        }),
      }),
    },
  })
  renderizar()

  expect(await screen.findByText('Finanzas (60)')).toBeInTheDocument()
  expect(screen.getByText('Bancos comerciales (6029)')).toBeInTheDocument()
  // La lectura en inglés de la SEC sigue abajo, sin traducir: las dos conviven (regla 11).
  expect(screen.getByText('Commercial Banks, NEC')).toBeInTheDocument()
})

it('sin etiqueta ES curada para el código, declara "sin traducir" en vez de dejar el campo vacío', async () => {
  mockearRutas({
    [RUTA_RV(TICKER)]: {
      body: fichaRV({
        propio: propio({
          sic_codigo: '9999',
          sic_titulo: 'Something The SEC Titles',
          sector_codigo: '99',
          sector: null,
          rubro_especifico: null,
        }),
      }),
    },
  })
  renderizar()

  expect(await screen.findByText('99 (sin traducir)')).toBeInTheDocument()
  expect(screen.getByText('9999 (sin traducir)')).toBeInTheDocument()
})

// --- F-079, D3: geografía curada de ETFs, con su fuente y su fecha de verificación --------------

it('un ETF con geografía curada muestra el bloque de índice, alcance, país y región', async () => {
  mockearRutas({
    [RUTA_RV('GLD')]: {
      body: fichaRV({
        propio: propio({
          ticker: 'GLD',
          estrategia_etf: 'geografico',
          etf_indice: 'MSCI Brazil',
          etf_alcance: 'Empresas brasileñas de gran y mediana capitalización',
          etf_pais: 'BR',
          etf_region: 'América Latina y el Caribe',
          etf_geo_fuente: 'ficha del emisor del índice',
          etf_geo_verificado: '2026-08-20',
        }),
      }),
    },
  })
  renderizar('GLD')

  expect(await screen.findByText('Geografía del fondo · curado propio')).toBeInTheDocument()
  expect(screen.getByText('MSCI Brazil')).toBeInTheDocument()
  expect(screen.getByText('Empresas brasileñas de gran y mediana capitalización')).toBeInTheDocument()
  expect(screen.getByText('BR')).toBeInTheDocument()
  expect(screen.getByText('América Latina y el Caribe')).toBeInTheDocument()
  expect(screen.getByText(/ficha del emisor del índice/)).toBeInTheDocument()
})

it('sin geografía curada (`etf_indice` null) no muestra el bloque, sea o no un fondo', async () => {
  mockearRutas({
    [RUTA_RV('SPY')]: {
      body: fichaRV({ propio: propio({ ticker: 'SPY', estrategia_etf: 'indice_amplio' }) }),
    },
  })
  renderizar('SPY')

  await screen.findByText('La empresa · SEC')
  expect(screen.queryByText('Geografía del fondo · curado propio')).not.toBeInTheDocument()
})

it('un fondo multi-país curado declara país y región sin dato, no completa la composición', async () => {
  mockearRutas({
    [RUTA_RV('EEM')]: {
      body: fichaRV({
        propio: propio({
          ticker: 'EEM',
          estrategia_etf: 'geografico',
          etf_indice: 'MSCI Emerging Markets',
          etf_alcance: 'Mercados emergentes globales',
          etf_pais: null,
          etf_region: null,
          etf_geo_fuente: 'ficha del emisor del índice',
          etf_geo_verificado: '2026-08-20',
        }),
      }),
    },
  })
  renderizar('EEM')

  await screen.findByText('MSCI Emerging Markets')
  expect(screen.getByText('Mercados emergentes globales')).toBeInTheDocument()
  expect(screen.getAllByText('s/d').length).toBeGreaterThan(0)
})

it('muestra las puntas y las operaciones de BYMA', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('Compra')).toBeInTheDocument()
  expect(screen.getByText('4.995,00')).toBeInTheDocument()
  expect(screen.getByText('5.005,00')).toBeInTheDocument()
  expect(screen.getByText('120')).toBeInTheDocument()
})

// --- GWT-5: la opinión de terceros no entra ----------------------------------------------------

it('no muestra recomendación, precio objetivo ni consenso de analistas', async () => {
  mockearRutas({
    [RUTA_RV(TICKER)]: { body: fichaRV({ propio: propio(PROPIO_CLASIFICADO) }) },
  })
  const { container } = renderizar()

  await screen.findByText('Grupo Financiero Galicia S.A.')
  const texto = container.textContent ?? ''
  expect(texto).not.toMatch(/recomendaci|precio objetivo|consenso|analista/i)
})

it('sin nombre de empresa la cabecera dice el ticker, no un nombre inventado', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText('GGAL — nombre no disponible')).toBeInTheDocument()
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
    historico: historico({ puntos: [{ fecha: '2026-08-07', cierre: 5000 }] }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: serieCorta } })
  const { container } = renderizar()

  expect(await screen.findByText('No hay serie de cierres para dibujar.')).toBeInTheDocument()
  expect(container.querySelector('polyline')).toBeNull()
})

it('con data912 caído declara el histórico ausente y el resto de la ficha sigue', async () => {
  const sinHistorico = fichaRV({
    propio: propio(PROPIO_CLASIFICADO),
    historico: historico({
      disponible: false,
      motivo: 'data912 no respondió el histórico de GGAL (timeout)',
      puntos: [],
    }),
  })
  mockearRutas({ [RUTA_RV(TICKER)]: { body: sinHistorico } })
  const { container } = renderizar()

  expect(
    await screen.findByText('data912 no tiene serie histórica para este símbolo.'),
  ).toBeInTheDocument()
  expect(screen.getByText(/timeout/)).toBeInTheDocument()
  expect(container.querySelector('polyline')).toBeNull()
  // Lo demás no depende de data912.
  expect(screen.getByText('Grupo Financiero Galicia S.A.')).toBeInTheDocument()
})

it('la leyenda del histórico no hereda la moneda de la especie', async () => {
  mockearRutas({ [RUTA_RV(TICKER)]: { body: fichaRV() } })
  renderizar()

  expect(await screen.findByText(/no declara la moneda de la serie/)).toBeInTheDocument()
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
  const fetchMock = mockearRutas({
    [RUTA_RV(TICKER)]: { body: fichaRV({ propio: propio(PROPIO_CLASIFICADO) }) },
  })
  renderizar()

  await screen.findByText('Grupo Financiero Galicia S.A.')
  const pedidas = fetchMock.mock.calls.map((llamada) => String(llamada[0]))
  expect(pedidas).toEqual([RUTA_RV(TICKER)])
})
