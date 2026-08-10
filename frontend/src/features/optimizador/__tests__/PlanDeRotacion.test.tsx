/**
 * `PlanDeRotacion` — F-036, GWT-2 y GWT-3: el panel aparece con la primera aceptación y muestra la
 * cartera propuesta (calendario + seis ejes); deshacer es LIFO puro, sólo la última tiene botón, y
 * deshacer la única hace desaparecer el panel entero.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import type { Concentracion } from '@/lib/cartera/esquemaConcentracion'
import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import { PlanDeRotacion } from '../components/PlanDeRotacion'
import { PlanRotacionProvider, usePlanRotacionAcciones } from '../store/planRotacionStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function especie(ticker: string, emision: string): Especie {
  return {
    ticker,
    emision,
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
  }
}

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_perfil',
    segmento: 'usd_hard',
    origen: { ticker: origenTicker, emisor: 'República Argentina', rendimiento: 0.11, duracion: 3.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 100_000 },
    destino: { ticker: destinoTicker, emisor: 'República Argentina', rendimiento: 0.112, duracion: 2.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 300_000 },
    delta: { rendimiento_pp: 0.2, duracion: -1 },
    flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: false, mejora_volumen: true, posible_distress: false },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: null,
  }
}

function concentracion(): Concentracion {
  return {
    perfil: 'moderado',
    limites: { tope_rend_usd: 0.15, percentil_liquidez: 25, max_emisor: 15, max_soberano: 65, max_sector: 40, min_sectores: 3 },
    topes: [],
    excedidos: 0,
    distribucion: { sector: [], ley: [], naturaleza: [] },
    sectores: { presentes: [], cantidad: 0, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    alertas: [],
  }
}

function calendarioUniverso() {
  return {
    resumen: {
      hoy: '2026-08-10',
      desde: '2026-08-10',
      hasta: '2027-07-10',
      con_montos: true,
      monedas: ['usd'],
      instrumentos: 1,
      meses_sin_renta: [],
      renta_anual: { usd: 0.05 },
      amortizacion_anual: { usd: 0 },
      pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses: [
      { anio: 2026, mes: 9, etiqueta: '2026-09', nombre: 'Septiembre 2026', con_renta: 1, con_amortizacion: 0, sin_renta: false, renta: { usd: 50 }, amortizacion: { usd: 0 }, instrumentos: [] },
    ],
    alertas: [],
  }
}

function responderCon() {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: [especie('AL30D', 'AL30'), especie('GD30D', 'GD30'), especie('AE38D', 'AE38')], next_cursor: null }
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion()
    } else if (url.includes('/calendario/cartera')) {
      cuerpo = calendarioUniverso()
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function BotonAceptarDeTest({ candidata: c, texto }: { candidata: Candidata; texto: string }) {
  const acciones = usePlanRotacionAcciones()
  return (
    <button type="button" onClick={() => acciones.aceptar(c)}>
      {texto}
    </button>
  )
}

function renderizar() {
  responderCon()
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <PlanRotacionProvider posiciones={[{ ticker: 'AL30D', peso: 100 }]}>
        <BotonAceptarDeTest candidata={candidata('AL30D', 'GD30D')} texto="aceptar-1" />
        <BotonAceptarDeTest candidata={candidata('GD30D', 'AE38D')} texto="aceptar-2" />
        <PlanDeRotacion montos={[{ ticker: 'AL30D', monto: 1000 }]} perfil="moderado" />
      </PlanRotacionProvider>
    </QueryClientProvider>,
  )
}

describe('PlanDeRotacion', () => {
  it('sin rotaciones aceptadas, no muestra nada', () => {
    renderizar()
    expect(screen.queryByLabelText('Cartera propuesta')).not.toBeInTheDocument()
  })

  it('al aceptar, aparece el panel con la rotación y el calendario/ejes de la propuesta (GWT-2)', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))

    const panel = await screen.findByLabelText('Cartera propuesta')
    expect(panel).toHaveTextContent('1 rotación aceptada')
    expect(await screen.findByText(/AL30D.*GD30D/)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Deshacer' })).toBeInTheDocument()
  })

  it('deshacer la única aceptada hace desaparecer el panel (GWT-3)', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))
    await screen.findByLabelText('Cartera propuesta')

    await usuario.click(screen.getByRole('button', { name: 'Deshacer' }))
    expect(screen.queryByLabelText('Cartera propuesta')).not.toBeInTheDocument()
  })

  it('con dos aceptadas, sólo la última tiene botón Deshacer', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))
    await screen.findByLabelText('Cartera propuesta')
    await usuario.click(screen.getByRole('button', { name: 'aceptar-2' }))

    const panel = await screen.findByLabelText('Cartera propuesta')
    expect(panel).toHaveTextContent('2 rotaciones aceptadas')
    expect(screen.getAllByRole('button', { name: 'Deshacer' })).toHaveLength(1)
    expect(screen.getByText(/de la última a la primera/)).toBeInTheDocument()
  })
})
