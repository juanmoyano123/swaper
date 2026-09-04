/**
 * Los GWT de F-038 vistos desde la pantalla.
 *
 * El fetch mock responde `/segmentos` una sola vez y parte el segmento `usd_hard` en dos páginas
 * de `/especies` (con `next_cursor` la primera, `null` la segunda): es lo que prueba que
 * `useUniversoSegmento` concatena el segmento entero antes de que la tabla ordene o filtre nada.
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
import type { FondoFci } from '@/lib/fci'
import { fmtFechaHora } from '@/lib/fmt'

import { MonitorPage } from '../MonitorPage'
import type { Especie, Segmentos } from '../lib/schema'

// jsdom no calcula layout: sin esto, `@tanstack/react-virtual` mide un contenedor de alto cero y
// no renderiza ninguna fila. El alto fijo espeja el `ALTO_CONTENEDOR` de `TablaUniverso`.
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

function especie(extra: Partial<Especie> = {}): Especie {
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
    capturado_en: null,
    ...extra,
  }
}

// AL30 10%/2,5a y GD30 15%/5a alcanzan y sobran para el segmento usd_hard; AE38 no publica
// rendimiento (el caso de "s/d" y de exclusión del filtro y de la curva) pero sí duración, para
// aislar que lo que la excluye es el rendimiento faltante y no la duración.
const AL30 = especie()
const GD30 = especie({ ticker: 'GD30', emision: 'GD30', rendimiento: 0.15, duracion: 5.0 })
const AE38 = especie({ ticker: 'AE38', emision: 'AE38', ley: null, rendimiento: null, duracion: 3.0 })
const TX26 = especie({
  ticker: 'TX26',
  emision: 'TX26',
  segmento: 'cer',
  naturaleza: 'tasa_real_cer',
  naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)',
  rendimiento: 0.05,
  duracion: 1.0,
})
// Una ON en el dólar hard, para tener más de un crédito en el segmento y que `SelectorCredito`
// dibuje sus chips — con un solo crédito presente el selector no se muestra (nada que elegir).
const YMCHO = especie({
  ticker: 'YMCHO',
  emision: 'YMCHO',
  clase_activo: 'on_corporativo',
  rendimiento: 0.12,
  duracion: 1.8,
})

function segmentosResponse(): Segmentos {
  return {
    segmentos: [
      {
        clave: 'usd_hard',
        nombre: 'Hard dollar',
        naturaleza: 'tir_usd',
        naturaleza_nombre: 'TIR en dólares (hard dollar)',
        especies: 3,
      },
      {
        clave: 'cer',
        nombre: 'CER',
        naturaleza: 'tasa_real_cer',
        naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)',
        especies: 1,
      },
    ],
    renta_variable: 1417,
    sin_segmento: 535,
  }
}

function pagina(items: Especie[], next_cursor: string | null = null) {
  return { items, next_cursor }
}

function respuestaJson(cuerpo: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }),
  )
}

function mockearApi() {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')

    if (url.pathname === '/api/v1/universo/segmentos') {
      return respuestaJson(segmentosResponse())
    }

    if (url.pathname === '/api/v1/universo/emisiones/especies') {
      const segmento = url.searchParams.get('segmento')
      const cursor = url.searchParams.get('cursor')

      if (segmento === 'usd_hard') {
        // El bucle de páginas: la primera trae dos especies y un cursor, la segunda trae la
        // tercera y corta con `next_cursor: null`.
        if (cursor === null) return respuestaJson(pagina([AL30, GD30], 'pagina-2'))
        if (cursor === 'pagina-2') return respuestaJson(pagina([AE38]))
      }
      if (segmento === 'cer') return respuestaJson(pagina([TX26]))
    }

    throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Un único segmento (`usd_hard`) con tres soberanos y una ON, para ejercitar los chips de crédito. */
function mockearApiConCredito() {
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
            especies: 4,
          },
        ],
        renta_variable: 0,
        sin_segmento: 0,
      })
    }
    if (url.pathname === '/api/v1/universo/emisiones/especies') {
      return respuestaJson(pagina([AL30, GD30, AE38, YMCHO]))
    }

    throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Un único segmento (`usd_hard`) con las especies que el test quiera, para casos que necesitan
 *  más de una fila pero no el crédito ni las hermanas que trae `mockearApiConCredito`. */
