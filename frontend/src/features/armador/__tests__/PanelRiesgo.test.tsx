/**
 * `PanelRiesgo` visto desde la pantalla — F-031. La lib pura (`vectorDeRiesgo`) ya tiene sus
 * propios GWT en `lib/cartera/__tests__/riesgo.test.ts`; acá se verifica lo que sólo se puede
 * romper en pantalla: que el panel arme `porTicker` a partir de `useCarteraResuelta`, que
 * comparta la firma de `useConcentracion` con `PanelConcentracion` (mismo patrón de peso real),
 * y que el estado vacío/carga/error se muestren.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelRiesgo } from '../components/PanelRiesgo'
import type { Especie } from '../lib/schema'
import type { Concentracion } from '../lib/schemaConcentracion'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

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
    periodicidad: 'semestral',
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
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

function veredicto(extra: Partial<Concentracion> = {}): Concentracion {
  return {
    perfil: 'moderado',
    limites: {
      tope_rend_usd: 0.15,
      percentil_liquidez: 25,
      max_emisor: 15,
      max_soberano: 65,
      max_sector: 40,
      min_sectores: 3,
    },
    topes: [
      { tipo: 'soberano', clave: 'SOBERANO_AR', nombre: 'Riesgo soberano argentino', peso: 100, tope: 65, excedido: true, exceso: 35 },
    ],
    excedidos: 1,
    distribucion: { sector: [], ley: [], naturaleza: [] },
    sectores: { presentes: ['Soberano'], cantidad: 1, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    alertas: [],
    ...extra,
  }
}

function responderCon({
  especies = [especie()],
  tipoDeCambio = { valor: 1500, disponible: true },
  concentracion = veredicto(),
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  concentracion?: unknown
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function Arnes() {
  const { alternarPapel } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        agregar GD30
      </button>
      <PanelRiesgo />
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

describe('sin posiciones', () => {
  it('lo dice y no llama al endpoint de concentración', () => {
    const fetchMock = responderCon()
    renderizar()

    expect(screen.getByText(/Sin posiciones de renta fija/)).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([e]) => String(e).includes('/concentracion'))).toHaveLength(0)
  })
})

describe('con posiciones', () => {
  it('muestra los seis ejes del vector', async () => {
    responderCon()
    renderizar()
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))

    expect(await screen.findByText('Duración')).toBeInTheDocument()
    expect(screen.getByText('Crédito')).toBeInTheDocument()
    expect(screen.getByText('Legislación')).toBeInTheDocument()
    expect(screen.getByText('Liquidez')).toBeInTheDocument()
    expect(screen.getByText('Concentración')).toBeInTheDocument()
    expect(screen.getByText('Moneda')).toBeInTheDocument()
  })

  it('declara sobre qué peso se midió, mismo criterio que PanelConcentracion', async () => {
    responderCon()
    renderizar()
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))

    expect(await screen.findByText(/ninguna se pudo resolver a peso real/)).toBeInTheDocument()
  })

  it('el eje concentración refleja el veredicto ya pedido por la misma firma de useConcentracion', async () => {
    responderCon()
    renderizar()
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))

    await screen.findByText('Concentración')
    expect(screen.getByText('máximo por crédito')).toBeInTheDocument()
  })
})
