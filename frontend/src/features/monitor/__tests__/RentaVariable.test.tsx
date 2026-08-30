/**
 * Los GWT de F-052 (renta variable en el monitor) vistos desde la pantalla.
 *
 * Mismo patrón que `MonitorPage.test.tsx`: el segmento renta fija por defecto (`usd_hard`) trae
 * una sola especie mínima —hace falta para que la pestaña por defecto tenga algo que mostrar—, y
 * el foco de este archivo está en lo que pasa al activar la pestaña de CEDEARs.
 *
 * Sólo CEDEARs desde el 14/08/2026: la pestaña "Acciones" se sacó del monitor (pedido del dueño
 * del producto — la mayoría de las acciones argentinas no opera nunca). `CLAVES_RENTA_VARIABLE`
 * (`components/SelectorSegmento.tsx`) quedó en `['cedear']`, así que no hay una sub-pestaña propia
 * de "CEDEARs" que clickear: activar la familia "Renta variable" (reorganización del mismo día, ver
 * `MonitorPage.tsx`) va directo a la tabla, sin sub-barra de una sola opción.
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
    subtipo: null,
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
    residual: 100.0,
    valor_tecnico: 71.4,
    sector: null,
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    fuente: null,
  }
}

function especieRV(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  return {
    ticker: 'GGAL',
    clase_activo: 'cedear',
    precio: 1000.0,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 950.0,
    variacion: (1000.0 - 950.0) / 950.0,
    volumen: 1_500_000_000,
    volumen_usd: 1_000_000,
    px_bid: 995.0,
    px_ask: 1005.0,
    operaciones: 50,
    fuente: null,
    emision: null,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    sector_codigo: null,
    sector: null,
    rubro_especifico: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    region_etf: null,
    etf_indice: null,
    etf_alcance: null,
    etf_pais: null,
    etf_region: null,
    etf_geo_fuente: null,
    etf_geo_verificado: null,
    pais: null,
    region: null,
    pais_fuente: null,
    pais_verificado: null,
    ...extra,
  }
}

// GGAL y PAMP en ARS, LOMA en USD. El crudo de GGAL (1.500 MM de pesos) es ~750 veces el de LOMA
// (2,0 MM de dólares) y los dos son el mismo orden de magnitud en plata: es el caso que hacía
// incomparable la columna de volumen mientras las tres monedas convivían en la tabla. Desde el
// 08/08/2026 no conviven —el selector de moneda deja una sola a la vista— y por eso el volumen se
// puede mostrar crudo. PAMP no tiene cierre anterior ni puntas: es el caso "cero" de la cobertura.
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
// Una acción en `EXT`: la fuente declara la moneda pero no documenta qué denota, así que su volumen
// llega sin convertir (regla 11). Existe acá para fijar que igual se muestra, en su propia pestaña
// de moneda y con su volumen crudo — no se esconde ni se mezcla con las otras dos.
const TXAR = especieRV({
  ticker: 'TXAR',
  precio: 44.5,
  moneda_cotizacion: 'EXT',
  cierre_anterior: 44.0,
  variacion: (44.5 - 44.0) / 44.0,
  volumen: 900_000,
  volumen_usd: null,
  px_bid: 44.4,
  px_ask: 44.6,
  operaciones: 12,
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
      if (clase === 'cedear') return respuestaJson(pagina([GGAL, LOMA, PAMP, TXAR]))
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

/** Abre Renta variable (única sub-clase: CEDEARs), que arranca en ARS: GGAL y PAMP. LOMA está en
 *  USD y TXAR en EXT. */
async function irALaPestanaDeCedears() {
  const resultado = renderizar()
  await userEvent.click(await screen.findByRole('button', { name: 'Renta variable' }))
  await screen.findByText('2 de 2 especies en ARS')
  return resultado
}

/** El chip de una moneda del selector, que lleva su conteo al lado del código. */
function chipDeMoneda(codigo: string) {
  return screen.getByRole('radio', { name: new RegExp(`^${codigo}`) })
}

// --- GWT-1: columnas de renta variable, sin rendimiento ni nada en su lugar ----------------------

describe('GWT-1: las pestañas de renta variable no tienen columna de rendimiento', () => {
  it('activar Renta variable no deja una sub-barra: va directo a la tabla', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    expect(screen.queryByRole('button', { name: 'CEDEARs' })).not.toBeInTheDocument()
  })

  it('las columnas son precio, variación, volumen, compra y venta — sin rendimiento ni TIR', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    // Anclado a la palabra entera desde F-078: el chip temático "Metales preciosos" también
    // contiene "precio", y un `/precio/i` suelto encuentra los dos.
    expect(screen.getByRole('button', { name: /^precio$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /variación/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^volumen/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /compra/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /venta/i })).toBeInTheDocument()
    expect(screen.queryByText(/rendimiento/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/TIR/)).not.toBeInTheDocument()
  })
})