function mockearApiConEspecies(especies: Especie[]) {
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
            especies: especies.length,
          },
        ],
        renta_variable: 0,
        sin_segmento: 0,
      })
    }
    if (url.pathname === '/api/v1/universo/emisiones/especies') {
      return respuestaJson(pagina(especies))
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

// --- Unidad: rendimiento y paridad viajan como fracción, la celda los muestra en puntos ----------
//
// `rendimiento`, `tir`, `tna` y `paridad` son fracciones en el backend (`TOPE_SANIDAD_SEGMENTO` de
// `sanidad.py` es 3.0 = 300% de TIR; `cupones.py` calcula el precio sucio como `paridad *
// valor_tecnico`, o sea paridad 1.0 = a la par). `fmtPct` espera puntos porcentuales, así que la
// celda multiplica ×100 antes de formatear — igual que ya hace `RenglonPapel` en el armador. Este
// test fija esa conversión con un valor que no admite ambigüedad de escala.

function mockearApiConUnaEspecie(especie: Especie) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')

    if (url.pathname === '/api/v1/universo/segmentos') {
      return respuestaJson({
        segmentos: [
          {
            clave: especie.segmento,
            nombre: 'Hard dollar',
            naturaleza: especie.naturaleza,
            naturaleza_nombre: especie.naturaleza_nombre,
            especies: 1,
          },
        ],
        renta_variable: 0,
        sin_segmento: 0,
      })
    }
    if (url.pathname === '/api/v1/universo/emisiones/especies') return respuestaJson(pagina([especie]))

    throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('rendimiento y paridad: fracción en el dato, puntos porcentuales en la celda', () => {
  it('0,0792 de rendimiento se muestra como "7,92%" y 0,9234 de paridad como "92,34%"', async () => {
    mockearApiConUnaEspecie(especie({ rendimiento: 0.0792, paridad: 0.9234 }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(fila).not.toBeNull()
    expect(fila).toHaveTextContent('7,92%')
    expect(fila).toHaveTextContent('92,34%')
    // Ni la fracción cruda ni un ×100 mal aplicado (792,00% o 9.234,00%) tienen que aparecer.
    expect(fila).not.toHaveTextContent('0,08%')
    expect(fila).not.toHaveTextContent('792,00%')
  })

  it('una fila con rendimiento y duración entra a la curva del segmento, no a la nota de excluidas', async () => {
    // Recharts no dibuja el SVG completo en jsdom (falta layout real), así que lo que se puede
    // afirmar acá es lo que decide `CurvaSegmento.tsx` en JS puro: con los dos números presentes,
    // la fila cuenta como punto y no como excluida. La escala ×100 del eje y de la celda es la
    // misma función (`especie.rendimiento * 100`) que ya prueba el test anterior.
    mockearApiConUnaEspecie(especie({ rendimiento: 0.0792, duracion: 4.0, paridad: 0.9234 }))
    renderizar()
    await screen.findByText('1 de 1 especies en USD')

    expect(screen.queryByText(/no están en la curva/)).not.toBeInTheDocument()
    expect(screen.queryByText(/no hay curva que dibujar/)).not.toBeInTheDocument()
  })
})

describe('residual: cuánto capital queda vivo (relevamiento de confiabilidad de datos, 17/08/2026)', () => {
  it('muestra el residual calculado en la fila de la especie', async () => {
    mockearApiConUnaEspecie(especie({ residual: 60.0, valor_tecnico: 62.3 }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(fila).toHaveTextContent('60,0')
  })

  it('sin cronograma o con residual incoherente, declara sin dato en vez de 100 o de 0', async () => {
    mockearApiConUnaEspecie(especie({ residual: null, valor_tecnico: null }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(fila).toHaveTextContent('s/d')
  })
})

describe('sin precio: por qué está en s/d, sin tener que abrir la ficha', () => {
  it('con capturado_en, declara la fecha del último dato conocido', async () => {
    mockearApiConUnaEspecie(
      especie({ precio: null, capturado_en: '2026-08-20T20:00:02.098529+00:00' }),
    )
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    const celdaPrecio = within(fila as HTMLElement).getByText('s/d')
    expect(celdaPrecio.getAttribute('title')).toBe(
      'sin precio en la corrida de hoy; el último dato conocido es del 20/08/2026, 17:00',
    )
  })

  it('sin capturado_en, declara que nunca tuvo un precio registrado', async () => {
    mockearApiConUnaEspecie(especie({ precio: null, capturado_en: null }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    const celdaPrecio = within(fila as HTMLElement).getByText('s/d')
    expect(celdaPrecio.getAttribute('title')).toBe(
      'nunca tuvo un precio registrado desde que está en el universo',
    )
  })

  it('con precio, no lleva título explicativo', async () => {
    mockearApiConUnaEspecie(especie({ precio: 62.5, capturado_en: '2026-08-30T20:00:00Z' }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    const celdaPrecio = within(fila as HTMLElement).getByText('62,50')
    expect(celdaPrecio.getAttribute('title')).toBeNull()
  })
})

describe('columna "último dato": la antigüedad se ve sin pasar el mouse', () => {
  it('sin capturado_en, la celda dice "nunca"', async () => {
    mockearApiConUnaEspecie(especie({ capturado_en: null }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(fila).toHaveTextContent('nunca')
  })

  it('con capturado_en de hace 17 días, la celda dice "hace 17 días" y el título trae la hora exacta', async () => {
    const hace17dias = new Date(Date.now() - 17 * 24 * 60 * 60 * 1000).toISOString()
    mockearApiConUnaEspecie(especie({ precio: null, capturado_en: hace17dias }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    const celdaUltimoDato = within(fila as HTMLElement).getByText('hace 17 días')
    expect(celdaUltimoDato.getAttribute('title')).toBe(fmtFechaHora(hace17dias))
  })

  it('una fila recién capturada dice "hace N min", no una fecha vieja', async () => {
    mockearApiConUnaEspecie(especie({ capturado_en: new Date().toISOString() }))
    renderizar()

    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(fila).toHaveTextContent(/hace \d+ min/)
  })

  it('la cabecera "último dato" ordena por antigüedad, con "nunca" siempre al final', async () => {
    const hace1dia = new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()
    const hace10dias = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString()
    mockearApiConEspecies([
      especie({ ticker: 'AL30', emision: 'AL30', capturado_en: hace10dias }),
      especie({ ticker: 'GD30', emision: 'GD30', capturado_en: hace1dia }),
      especie({ ticker: 'AE38', emision: 'AE38', capturado_en: null }),
    ])
    const { container } = renderizar()
    await screen.findByText('3 de 3 especies en USD')

    const tickerDeCadaFila = () =>
      Array.from(container.querySelectorAll('div[role="button"]')).map((fila) => fila.textContent?.slice(0, 4))

    const cabecera = screen.getByRole('button', { name: 'último dato' })
    await userEvent.click(cabecera) // asc: la fecha ISO más chica primero → el más viejo primero
    expect(tickerDeCadaFila()).toEqual(['AL30', 'GD30', 'AE38'])

    await userEvent.click(cabecera) // desc: el más reciente primero, "nunca" sigue último
    expect(tickerDeCadaFila()).toEqual(['GD30', 'AL30', 'AE38'])
  })
})

// --- GWT-1: un segmento activo por vez, con la unidad de rendimiento declarada -------------------

describe('un solo segmento a la vez', () => {
  it('la unidad de rendimiento de la cabecera y de los filtros cambia con el segmento activo', async () => {
    mockearApi()
    renderizar()

    expect(await screen.findByRole('button', { name: /rendimiento \(TIR USD\)/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/Rendimiento mín\. \(TIR USD\)/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'CER' }))

    expect(await screen.findByRole('button', { name: /rendimiento \(Tasa real CER\)/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/Rendimiento mín\. \(Tasa real CER\)/)).toBeInTheDocument()
    // Un solo segmento a la vez: no puede quedar ni rastro de la unidad del segmento anterior.
    expect(screen.queryByText(/TIR USD/)).not.toBeInTheDocument()
  })

  it('declara lo que no está en ninguna pestaña', async () => {
    mockearApi()
    renderizar()

    expect(await screen.findByText(/535 sin segmento no se muestran acá/)).toBeInTheDocument()
  })
})

// --- Jerarquía de dos niveles: familia arriba, segmento (tipo de tasa) adentro --------------------

describe('jerarquía de dos niveles: familia arriba, segmento adentro', () => {
  it('arranca en Renta fija, con Dólar hard como segmento activo y sin pestañas de crédito', async () => {
    mockearApi()
    renderizar()

    const rf = await screen.findByRole('button', { name: 'Renta fija' })
    expect(rf).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('button', { name: 'Renta variable' })).toBeInTheDocument()

    const dolarHard = screen.getByRole('button', { name: 'Dólar hard' })
    expect(dolarHard).toHaveAttribute('aria-current', 'true')
    // El crédito ya no se elige como pestaña: no hay botón "Soberanos" ni "ONs" en la barra.
    expect(screen.queryByRole('button', { name: 'Soberanos' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ONs' })).not.toBeInTheDocument()
  })

  it('sin renta variable en el universo, la pestaña de familia no se dibuja', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = new URL(String(input), 'http://localhost')
      if (url.pathname === '/api/v1/universo/segmentos') {
        return respuestaJson({ ...segmentosResponse(), renta_variable: 0 })
      }
      if (url.pathname === '/api/v1/universo/emisiones/especies') {
        const segmento = url.searchParams.get('segmento')
        const cursor = url.searchParams.get('cursor')
        if (segmento === 'usd_hard') {
          if (cursor === null) return respuestaJson(pagina([AL30, GD30], 'pagina-2'))
          if (cursor === 'pagina-2') return respuestaJson(pagina([AE38]))
        }
        if (segmento === 'cer') return respuestaJson(pagina([TX26]))
      }
      throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderizar()

    await screen.findByText('3 de 3 especies en USD')
    expect(screen.queryByText('Renta fija')).not.toBeInTheDocument()
    expect(screen.queryByText('Renta variable')).not.toBeInTheDocument()
  })
})

// --- Chips de crédito: Todos por defecto, generalizado a cualquier segmento -----------------------

describe('chips de crédito dentro del segmento', () => {
  it('con un solo crédito presente no se dibuja el selector', async () => {
    mockearApi() // usd_hard sólo con bono_soberano (AL30, GD30, AE38)
    renderizar()

    await screen.findByText('3 de 3 especies en USD')
    expect(screen.queryByRole('radiogroup', { name: 'Crédito' })).not.toBeInTheDocument()
  })

  it('con más de un crédito, muestra Todos primero y cada chip con su conteo', async () => {
    mockearApiConCredito()
    renderizar()

    const radiogroup = await screen.findByRole('radiogroup', { name: 'Crédito' })
    expect(within(radiogroup).getByRole('radio', { name: /^Todos/ })).toHaveAttribute('aria-checked', 'true')
    expect(within(radiogroup).getByRole('radio', { name: 'Todos 4' })).toBeInTheDocument()
    expect(within(radiogroup).getByRole('radio', { name: /^Soberanos/ })).toBeInTheDocument()
    expect(within(radiogroup).getByRole('radio', { name: /^ONs/ })).toBeInTheDocument()
    expect(within(radiogroup).queryByRole('radio', { name: /^Subsoberanos/ })).not.toBeInTheDocument()
  })

  it('clickear un crédito filtra la tabla; volver a Todos la restaura', async () => {
    mockearApiConCredito()
    renderizar()

    await screen.findByText('4 de 4 especies en USD')
    await userEvent.click(screen.getByRole('radio', { name: /^ONs/ }))

    expect(await screen.findByText('1 de 1 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('YMCHO')).toBeInTheDocument()
    expect(screen.queryByText('AL30')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: /^Todos/ }))
    expect(await screen.findByText('4 de 4 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('AL30')).toBeInTheDocument()
    expect(screen.getByText('YMCHO')).toBeInTheDocument()
  })
})

// --- Sub-chip de subtipo soberano (28/08/2026) ---------------------------------------------------

describe('sub-chip de subtipo dentro de los soberanos', () => {
  // Dos soberanos con subclases distintas y una ON: alcanza para que el sub-chip tenga algo que
  // separar y para comprobar que la ON no lo hace aparecer.
  const S31G6 = especie({ ticker: 'S31G6', emision: 'S31G6', subtipo: 'letra', rendimiento: 0.2, duracion: 0.4 })
  const AL30_BONAR = especie({ ticker: 'AL30', emision: 'AL30', subtipo: 'bonar' })

  function mockearApiConSubtipos() {
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
              especies: 3,
            },
          ],
          renta_variable: 0,
          sin_segmento: 0,
        })
      }
      if (url.pathname === '/api/v1/universo/emisiones/especies') {
        return respuestaJson(pagina([AL30_BONAR, S31G6, YMCHO]))
      }

      throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  }

  it('con el crédito en Todos el sub-chip no se dibuja: el subtipo es del soberano, no del segmento', async () => {
    mockearApiConSubtipos()
    renderizar()

    await screen.findByRole('radiogroup', { name: 'Crédito' })
    expect(screen.queryByRole('radiogroup', { name: 'Subtipo soberano' })).not.toBeInTheDocument()
  })

  it('al elegir Soberanos aparece con sus subclases y sus conteos', async () => {
    mockearApiConSubtipos()
    renderizar()

    await userEvent.click(await screen.findByRole('radio', { name: /^Soberanos/ }))

    const sub = await screen.findByRole('radiogroup', { name: 'Subtipo soberano' })
    expect(within(sub).getByRole('radio', { name: 'Todos 2' })).toBeInTheDocument()
    expect(within(sub).getByRole('radio', { name: 'Letras 1' })).toBeInTheDocument()
    expect(within(sub).getByRole('radio', { name: 'Bonares 1' })).toBeInTheDocument()
  })

  it('elegir una subclase filtra la tabla dentro del crédito soberano', async () => {
    mockearApiConSubtipos()
    renderizar()

    await userEvent.click(await screen.findByRole('radio', { name: /^Soberanos/ }))
    expect(await screen.findByText('2 de 2 especies en USD')).toBeInTheDocument()

    await userEvent.click(await screen.findByRole('radio', { name: /^Letras/ }))

    expect(await screen.findByText('1 de 1 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('S31G6')).toBeInTheDocument()
    expect(screen.queryByText('AL30')).not.toBeInTheDocument()
  })

  it('cambiar el crédito apaga el subtipo en vez de dejarlo filtrando en fantasma', async () => {
    mockearApiConSubtipos()
    renderizar()

    await userEvent.click(await screen.findByRole('radio', { name: /^Soberanos/ }))
    await userEvent.click(await screen.findByRole('radio', { name: /^Letras/ }))
    expect(await screen.findByText('1 de 1 especies en USD')).toBeInTheDocument()

    // Los chips de crédito siguen ahí: el subtipo se neutraliza al contarlos, porque es una
    // dimensión hija. Sin eso, elegir Letras dejaba al asesor encerrado en el soberano.
    expect(screen.getByRole('radio', { name: /^ONs/ })).toBeInTheDocument()

    await userEvent.click(screen.getByRole('radio', { name: /^ONs/ }))

    // Sin el reseteo, el subtipo 'letra' seguiría activo y la ON —que no lo tiene— quedaría afuera.
    expect(await screen.findByText('1 de 1 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('YMCHO')).toBeInTheDocument()
    expect(screen.queryByRole('radiogroup', { name: 'Subtipo soberano' })).not.toBeInTheDocument()
  })
})

// --- Facetado en cascada: Ley/Sector/Calificación/Emisor, más los chips de crédito y moneda ------
//
// Cuatro especies con dos créditos y dos sectores cruzados: AL30 es el único soberano; de las tres
// ONs, YPFD y PAMP son O&G y BYMA es Financiera. El conteo "N de M" de la tabla sigue siendo
// crédito+moneda solamente (M no se mueve con sector/emisor: es una invariante de antes de esta
// feature, `deLaMoneda` en `MonitorPage.tsx`) — lo nuevo se verifica en las opciones de los
// selects, en el conteo del chip de crédito, y en el aviso de selecciones apagadas.

describe('facetado de la barra del universo', () => {
  const YPFD = especie({
    ticker: 'YPFD', emision: 'YPFD', clase_activo: 'on_corporativo',
    sector: 'O&G', emisor: 'YPF S.A.', ley: 'Ley N.Y.', rendimiento: 0.09,
  })
  const PAMP = especie({
    ticker: 'PAMP', emision: 'PAMP', clase_activo: 'on_corporativo',
    sector: 'O&G', emisor: 'Pampa Energía', ley: 'Ley Argentina', rendimiento: 0.08,
  })
  const BYMA = especie({
    ticker: 'BYMA', emision: 'BYMA', clase_activo: 'on_corporativo',
    sector: 'Financiera', emisor: 'Banco Galicia', ley: 'Ley Argentina', rendimiento: 0.07,
  })
  const AL30_SOB = especie({
    ticker: 'AL30', emision: 'AL30', clase_activo: 'bono_soberano',
    sector: 'Soberano', emisor: 'Tesoro Nacional', ley: 'Ley Argentina', rendimiento: 0.1,
  })

  function mockearApiConSector() {
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
              especies: 4,
            },
          ],
          renta_variable: 0,
          sin_segmento: 0,
        })
      }
      if (url.pathname === '/api/v1/universo/emisiones/especies') {
        return respuestaJson(pagina([AL30_SOB, YPFD, PAMP, BYMA]))
      }
      throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  }

  function opcionesDe(etiqueta: string) {
    return Array.from(screen.getByLabelText(etiqueta).children).map((o) => o.textContent)
  }

  it('elegir Sector deja en Emisor sólo los emisores de ese sector', async () => {
    mockearApiConSector()
    renderizar()
    await screen.findByText('4 de 4 especies en USD')

    expect(opcionesDe('Emisor')).toEqual([
      'todos', 'Banco Galicia', 'Pampa Energía', 'Tesoro Nacional', 'YPF S.A.',
    ])

    await userEvent.selectOptions(screen.getByLabelText('Sector'), 'O&G')

    expect(opcionesDe('Emisor')).toEqual(['todos', 'Pampa Energía', 'YPF S.A.'])
    // El select propio no se acota a sí mismo.
    expect(opcionesDe('Sector')).toEqual(['todos', 'Financiera', 'O&G', 'Soberano'])
    // El "M" del conteo sigue siendo el segmento entero (crédito+moneda, no sector): la tabla
    // filtra las dos que no son O&G, la denominación no cambia.
    expect(await screen.findByText('2 de 4 especies en USD')).toBeInTheDocument()
  })

  it('y la inversa: elegir Emisor deja en Sector sólo el suyo', async () => {
    mockearApiConSector()
    renderizar()
    await screen.findByText('4 de 4 especies en USD')

    await userEvent.selectOptions(screen.getByLabelText('Emisor'), 'YPF S.A.')

    expect(opcionesDe('Sector')).toEqual(['todos', 'O&G'])
    expect(await screen.findByText('1 de 4 especies en USD')).toBeInTheDocument()
  })

  it('el conteo del chip de crédito respeta el filtro de ley', async () => {
    mockearApiConSector()
    renderizar()

    expect(await screen.findByRole('radio', { name: 'Todos 4' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /^ONs/ })).toHaveTextContent('3')
    expect(screen.getByRole('radio', { name: /^Soberanos/ })).toHaveTextContent('1')

    // Bajo Ley Argentina sólo quedan dos de las tres ONs (YPFD es Ley N.Y.): el chip lo dice, y el
    // soberano (también Ley Argentina) no se mueve.
    await userEvent.selectOptions(screen.getByLabelText('Ley'), 'Ley Argentina')

    expect(await screen.findByRole('radio', { name: 'Todos 3' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /^ONs/ })).toHaveTextContent('2')
    expect(screen.getByRole('radio', { name: /^Soberanos/ })).toHaveTextContent('1')
  })

  it('el chip de crédito desaparece cuando el resto de los filtros ya no deja nada que separar', async () => {
    mockearApiConSector()
    renderizar()
    await screen.findByRole('radio', { name: 'Todos 4' })

    // Bajo el sector O&G sólo hay ONs (YPFD y PAMP): no queda nada que el chip pueda separar.
    await userEvent.selectOptions(screen.getByLabelText('Sector'), 'O&G')

    await screen.findByText('2 de 4 especies en USD')
    expect(screen.queryByRole('radiogroup', { name: 'Crédito' })).not.toBeInTheDocument()
  })

  it('una selección sin respaldo se apaga, se declara, y no deja la barra sin controles', async () => {
    mockearApiConSector()
    renderizar()
    await screen.findByText('4 de 4 especies en USD')

    await userEvent.selectOptions(screen.getByLabelText('Sector'), 'O&G')
    await userEvent.selectOptions(screen.getByLabelText('Emisor'), 'Pampa Energía')
    // Un rango de rendimiento que Pampa (8%) no cumple.
    await userEvent.type(screen.getByLabelText(/Rendimiento mín/), '50')

    expect(await screen.findByText('Ninguna especie pasa los filtros activos.')).toBeInTheDocument()
    // Los selects y el input siguen montados e interactuables: no desaparece la barra.
    expect(screen.getByLabelText('Sector')).toBeInTheDocument()
    expect(screen.getByLabelText('Emisor')).toBeInTheDocument()
    expect(screen.getByLabelText(/Rendimiento mín/)).toBeInTheDocument()
  })

  it('limpiar filtros también vacía sector, emisor y calificación', async () => {
    mockearApiConSector()
    renderizar()
    await screen.findByText('4 de 4 especies en USD')

    await userEvent.selectOptions(screen.getByLabelText('Sector'), 'O&G')
    await screen.findByText('2 de 4 especies en USD')

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('4 de 4 especies en USD')).toBeInTheDocument()
    expect(screen.getByLabelText('Sector')).toHaveValue('')
  })
})

// --- GWT-2: orden + dos filtros numéricos, con el conteo siempre visible -------------------------

describe('orden y filtros del universo cargado', () => {
  it('el conteo arranca en "N de M" con el segmento entero, sin filtros', async () => {
    mockearApi()
    renderizar()

    expect(await screen.findByText('3 de 3 especies en USD')).toBeInTheDocument()
  })

  it('ordenar por rendimiento y aplicar dos filtros numéricos deja las filas correctas y actualiza el conteo', async () => {
    mockearApi()
    const { container } = renderizar()

    await screen.findByText('3 de 3 especies en USD')

    const cabeceraRendimiento = screen.getByRole('button', { name: /rendimiento \(TIR USD\)/ })
    await userEvent.click(cabeceraRendimiento) // asc
    await userEvent.click(cabeceraRendimiento) // desc: GD30 (15%) antes que AL30 (10%), null al final

    const tickerDeCadaFila = () =>
      Array.from(container.querySelectorAll('div[role="button"]')).map((fila) => fila.textContent?.slice(0, 4))
    expect(tickerDeCadaFila()).toEqual(['GD30', 'AL30', 'AE38'])

    // Dos filtros numéricos: entre 12% y 20% sólo entra GD30 (15%). AL30 (10%) y AE38 (s/d) quedan
    // afuera — AE38 porque un filtro de rendimiento activo no puede afirmar que un s/d lo cumple.
    await userEvent.type(screen.getByLabelText(/Rendimiento mín\. \(TIR USD\)/), '12')
    await userEvent.type(screen.getByLabelText(/Rendimiento máx\. \(TIR USD\)/), '20')

    expect(await screen.findByText('1 de 3 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('GD30')).toBeInTheDocument()
    expect(screen.queryByText('AL30')).not.toBeInTheDocument()
    expect(screen.queryByText('AE38')).not.toBeInTheDocument()
  })

  it('limpiar filtros vuelve a mostrar el segmento entero', async () => {
    mockearApi()
    renderizar()
    await screen.findByText('3 de 3 especies en USD')

    // "1" (1%) no excluye a AL30 (10%) ni a GD30 (15%): sólo deja afuera a AE38, sin rendimiento.
    await userEvent.type(screen.getByLabelText(/Rendimiento mín\. \(TIR USD\)/), '1')
    await screen.findByText('2 de 3 especies en USD') // afuera queda AE38: s/d no pasa un filtro activo

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('3 de 3 especies en USD')).toBeInTheDocument()
  })
})

// --- rendimiento null: s/d en la celda, afuera del filtro y de la curva ---------------------------

describe('una fila sin rendimiento publicado', () => {
  it('muestra s/d en la celda de rendimiento', async () => {
    mockearApi()
    renderizar()
    await screen.findByText('3 de 3 especies en USD')

    const filaAE38 = screen.getByText('AE38').closest('div[role="button"]')
    expect(filaAE38).not.toBeNull()
    expect(filaAE38).toHaveTextContent('s/d')
  })

  it('no pasa un filtro de rendimiento activo aunque el filtro esté abierto de más', async () => {
    mockearApi()
    renderizar()
    await screen.findByText('3 de 3 especies en USD')

    await userEvent.type(screen.getByLabelText(/Rendimiento mín\. \(TIR USD\)/), '0')

    await screen.findByText('2 de 3 especies en USD')
    expect(screen.queryByText('AE38')).not.toBeInTheDocument()
  })

  it('no entra a la curva y queda contada en la nota al pie', async () => {
    mockearApi()
    renderizar()

    expect(await screen.findByText(/1 especies sin rendimiento o duración no están en la curva/)).toBeInTheDocument()
  })
})

// --- Tipo y ley: columnas propias, con la clase traducida a etiqueta legible ----------------------

describe('las columnas de tipo y ley', () => {
  it('clase_activo se muestra con su etiqueta legible y la ley en su propia celda', async () => {
    mockearApiConUnaEspecie(especie({ clase_activo: 'on_corporativo', ley: 'Ley Argentina' }))
    renderizar()

    // Con una sola especie en el segmento hay un solo crédito presente: no hay chip que elegir,
    // se ve directo bajo "Todos" (el default).
    const fila = await screen.findByText('AL30').then((el) => el.closest('div[role="button"]'))
    expect(screen.queryByRole('radiogroup', { name: 'Crédito' })).not.toBeInTheDocument()
    expect(fila).not.toBeNull()
    expect(fila).toHaveTextContent('ON corporativa')
    expect(fila).toHaveTextContent('Ley Argentina')
    // El valor interno no se filtra a la pantalla.
    expect(fila).not.toHaveTextContent('on_corporativo')
  })

  it('una clase no reconocida y una ley ausente se declaran s/d, nunca celda muda', async () => {
    // En un segmento sin partición por crédito, como CER: ahí una clase desconocida sí se muestra,
    // y lo que se prueba es que `etiquetaClase` la declara en vez de dejar la celda muda.
    mockearApiConUnaEspecie(
      especie({
        ticker: 'TX26',
        segmento: 'cer',
        naturaleza: 'tasa_real_cer',
        naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)',
        moneda_cotizacion: 'ARS',
        clase_activo: 'clase_inventada',
        ley: null,
      }),
    )
    renderizar()

    const fila = await screen.findByText('TX26').then((el) => el.closest('div[role="button"]'))
    expect(fila).not.toBeNull()
    // Dos s/d: el de tipo y el de ley. El resto de la fila tiene todos sus datos.
    expect(within(fila as HTMLElement).getAllByText('s/d')).toHaveLength(2)
  })

  it('una clase que ningún chip de crédito reconoce se muestra igual, bajo Todos', async () => {
    // Antes de la reorganización del 14/08/2026, partir el segmento en pestañas de crédito podía
    // dejar afuera una clase de activo nueva sin que nada avisara. Con "Todos" como default eso ya
    // no pasa: la fila se ve igual, y la nota del chip de crédito declara cuántas quedan fuera de
    // los tres créditos reconocidos.
    mockearApiConUnaEspecie(especie({ clase_activo: 'clase_inventada' }))
    renderizar()

    expect(await screen.findByText('AL30')).toBeInTheDocument()
    expect(
      await screen.findByText(/1 especies con otra clase de activo sólo se ven en Todos/),
    ).toBeInTheDocument()
  })
})

// --- GWT-4: clic en una fila abre la ficha del instrumento ----------------------------------------

describe('clic en una fila', () => {
  it('navega a la ficha del instrumento', async () => {
    mockearApi()
    renderizar()
    await screen.findByText('3 de 3 especies en USD')

    await userEvent.click(screen.getByText('GD30'))

    expect(await screen.findByText('ficha de GD30')).toBeInTheDocument()
  })
})

// --- El bucle de páginas ---------------------------------------------------------------------------

describe('la carga del segmento entero', () => {
  it('concatena las dos páginas y corta cuando next_cursor es null', async () => {
    const fetchMock = mockearApi()
    renderizar()

    expect(await screen.findByText('3 de 3 especies en USD')).toBeInTheDocument()
    expect(screen.getByText('AL30')).toBeInTheDocument()
    expect(screen.getByText('GD30')).toBeInTheDocument()
    expect(screen.getByText('AE38')).toBeInTheDocument()

    const rutasPedidas = fetchMock.mock.calls.map(([input]) => new URL(String(input), 'http://localhost').search)
    expect(rutasPedidas.some((s) => s.includes('cursor=pagina-2'))).toBe(true)
  })
})

// --- FCI: tercera familia (F-057, 23/08/2026) ------------------------------------------------

function FichaFciFalsa() {
  const { codigoCafci } = useParams()
  return <div>ficha del fondo {codigoCafci}</div>
}

function renderizarConRutaFci() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={['/monitor']}>
        <Routes>
          <Route path="/monitor" element={<MonitorPage />} />
          <Route path="/fci/:codigoCafci" element={<FichaFciFalsa />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const FONDO_FCI: FondoFci = {
  codigo_cafci: '1031',
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
  vcp: 1500.0,
  vcp_anterior: 1490.0,
  var_diaria_pct: 0.67,
  var_mes_pct: 5.2,
  var_anio_pct: 40.1,
  var_12m_pct: 55.3,
  cuotapartes: 100.0,
  cuotapartes_anterior: 99.0,
  patrimonio: 10_000_000.0,
  patrimonio_anterior: 9_900_000.0,
  market_share: 1.2,
  gerente: 'Gainvest S.A.',
  depositaria: 'Banco X',
  calificacion: 'EF-3',
  calificado: 'Si',
  tipo_dinero: 'Ahorro',
  comision_ingreso: 0,
  honorarios_adm_sg: 2.0,
  honorarios_adm_sd: 0.3,
  gastos_ord_gestion: 0.1,
  comision_rescate: 0,
  comision_transferencia: 0,
  honorarios_exito: 0,
  moneda_fondo: 'ARS',
  discrepancia_moneda: false,
  plazo_liq: 1,
  dias_para_rescatar: 1,
  minimo_inversion: 1000.0,
  advertencia_distribucion: 'Los rendimientos no consideran distribución de utilidades.',
  enlace_composicion_cnv: null,
}

/** Universo de renta fija/variable vacío a propósito: así la única familia disponible es FCI, y
 *  la pantalla cae en ella sin necesidad de clickear una pestaña. */
function mockearApiSoloFci(
  fondos: FondoFci[] = [FONDO_FCI],
  segmentos = [{ tipo_renta: 'renta_variable', cantidad: fondos.length, monedas: ['ARS'] }],
) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = new URL(String(input), 'http://localhost')

    if (url.pathname === '/api/v1/universo/segmentos') {
      return respuestaJson({ segmentos: [], renta_variable: 0, sin_segmento: 0 })
    }
    if (url.pathname === '/api/v1/fci/segmentos') {
      return respuestaJson({
        segmentos,
        planilla: {
          fecha_planilla: '2026-08-21',
          fecha_cierre_anterior: '2026-08-20',
          fecha_base_mes: '2026-07-31',
          fecha_base_anio: '2025-12-30',
          fecha_base_12m: '2025-07-31',
          total_filas: fondos.length,
          capturado_en: '2026-08-21T12:00:00Z',
          advertencia_distribucion: FONDO_FCI.advertencia_distribucion,
        },
      })
    }
    if (url.pathname === '/api/v1/fci/fondos') {
      const tipoRenta = url.searchParams.get('tipo_renta')
      const items = tipoRenta === null ? fondos : fondos.filter((f) => f.tipo_renta === tipoRenta)
      return respuestaJson({ items, next_cursor: null })
    }

    throw new Error(`ruta no mockeada en el test: ${url.pathname}${url.search}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Tres fondos con perfiles cruzados: dos gerentes, dos secciones, dos monedas, y una calificación
 *  que la fuente escribe "NA" — que no es lo mismo que no tenerla. */
const GAINVEST_ARS: FondoFci = { ...FONDO_FCI, codigo_cafci: '1', fondo: 'Gainvest Renta Variable - Clase A' }
const DELTA_ARS: FondoFci = {
  ...FONDO_FCI,
  codigo_cafci: '2',
  fondo: 'Delta Acciones - Clase I',
  gerente: 'Delta Asset Management S.A.',
  horizonte: 'Cor',
  calificacion: 'NA',
  var_diaria_pct: 1.4,
}
const DELTA_USD: FondoFci = {
  ...FONDO_FCI,
  codigo_cafci: '3',
  fondo: 'Delta Dólar - Clase A',
  seccion: 'Renta Variable Dólar',
  gerente: 'Delta Asset Management S.A.',
  moneda: 'USD',
  horizonte: 'Flex',
  calificacion: null,
  var_diaria_pct: 0.2,
}

describe('FCI como tercera familia', () => {
  it('sin renta fija ni renta variable, la pantalla cae directo en FCI y muestra el fondo', async () => {
    mockearApiSoloFci()
    renderizarConRutaFci()

    expect(await screen.findByText('Gainvest Renta Variable - Clase A')).toBeInTheDocument()
    expect(screen.getByText('1 de 1 fondos')).toBeInTheDocument()
  })

  it('clickear un fondo navega a su ficha por código CAFCI', async () => {
    mockearApiSoloFci()
    renderizarConRutaFci()
    await screen.findByText('Gainvest Renta Variable - Clase A')

    await userEvent.click(screen.getByText('Gainvest Renta Variable - Clase A'))

    expect(await screen.findByText('ficha del fondo 1031')).toBeInTheDocument()
  })
})

describe('filtros de la barra de FCI', () => {
  function opcionesDe(etiqueta: string) {
    return Array.from(screen.getByLabelText(etiqueta).children).map((o) => o.textContent)
  }

  async function renderizarConLosTres() {
    mockearApiSoloFci([GAINVEST_ARS, DELTA_ARS, DELTA_USD])
    renderizarConRutaFci()
    // La moneda preferida es ARS: el "de M" son los dos fondos en pesos.
    await screen.findByText('2 de 2 fondos')
  }

  it('los selects ofrecen los códigos de la fuente sin traducir, y "NA" como una calificación más', async () => {
    await renderizarConLosTres()

    expect(opcionesDe('Horizonte')).toEqual(['todos', 'Cor', 'Flex', 'Lar'])
    expect(opcionesDe('Sección')).toEqual([
      'todos', 'Renta Variable Dólar', 'Renta Variable Peso Argentina',
    ])
    expect(opcionesDe('Gerente')).toEqual(['todos', 'Delta Asset Management S.A.', 'Gainvest S.A.'])
    const calificaciones = screen.getByRole('group', { name: 'Calificación' })
    expect(within(calificaciones).getByRole('checkbox', { name: 'NA' })).toBeInTheDocument()
    expect(within(calificaciones).getByRole('checkbox', { name: 'sin calificación' })).toBeInTheDocument()
  })

  it('elegir una gerente acota las demás dimensiones y actualiza el "N de M"', async () => {
    await renderizarConLosTres()

    await userEvent.selectOptions(screen.getByLabelText('Gerente'), 'Gainvest S.A.')

    expect(opcionesDe('Sección')).toEqual(['todos', 'Renta Variable Peso Argentina'])
    expect(opcionesDe('Horizonte')).toEqual(['todos', 'Lar'])
    // El select propio no se acota a sí mismo: se puede cambiar de idea.
    expect(opcionesDe('Gerente')).toEqual(['todos', 'Delta Asset Management S.A.', 'Gainvest S.A.'])
    // El "M" sigue siendo el tipo de renta en pesos; lo que cambia es el "N".
    expect(await screen.findByText('1 de 2 fondos')).toBeInTheDocument()
    expect(screen.queryByText('Delta Acciones - Clase I')).not.toBeInTheDocument()
  })

  it('un mínimo de variación se lee en puntos porcentuales: 1 deja fuera al que subió 0,67 %', async () => {
    await renderizarConLosTres()

    await userEvent.type(screen.getByLabelText('Var. día mín. (%)'), '1')

    expect(await screen.findByText('1 de 2 fondos')).toBeInTheDocument()
    expect(screen.getByText('Delta Acciones - Clase I')).toBeInTheDocument()
    expect(screen.queryByText('Gainvest Renta Variable - Clase A')).not.toBeInTheDocument()
  })

  it('una selección que se queda sin respaldo se apaga y se declara, no se aplica en silencio', async () => {
    await renderizarConLosTres()

    await userEvent.selectOptions(screen.getByLabelText('Gerente'), 'Gainvest S.A.')
    await userEvent.type(screen.getByLabelText('Var. día mín. (%)'), '1')

    expect(
      await screen.findByText(/no se aplica: Gerente «Gainvest S\.A\.»/),
    ).toBeInTheDocument()
    // Apagada quiere decir apagada: el fondo de la otra gerente se ve igual.
    expect(screen.getByText('Delta Acciones - Clase I')).toBeInTheDocument()
  })

  it('sin ningún fondo bajo los filtros lo dice, y la barra sigue montada para poder deshacerlos', async () => {
    await renderizarConLosTres()

    await userEvent.type(screen.getByLabelText('Var. día mín. (%)'), '99')

    expect(await screen.findByText('Ningún fondo pasa los filtros activos.')).toBeInTheDocument()
    expect(screen.getByLabelText('Gerente')).toBeInTheDocument()
  })

  it('"limpiar filtros" devuelve el tipo de renta entero', async () => {
    await renderizarConLosTres()
    await userEvent.selectOptions(screen.getByLabelText('Gerente'), 'Gainvest S.A.')
    await screen.findByText('1 de 2 fondos')

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('2 de 2 fondos')).toBeInTheDocument()
  })

  it('cambiar de tipo de renta limpia los filtros: el perfil de un segmento no aplica al otro', async () => {
    const mercadoDinero: FondoFci = {
      ...FONDO_FCI,
      codigo_cafci: '9',
      fondo: 'Delta Pesos - Clase A',
      tipo_renta: 'mercado_dinero',
      seccion: 'Mercado de Dinero Peso Argentina',
      gerente: 'Delta Asset Management S.A.',
    }
    mockearApiSoloFci([GAINVEST_ARS, DELTA_ARS, mercadoDinero], [
      { tipo_renta: 'renta_variable', cantidad: 2, monedas: ['ARS'] },
      { tipo_renta: 'mercado_dinero', cantidad: 1, monedas: ['ARS'] },
    ])
    renderizarConRutaFci()
    await screen.findByText('2 de 2 fondos')

    await userEvent.selectOptions(screen.getByLabelText('Gerente'), 'Gainvest S.A.')
    await screen.findByText('1 de 2 fondos')

    await userEvent.click(screen.getByRole('button', { name: /FCI mercado de dinero/i }))

    expect(await screen.findByText('1 de 1 fondos')).toBeInTheDocument()
    expect(screen.getByLabelText('Gerente')).toHaveValue('')
  })
})
