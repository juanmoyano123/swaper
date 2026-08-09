/**
 * `PanelRendimientos` vista desde la pantalla — F-022, mismo patrón que `PanelRenta.test.tsx`: mock
 * de `fetch` por URL, sin montar el backend. El motor puro se cubre aparte en `rendimientos.test.ts`;
 * acá lo que importa es que las cuatro tarjetas aparezcan siempre en el mismo orden, que la leyenda
 * de exclusión sea condicional, y que no exista ningún control que combine las cuatro naturalezas
 * (regla 2 del dominio).
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelRendimientos } from '../components/PanelRendimientos'
import type { Especie } from '../lib/schema'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

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
    rendimiento: 0.11,
    duracion: 3.2,
    vencimiento: '2030-07-09',
    ley: 'ARG',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 100,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: null,
    sector: null,
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

function responderCon({
  especies = [],
  tipoDeCambio = { valor: 1500, disponible: true },
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
}) {
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
      <button type="button" onClick={() => alternarPapel('AL30')}>
        agregar AL30
      </button>
      <button type="button" onClick={() => fijarPeso('AL30', 100)}>
        peso AL30 a 100
      </button>
      <button type="button" onClick={() => fijarMontoTotal(10_000)}>
        monto 10.000
      </button>
      <PanelRendimientos />
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

const LAS_CUATRO_UNIDADES = ['TIR USD', 'TIR DL', 'Tasa real CER', 'TNA $']

describe('sin posiciones', () => {
  it('dice qué falta en vez de mostrar tarjetas vacías sin explicación', () => {
    responderCon({})
    renderizar()

    expect(
      screen.getByText(/Sin posiciones de renta fija todavía: agregá papeles/),
    ).toBeInTheDocument()
  })
})

describe('con una cartera 100% hard-dollar', () => {
  it('GWT-1/GWT-2: muestra las cuatro tarjetas siempre, en el mismo orden, con s/d donde no hay dato', async () => {
    responderCon({ especies: [especie({ rendimiento: 0.11 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 100' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    // Las cuatro unidades presentes, en el orden fijo del dominio.
    const rotulos = await Promise.all(LAS_CUATRO_UNIDADES.map((u) => screen.findByText(u)))
    const orden = rotulos.map((nodo) => nodo.textContent)
    expect(orden).toEqual(LAS_CUATRO_UNIDADES)

    // La naturaleza presente muestra su número.
    expect(await screen.findByText('11,00%')).toBeInTheDocument()

    // Las tres restantes, en cero por ciento de la cartera y `s/d`, no ausentes.
    const sinDato = screen.getAllByText('s/d')
    expect(sinDato.length).toBeGreaterThanOrEqual(3)
    const ceros = screen.getAllByText('0,0% de la cartera')
    expect(ceros).toHaveLength(3)
  })

  it('no hay ningún control que combine las cuatro naturalezas en un promedio', async () => {
    responderCon({ especies: [especie({ rendimiento: 0.11 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 100' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    await screen.findByText('11,00%')

    expect(screen.queryByText(/promedio general/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    // El único toggle son los botones del arnés de test; el panel no agrega ninguno propio.
    expect(screen.queryByRole('button', { name: /ver promedio/i })).not.toBeInTheDocument()
  })
})

describe('con una posición sin rendimiento informado', () => {
  it('GWT-4: declara cuántas posiciones y qué porcentaje quedaron fuera del cálculo', async () => {
    responderCon({ especies: [especie({ rendimiento: null })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 100' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    expect(
      await screen.findByText(/1 posición\(es\) sin rendimiento informado, 100,0% de la cartera/),
    ).toBeInTheDocument()
  })

  it('sin posiciones excluidas, la leyenda de exclusión no aparece', async () => {
    responderCon({ especies: [especie({ rendimiento: 0.11 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 100' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    await screen.findByText('11,00%')
    expect(screen.queryByText(/quedaron fuera del cálculo/)).not.toBeInTheDocument()
  })
})
