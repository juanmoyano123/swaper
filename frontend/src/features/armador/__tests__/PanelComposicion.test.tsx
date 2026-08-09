/**
 * `PanelComposicion` vista desde la pantalla — F-023, mismo patrón que `PanelConcentracion.test.tsx`
 * y `PanelRendimientos.test.tsx`: fetch mockeado por URL, sin montar el backend. El motor puro se
 * cubre aparte en `composicion.test.ts` y `CurvaTirDuracion.test.tsx`; acá lo que importa es que
 * los tres cortes aparezcan, que la pestaña de mayor peso arranque activa, que cambiar de pestaña
 * no mezcle segmentos y que el panel declare sobre qué peso midió, igual que `PanelConcentracion`.
 *
 * `ResponsiveContainer` de recharts mide con `ResizeObserver`, que jsdom no implementa: se
 * polyfillea acá mismo (igual que en `CurvaTirDuracion.test.tsx`), sin tocar `src/test/setup.ts`.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelComposicion } from '../components/PanelComposicion'
import type { Especie } from '../lib/schema'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

beforeEach(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverMock)
  // Ídem `CurvaTirDuracion.test.tsx`: `ResponsiveContainer` mide con `getBoundingClientRect()`
  // antes de que el observer dispare, y jsdom la devuelve en cero.
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    width: 600,
    height: 260,
    top: 0,
    left: 0,
    bottom: 260,
    right: 600,
    x: 0,
    y: 0,
    toJSON: () => {},
  })
})

/** recharts mide el ancho de cada texto con un `<span>` oculto y global
 *  (`#recharts_measurement_span`) que conserva el último texto medido entre renders: sin
 *  ignorarlo, un ticker puede aparecer "duplicado" en la búsqueda. */
const SIN_MEDICION = { ignore: '#recharts_measurement_span' }

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'GD30',
    emision: 'GD30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.11,
    duracion: 3.2,
    vencimiento: '2030-07-09',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 70,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: 1,
    sector: 'Soberano',
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

const YMCHO = especie({
  ticker: 'YMCHO',
  emision: 'YMCH',
  clase_activo: 'on_corporativo',
  emisor: 'YPF S.A.',
  sector: 'O&G',
  precio: 99,
})

function responderCon({
  especies = [especie(), YMCHO],
  tipoDeCambio = { valor: 1500, disponible: true },
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
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

function Arnes() {
  const { alternarPapel, fijarPeso, fijarMontoTotal } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        agregar GD30
      </button>
      <button type="button" onClick={() => alternarPapel('YMCHO')}>
        agregar YMCHO
      </button>
      <button type="button" onClick={() => fijarPeso('GD30', 70)}>
        peso GD30 a 70
      </button>
      <button type="button" onClick={() => fijarPeso('YMCHO', 30)}>
        peso YMCHO a 30
      </button>
      <button type="button" onClick={() => fijarMontoTotal(10_000)}>
        monto 10.000
      </button>
      <PanelComposicion />
    </div>
  )
}

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <ArmadorProvider>
        <Arnes />
      </ArmadorProvider>
    </QueryClientProvider>,
  )
}

async function conDosPosiciones() {
  await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))
  await userEvent.click(screen.getByRole('button', { name: 'agregar YMCHO' }))
  await userEvent.click(screen.getByRole('button', { name: 'peso GD30 a 70' }))
  await userEvent.click(screen.getByRole('button', { name: 'peso YMCHO a 30' }))
}

describe('sin posiciones', () => {
  it('lo dice, sin distribución ni curva', () => {
    responderCon()
    renderizar()

    expect(screen.getByText(/Sin posiciones de renta fija todavía/)).toBeInTheDocument()
    expect(screen.queryByText('Clase de activo')).not.toBeInTheDocument()
    expect(screen.queryByText('Curva TIR/duración')).not.toBeInTheDocument()
  })
})

describe('los tres cortes', () => {
  it('muestra clase, segmento y emisor, sin repetir el sector que ya cubre PanelConcentracion', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('Clase de activo')).toBeInTheDocument()
    expect(screen.getByText('Segmento')).toBeInTheDocument()
    expect(screen.getByText('Emisor')).toBeInTheDocument()
    expect(screen.queryByText('Sector')).not.toBeInTheDocument()
  })

  it('el emisor no informado aparece en su propio tramo, nunca repartido', async () => {
    responderCon({ especies: [especie(), especie({ ...YMCHO, emisor: null })] })
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('emisor no informado')).toBeInTheDocument()
  })
})

describe('la pestaña de la curva', () => {
  it('arranca en el segmento de mayor peso de la cartera, abierto por crédito', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    // GD30 (70%, soberano) pesa más que YMCHO (30%, ON): la pestaña "Soberanos" arranca activa y
    // GD30 aparece rotulado en la curva.
    const soberanos = await screen.findByRole('button', { name: 'Soberanos' })
    expect(soberanos).toHaveAttribute('aria-current', 'true')
    expect(await screen.findByText('GD30', SIN_MEDICION)).toBeInTheDocument()
  })

  it('cambiar de pestaña muestra el otro crédito sin mezclar los dos en la misma nube', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()
    await screen.findByText('GD30', SIN_MEDICION)

    await userEvent.click(screen.getByRole('button', { name: 'ONs' }))

    expect(await screen.findByText('YMCHO', SIN_MEDICION)).toBeInTheDocument()
    expect(screen.queryByText('GD30', SIN_MEDICION)).not.toBeInTheDocument()
  })
})

describe('sobre qué peso se midió', () => {
  it('sin monto total cargado, pondera por la ponderación pedida y lo declara', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(
      await screen.findByText(/ninguna se pudo resolver a peso real/),
    ).toBeInTheDocument()
  })

  it('con monto total, pondera por el peso real y lo declara', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    expect(
      await screen.findByText(/Medido sobre el peso real de las 2 posiciones/),
    ).toBeInTheDocument()
  })
})

describe('sin familia por color', () => {
  it('no agrega ningún control de Bonares/Globales/Bopreal: está fuera de alcance', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()
    await screen.findByText('Clase de activo')

    expect(screen.queryByText(/Bonares/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Globales/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/Bopreal/i)).not.toBeInTheDocument()
  })
})
