/**
 * `SeccionRiesgo` vista desde la pantalla — F-031, mitad diagnóstico. La lib pura ya está probada
 * en `lib/cartera/__tests__/riesgo.test.ts` (incluido el GWT-5 de paridad entre orígenes); acá se
 * verifica lo que sólo se puede romper en esta pantalla: que reciba `posiciones`/`perfil` ya
 * resueltos por el padre sin cambiar su firma, que pida universo y concentración por su cuenta, y
 * que respete el mismo criterio de "sin posiciones no hay nada que mostrar" que el resto de
 * `DiagnosticoCartera`.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import type { Concentracion } from '@/lib/cartera/esquemaConcentracion'

import { SeccionRiesgo } from '../components/SeccionRiesgo'

afterEach(() => {
  vi.unstubAllGlobals()
})

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30D',
    emision: 'AL30',
    sufijo_liquidacion: 'D',
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.11,
    duracion: 3.5,
    vencimiento: '2030-07-09',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 100,
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
  concentracion = veredicto(),
}: { especies?: Especie[]; concentracion?: unknown } = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion
    } else {
      throw new Error(`fetch no mockeado en este test: ${url} ${init?.method ?? ''}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar(props: { posiciones: { ticker: string; peso: number }[]; perfil: 'conservador' | 'moderado' | 'agresivo' }) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <SeccionRiesgo {...props} />
    </QueryClientProvider>,
  )
}

describe('sin posiciones', () => {
  it('no renderiza nada, mismo criterio que el resto de DiagnosticoCartera', () => {
    responderCon()
    const { container } = renderizar({ posiciones: [], perfil: 'moderado' })

    expect(container).toBeEmptyDOMElement()
  })
})

describe('con posiciones', () => {
  it('pide universo y concentración con la firma recibida, y muestra los seis ejes', async () => {
    const fetchMock = responderCon()
    renderizar({ posiciones: [{ ticker: 'AL30D', peso: 100 }], perfil: 'moderado' })

    expect(await screen.findByText('Duración')).toBeInTheDocument()
    expect(screen.getByText('Crédito')).toBeInTheDocument()
    expect(screen.getByText('Legislación')).toBeInTheDocument()
    expect(screen.getByText('Liquidez')).toBeInTheDocument()
    expect(screen.getByText('Concentración')).toBeInTheDocument()
    expect(screen.getByText('Moneda')).toBeInTheDocument()

    const pedidoConcentracion = fetchMock.mock.calls.find(([e]) => String(e).includes('/concentracion'))!
    expect(String(pedidoConcentracion[0])).toContain('perfil=moderado')
    const cuerpo = JSON.parse(String((pedidoConcentracion[1] as RequestInit).body))
    expect(cuerpo.posiciones).toEqual([{ ticker: 'AL30D', peso: 100 }])
  })

  it('la misma composición produce el mismo eje de concentración que el veredicto ya pedido', async () => {
    responderCon()
    renderizar({ posiciones: [{ ticker: 'AL30D', peso: 100 }], perfil: 'moderado' })

    await screen.findByText('Concentración')
    expect(screen.getByText('máximo por crédito')).toBeInTheDocument()
  })
})
