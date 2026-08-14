/**
 * `BloqueRentaVariable` vista desde la pantalla — F-026. Mismo patrón que `CarteraEditable.test.tsx`
 * (mock de `fetch` por URL, sin MSW) y que `RentaVariable.test.tsx` del monitor para la navegación
 * a la ficha. La lógica pura de cálculo se cubre aparte en `resolverRentaVariable.test.ts`.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import { BloqueRentaVariable } from '../components/BloqueRentaVariable'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function accion(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  // La emisión sigue al ticker salvo que el caso la fije: si quedara clavada, dos especies con
  // tickers distintos se agruparían como el mismo papel.
  const ticker = extra.ticker ?? 'GGAL'
  return {
    ticker: 'GGAL',
    clase_activo: 'accion',
    precio: 30,
    moneda_cotizacion: 'USD',
    cierre_anterior: 29,
    variacion: 0.0345,
    volumen: 100_000,
    volumen_usd: 100_000,
    px_bid: 29.9,
    px_ask: 30.1,
    operaciones: 12,
    fuente: null,
    // El agrupamiento por papel: sin variantes, cada especie es su propia emisión.
    emision: ticker,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_corto: null,
    nombre_largo: null,
    sector: null,
    industria: null,
    pais: null,
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

function cedear(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  const ticker = extra.ticker ?? 'AAPL'
  return {
    ticker: 'AAPL',
    clase_activo: 'cedear',
    precio: 50,
    moneda_cotizacion: 'USD',
    cierre_anterior: 49,
    variacion: -0.01,
    volumen: 5_000,
    volumen_usd: 5_000,
    px_bid: 49.5,
    px_ask: 50.5,
    operaciones: 3,
    fuente: null,
    emision: ticker,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_corto: null,
    nombre_largo: null,
    sector: null,
    industria: null,
    pais: null,
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

function responderCon({
  acciones = [],
  cedears = [],
  especiesRentaFija = [],
  tipoDeCambio = { valor: 1500, disponible: true },
}: {
  acciones?: EspecieRentaVariable[]
  cedears?: EspecieRentaVariable[]
  especiesRentaFija?: unknown[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/renta-variable/especies')) {
      const clase = new URL(url, 'http://localhost').searchParams.get('clase')
      cuerpo = { items: clase === 'accion' ? acciones : cedears, next_cursor: null }
    } else if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especiesRentaFija, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function FichaFalsa() {
  const { ticker } = useParams()
  return <div>ficha de {ticker}</div>
}

/** Expone las acciones del store que en la pantalla real dispara el bloque mismo. */
function Arnes() {
  const { alternarRentaVariable, fijarMontoTotal } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarRentaVariable('GGAL')}>
        agregar GGAL directo
      </button>
      <button type="button" onClick={() => fijarMontoTotal(1000)}>
        monto 1.000
      </button>
      <BloqueRentaVariable />
    </div>
  )
}

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={['/armador']}>
        <Routes>
          <Route
            path="/armador"
            element={
              <ArmadorProvider>
                <Arnes />
              </ArmadorProvider>
            }
          />
          <Route path="/instrumento/:ticker" element={<FichaFalsa />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('sin posiciones de renta variable', () => {
  it('lo dice en vez de mostrar una grilla vacía', async () => {
    responderCon({ acciones: [accion()] })
    renderizar()

    expect(await screen.findByText(/Sin acciones ni CEDEARs en la cartera/)).toBeInTheDocument()
  })
})

describe('una tarjeta de renta variable', () => {
  it('no tiene columna de TIR, ni de duración, ni de cupón (GWT de la spec)', async () => {
    responderCon({ acciones: [accion()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))

    const tarjeta = await screen.findByRole('article', { name: 'GGAL' })
    expect(within(tarjeta).queryByText(/TIR/)).not.toBeInTheDocument()
    expect(within(tarjeta).queryByText(/[Dd]uración/)).not.toBeInTheDocument()
    expect(within(tarjeta).queryByText(/[Cc]upón/)).not.toBeInTheDocument()
  })

  it('muestra peso dentro del bloque, invertido y "Div. est." siempre en s/d', async () => {
    responderCon({ acciones: [accion({ precio: 30 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))

    const tarjeta = await screen.findByRole('article', { name: 'GGAL' })
    // Única posición del bloque: peso real dentro del bloque = 100%.
    expect(within(tarjeta).getByText('100,00%')).toBeInTheDocument()
    // objetivo 1000 USD / 30 = 33,33 -> floor 33 unidades -> 33 * 30 = 990.
    expect(within(tarjeta).getByText('US$ 990,00')).toBeInTheDocument()
    // Nunca estimado: siempre s/d, con nota explicando por qué.
    const divEst = within(tarjeta).getByText('Div. est.').closest('div')
    expect(within(divEst as HTMLElement).getByText('s/d')).toBeInTheDocument()
  })

  it('declara la clase con un badge en vez de un emisor inventado (el dato no existe)', async () => {
    responderCon({ acciones: [accion()], cedears: [cedear()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))

    const tarjeta = await screen.findByRole('article', { name: 'GGAL' })
    // El badge dice qué es el papel; sin perfil de empresa cargado, el nombre queda en s/d y no
    // se rellena con el ticker ni con nada parecido.
    expect(within(tarjeta).getByText('ACC')).toBeInTheDocument()
  })

  it('clic en el ticker abre la ficha del instrumento', async () => {
    responderCon({ acciones: [accion()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    const tarjeta = await screen.findByRole('article', { name: 'GGAL' })

    await userEvent.click(within(tarjeta).getByRole('button', { name: 'GGAL' }))

    expect(await screen.findByText('ficha de GGAL')).toBeInTheDocument()
  })

  it('el % pedido se edita con un input propio, y actualiza el store (Etapa 3)', async () => {
    responderCon({ acciones: [accion({ precio: 30 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))
    const tarjeta = await screen.findByRole('article', { name: 'GGAL' })

    const input = within(tarjeta).getByLabelText('ponderación pedida de GGAL')
    expect(input).toHaveValue(100)

    await userEvent.clear(input)
    await userEvent.type(input, '40')

    // El peso pedido bajó a 40, pero es la única posición del bloque: el peso real dentro del
    // bloque sigue siendo 100% — son dos cuentas distintas y no se confunden.
    expect(input).toHaveValue(40)
    const filaReal = within(tarjeta).getByText('% real').closest('div')
    expect(within(filaReal as HTMLElement).getByText('100,00%')).toBeInTheDocument()
  })

  it('el botón × saca la posición de la cartera', async () => {
    responderCon({ acciones: [accion()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await screen.findByRole('article', { name: 'GGAL' })

    // Ambiguo si se busca en toda la pantalla: la tarjeta tiene su propio botón × y el buscador
    // de abajo tiene el suyo con la misma etiqueta accesible para el mismo ticker.
    const listaCartera = screen.getByRole('list', { name: 'Renta variable en la cartera' })
    await userEvent.click(within(listaCartera).getByRole('button', { name: 'sacar GGAL de la cartera' }))

    expect(screen.queryByRole('article', { name: 'GGAL' })).not.toBeInTheDocument()
    expect(await screen.findByText(/Sin acciones ni CEDEARs en la cartera/)).toBeInTheDocument()
  })
})

// --- GWT-4 de la spec: el monto total incluye las dos porciones, cada una con su subtotal --------

describe('composición del monto total (GWT-4)', () => {
  it('declara el subtotal de renta fija y el de renta variable por separado, y el total como su suma', async () => {
    responderCon({
      acciones: [accion({ precio: 30 })],
      especiesRentaFija: [
        {
          ticker: 'AL30',
          emision: 'AL30',
          sufijo_liquidacion: null,
          clase_activo: 'bono_soberano',
          segmento: 'usd_hard',
          naturaleza: 'tir_usd',
          naturaleza_nombre: 'TIR en dólares (hard dollar)',
          rendimiento: 0.1123,
          duracion: 3.2,
          vencimiento: '2030-07-09',
          periodicidad: 'semestral',
          ley: 'ARG',
          moneda_cupon: 'USD',
          emisor: 'República Argentina',
          precio: 105,
          moneda_cotizacion: 'USD',
          volumen: 100_000,
          volumen_usd: 100_000,
          paridad: 0.98,
          lamina: null,
          sector: null,
          dato_sano: true,
          hermanas: [],
        },
      ],
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))

    await screen.findByRole('article', { name: 'GGAL' })

    // Renta variable: única posición, peso pedido 100% del total -> objetivo 1000 USD / 30 = 33
    // unidades -> 990 USD invertidos.
    const campoRv = (await screen.findByText('Renta variable (USD)')).closest('div')
    expect(within(campoRv as HTMLElement).getByText('US$ 990,00')).toBeInTheDocument()

    // Con una sola posición de renta variable en la cartera, `posicionesRentaFija` (base común)
    // no tiene nada que resolver todavía — este bloque no agrega AL30 a la cartera, sólo lee el
    // subtotal ya calculado por `useCarteraResuelta`. Se declara sin dato, no cero.
    const campoRf = (await screen.findByText('Renta fija (USD)')).closest('div')
    expect(within(campoRf as HTMLElement).getByText('s/d')).toBeInTheDocument()

    // El total sólo suma lo que sí se resolvió: acá, únicamente la porción de renta variable.
    const campoTotal = (await screen.findByText('Total de la cartera (USD)')).closest('div')
    expect(within(campoTotal as HTMLElement).getByText('US$ 990,00')).toBeInTheDocument()
  })
})

// --- Etapa 3: el mix pedido y el mix real de la cabecera --------------------------------------------

describe('el mix RF/RV de la cabecera', () => {
  it('el mix pedido se calcula siempre que haya posiciones; el mix real exige las dos porciones resueltas', async () => {
    responderCon({ acciones: [accion({ precio: 30 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))
    await screen.findByRole('article', { name: 'GGAL' })

    // Única posición, 100% pedido a renta variable: el mix pedido es 0,0% / 100,0%.
    const campoMixPedido = (await screen.findByText('Mix pedido RF/RV')).closest('div')
    expect(within(campoMixPedido as HTMLElement).getByText('0,0% / 100,0%')).toBeInTheDocument()

    const campoSumaRv = (await screen.findByText('Σ pedido RV')).closest('div')
    expect(within(campoSumaRv as HTMLElement).getByText('100,0%')).toBeInTheDocument()

    // El mix real necesita renta fija resuelta, que acá no hay (s/d, no 0): no se muestra un mix
    // a medias que sugeriría que la renta fija pesa 0% cuando en realidad no se sabe.
    const campoMixReal = (await screen.findByText('Mix real RF/RV (sobre invertido)')).closest('div')
    expect(within(campoMixReal as HTMLElement).getByText('s/d')).toBeInTheDocument()
  })
})

// --- Regla 3: nunca se inventa un tipo de cambio externo -------------------------------------------

describe('una especie en ARS sin tipo de cambio', () => {
  it('la tarjeta declara peso e invertido sin dato, sin estimar nada', async () => {
    responderCon({
      cedears: [cedear({ ticker: 'PAMP', moneda_cotizacion: 'ARS' })],
      tipoDeCambio: { valor: null, disponible: false },
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'monto 1.000' }))
    // Agregamos PAMP a mano porque el arnés sólo expone GGAL; se reutiliza alternarRentaVariable
    // vía búsqueda para no exponer otro botón fijo en el arnés.
    await screen.findByRole('listitem')
    await userEvent.click(screen.getByRole('button', { name: 'agregar PAMP a la cartera' }))

    const tarjeta = await screen.findByRole('article', { name: 'PAMP' })
    const filaPeso = within(tarjeta).getByText('% real').closest('div')
    expect(within(filaPeso as HTMLElement).getByText('s/d')).toBeInTheDocument()
  })
})

// --- El buscador: agregar y sacar desde la lista, cambiar de clase -------------------------------

describe('el buscador de CEDEARs', () => {
  it('filtra por ticker y agrega con el botón +', async () => {
    responderCon({ cedears: [cedear(), cedear({ ticker: 'PAMP' })] })
    renderizar()

    await screen.findAllByRole('listitem')
    await userEvent.type(screen.getByRole('textbox', { name: /Buscar CEDEAR/i }), 'PAM')

    expect(screen.queryByText('AAPL')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'agregar PAMP a la cartera' }))

    expect(await screen.findByRole('article', { name: 'PAMP' })).toBeInTheDocument()
  })

  // --- Etapa 5 del rediseño del armador: sector, rubro y búsqueda por nombre --------------------

  it('busca por nombre además de por ticker', async () => {
    responderCon({
      cedears: [
        cedear({ nombre_corto: 'APPLE INC', nombre_largo: 'Apple Inc.' }),
        cedear({ ticker: 'PAMP', nombre_corto: 'PAMPA ENERGIA' }),
      ],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    await userEvent.type(screen.getByRole('textbox', { name: /Buscar CEDEAR/i }), 'apple')

    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'PAMP' })).not.toBeInTheDocument()
  })

  it('filtra por rubro, sólo con las especies de esa clase que lo declaran', async () => {
    responderCon({
      cedears: [
        cedear({ sic_oficina: 'Office of Finance' }),
        cedear({ ticker: 'PAMP', sic_oficina: 'Office of Energy & Transportation' }),
      ],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    await userEvent.selectOptions(screen.getByLabelText('Rubro (SEC)'), 'Office of Finance')

    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'PAMP' })).not.toBeInTheDocument()
  })

  it('filtra por eslabón productivo, que es la división del SIC y no una lectura nuestra', async () => {
    responderCon({
      cedears: [
        cedear({ division_cadena: 'Finanzas y seguros' }),
        cedear({ ticker: 'PAMP', division_cadena: 'Extracción' }),
      ],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    await userEvent.selectOptions(screen.getByLabelText('Eslabón productivo'), 'Extracción')

    expect(screen.getByRole('button', { name: 'PAMP' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'AAPL' })).not.toBeInTheDocument()
  })

  it('sin clasificar todavía, rubro y eslabón sólo ofrecen "todos" — no rompe la búsqueda', async () => {
    // El caso normal de un CEDEAR sin clasificación SEC todavía: cubre el 74 % (13/08/2026), no
    // el 100 %.
    responderCon({ cedears: [cedear(), cedear({ ticker: 'PAMP' })] })
    renderizar()
    await screen.findAllByRole('listitem')

    expect(screen.getByLabelText('Rubro (SEC)')).toHaveValue('')
    expect(screen.getByLabelText('Rubro (SEC)').children).toHaveLength(1) // sólo "todos"
    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
  })
})


describe('reemplazar una sugerencia', () => {
  // GGAL entra a la cartera con el botón directo del arnés (`alternarRentaVariable`, no el
  // picker): resuelve su rubro vía `useRentaVariableResuelta`, que sigue trayendo accion+cedear
  // para no romper una posición ya cargada (ver el comentario de esa decisión en
  // `useRentaVariableResuelta.ts`). El picker que se usa para *elegir el reemplazo* sólo lista
  // CEDEARs -- por eso el sustituto de estos tests siempre es un `cedear()`.
  it('saca la posición y deja el buscador enfocado para elegir otra', async () => {
    responderCon({
      acciones: [accion({ sic_oficina: 'Office of Finance' })],
      cedears: [cedear({ ticker: 'MSFT' })],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    // Se agrega a la cartera, que es lo que produce la tarjeta con sus acciones.
    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    const cambiar = await screen.findByRole('button', { name: 'reemplazar GGAL por otro activo' })

    await userEvent.click(cambiar)

    expect(
      screen.queryByRole('button', { name: 'reemplazar GGAL por otro activo' }),
    ).not.toBeInTheDocument()
    expect(screen.getByLabelText('Buscar CEDEAR por ticker o nombre')).toHaveFocus()
  })

  it('pre-filtra por el rubro de la que se saca: "otro banco, no este"', async () => {
    responderCon({
      acciones: [accion({ sic_oficina: 'Office of Finance' })],
      // El select sólo puede mostrar seleccionado un rubro que exista como opción -- por eso
      // hace falta un CEDEAR con el mismo rubro de GGAL además de PAMP, aunque el test no agregue
      // ese CEDEAR a la cartera.
      cedears: [
        cedear({ sic_oficina: 'Office of Finance' }),
        cedear({ ticker: 'PAMP', sic_oficina: 'Office of Energy & Transportation' }),
      ],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'reemplazar GGAL por otro activo' }))

    expect(screen.getByLabelText('Rubro (SEC)')).toHaveValue('Office of Finance')
    expect(screen.queryByRole('button', { name: 'PAMP' })).not.toBeInTheDocument()
  })

  it('sin rubro declarado no inventa un filtro: la búsqueda queda abierta', async () => {
    responderCon({
      acciones: [accion({ sic_oficina: null })],
      cedears: [cedear({ ticker: 'PAMP', sic_oficina: 'Office of Energy & Transportation' })],
    })
    renderizar()
    await screen.findAllByRole('listitem')

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL directo' }))
    await userEvent.click(screen.getByRole('button', { name: 'reemplazar GGAL por otro activo' }))

    expect(screen.getByLabelText('Rubro (SEC)')).toHaveValue('')
    expect(screen.getByRole('button', { name: 'PAMP' })).toBeInTheDocument()
  })
})


describe('un papel con sus monedas de liquidación', () => {
  /** Apple en pesos, MEP y cable: el mismo CEDEAR, tres especies. */
  const APPLE = [
    cedear({ ticker: 'AAPL', emision: 'AAPL', moneda_cotizacion: 'ARS', precio: 24050 }),
    cedear({ ticker: 'AAPLD', emision: 'AAPL', sufijo_liquidacion: 'D', precio: 15.8 }),
    cedear({ ticker: 'AAPLC', emision: 'AAPL', sufijo_liquidacion: 'C', precio: 15.17 }),
  ]

  it('las tres especies son una sola fila, con un botón por moneda', async () => {
    responderCon({ cedears: APPLE })
    renderizar()

    const lista = await screen.findByRole('list', { name: /Resultados de CEDEARs/ })
    expect(within(lista).getAllByRole('listitem')).toHaveLength(1)
    for (const moneda of ['ARS', 'MEP', 'Cable']) {
      expect(within(lista).getByText(moneda)).toBeInTheDocument()
    }
  })

  it('cada moneda agrega su propia especie a la cartera', async () => {
    responderCon({ cedears: APPLE })
    renderizar()
    await screen.findByRole('list', { name: /Resultados de CEDEARs/ })

    await userEvent.click(screen.getByRole('button', { name: 'agregar AAPLD a la cartera' }))

    expect(await screen.findByRole('article', { name: 'AAPLD' })).toBeInTheDocument()
  })

  it('buscar por el ticker de una hermana encuentra el papel', async () => {
    responderCon({ cedears: APPLE })
    renderizar()
    await screen.findByRole('list', { name: /Resultados de CEDEARs/ })

    await userEvent.type(
      screen.getByLabelText('Buscar CEDEAR por ticker o nombre'),
      'AAPLC',
    )

    expect(screen.getByRole('button', { name: 'AAPL' })).toBeInTheDocument()
  })

  it('la moneda que no operó no se puede agregar: sin precio no se valúa', async () => {
    responderCon({
      cedears: [
        cedear({ ticker: 'AAPL', emision: 'AAPL', moneda_cotizacion: 'ARS', precio: 24050 }),
        cedear({ ticker: 'AAPLD', emision: 'AAPL', sufijo_liquidacion: 'D', precio: null }),
      ],
    })
    renderizar()
    await screen.findByRole('list', { name: /Resultados de CEDEARs/ })

    expect(screen.getByRole('button', { name: 'agregar AAPLD a la cartera' })).toBeDisabled()
  })

  it('una especie que la fuente no explica se declara con n/n', async () => {
    responderCon({
      cedears: [cedear({ ticker: 'AAPLB', emision: 'n/n', no_identificado: true })],
    })
    renderizar()

    const lista = await screen.findByRole('list', { name: /Resultados de CEDEARs/ })
    expect(within(lista).getByText('n/n')).toBeInTheDocument()
  })
})


describe('qué es cada papel', () => {
  it('muestra nombre, actividad y eslabón de la cadena', async () => {
    responderCon({
      cedears: [
        cedear({
          ticker: 'AAPL',
          nombre_largo: 'Apple Inc.',
          sic_codigo: '3571',
          sic_titulo: 'Electronic Computers',
          division_cadena: 'Manufactura',
        }),
      ],
    })
    renderizar()

    const lista = await screen.findByRole('list', { name: /Resultados de CEDEARs/ })
    expect(within(lista).getByText('Apple Inc.')).toBeInTheDocument()
    expect(within(lista).getByText(/Electronic Computers · Manufactura/)).toBeInTheDocument()
  })

  it('un fondo muestra su estrategia en vez de una actividad', async () => {
    responderCon({
      cedears: [
        cedear({ ticker: 'GLD', nombre_largo: 'ETF SPDR GOLD TRUST', estrategia_etf: 'activo_fisico' }),
      ],
    })
    renderizar()

    const lista = await screen.findByRole('list', { name: /Resultados de CEDEARs/ })
    expect(within(lista).getByText(/fondo · activo físico/)).toBeInTheDocument()
  })

  it('un papel sin clasificar no muestra el sector de otro', async () => {
    // Las acciones argentinas: la SEC cubre el 9 %. Vacío declarado, nunca completado por analogía.
    responderCon({ cedears: [cedear({ ticker: 'GGAL', nombre_largo: null, sic_titulo: null })] })
    renderizar()

    const lista = await screen.findByRole('list', { name: /Resultados de CEDEARs/ })
    expect(within(lista).getByRole('button', { name: 'GGAL' })).toBeInTheDocument()
    expect(within(lista).queryByText(/Manufactura|Electronic/)).not.toBeInTheDocument()
  })
})
