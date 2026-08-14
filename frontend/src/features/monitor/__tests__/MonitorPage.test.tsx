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
    fuente: null,
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