// --- GWT-2: el volumen se ordena dentro de una moneda, nunca entre monedas ------------------------
//
// Reescrito el 08/08/2026. El GWT original exigía ordenar por `volumen_usd` y no por el nominal, y
// la razón era que la columna mezclaba monedas: el crudo de GGAL (1.500 MM de pesos) aplastaba al de
// LOMA (2,0 MM de dólares) sin que ninguno de los dos operara más. El problema es el mismo y la
// solución cambió: con el selector de moneda no hay dos monedas en la tabla a la vez, así que el
// crudo es comparable por construcción y no hace falta convertir nada — que es lo que la regla 11
// exige para las especies `EXT`, cuya conversión no se puede calcular.

describe('GWT-2: la columna de volumen nunca compara dos monedas', () => {
  it('en ARS sólo están las especies en ARS, y ordenan entre ellas por el volumen publicado', async () => {
    mockearApi()
    const { container } = await irALaPestanaDeCedears()

    const cabeceraVolumen = screen.getByRole('button', { name: /^volumen/i })
    await userEvent.click(cabeceraVolumen) // asc
    await userEvent.click(cabeceraVolumen) // desc

    const tickerDeCadaFila = () =>
      Array.from(container.querySelectorAll('div[role="button"]')).map((fila) => fila.textContent?.slice(0, 4))
    expect(tickerDeCadaFila()).toEqual(['GGAL', 'PAMP'])
    expect(screen.queryByText('LOMA')).not.toBeInTheDocument()
  })

  it('cambiar de moneda cambia la lista entera, y el conteo dice en cuál se está', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    await userEvent.click(chipDeMoneda('USD'))

    expect(await screen.findByText('1 de 1 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('LOMA')).toBeInTheDocument()
    expect(screen.queryByText('GGAL')).not.toBeInTheDocument()
  })

  it('las especies en EXT se muestran igual, en su propia moneda y con su volumen crudo', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    await userEvent.click(chipDeMoneda('EXT'))

    expect(await screen.findByText('1 de 1 especies en EXT')).toBeInTheDocument()
    expect(screen.getByText('TXAR')).toBeInTheDocument()
    // 900.000 con `fmtCompacto`, que abrevia a la argentina: M son miles y MM son millones. Que
    // `volumen_usd` sea null no la deja sin columna: lo que no se puede calcular es la conversión,
    // no el dato que BYMA publicó.
    expect(screen.getByText('900,0 M')).toBeInTheDocument()
  })

  it('el selector declara que los códigos son de BYMA y no los traduce', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    expect(screen.getByText(/Denominación declarada por BYMA, sin traducir/)).toBeInTheDocument()
    expect(screen.queryByText(/cable/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/\bMEP\b/)).not.toBeInTheDocument()
  })
})

// --- GWT-3: lo que BYMA no publica queda vacío y contado ------------------------------------------

describe('GWT-3: un campo que BYMA no publica queda vacío y contado en la nota de cobertura', () => {
  it('PAMP muestra s/d en variación y puntas, y la nota declara los faltantes', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

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
    await irALaPestanaDeCedears()

    expect(await screen.findByText(/535 sin segmento no se muestran acá/)).toBeInTheDocument()
  })
})

// --- Mecánica heredada: clic en una fila navega, el conteo está visible --------------------------

describe('mecánica heredada de la grilla', () => {
  it('clic en una fila navega a la ficha del instrumento', async () => {
    mockearApi()
    await irALaPestanaDeCedears()

    await userEvent.click(screen.getByText('GGAL'))

    expect(await screen.findByText('ficha de GGAL')).toBeInTheDocument()
  })
})

// --- Una clase sin filas hoy: "0 de 0", no error ni pantalla rota --------------------------------

describe('una clase sin filas hoy', () => {
  it('la pestaña de CEDEARs sin datos declara la etiqueta de la pestaña activa', async () => {
    // Mock propio, no `mockearApi()`: ese devuelve el universo lleno para `clase=cedear`, y acá
    // se prueba justo el caso contrario.
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
        return respuestaJson(pagina([]))
      }
      throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderizar()
    await userEvent.click(await screen.findByRole('button', { name: 'Renta variable' }))

    expect(await screen.findByText('0 de 0 especies')).toBeInTheDocument()
    expect(screen.getByText('No hay CEDEARs en el universo de hoy.')).toBeInTheDocument()
    // Sin especies no hay monedas que ofrecer: el selector no se dibuja vacío.
    expect(screen.queryByRole('radiogroup', { name: 'Moneda de cotización' })).not.toBeInTheDocument()
  })
})
