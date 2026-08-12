/**
 * F-036 — `BotonesDecision` (GWT-2/GWT-4, despachan al plan) y `EfectoCalendarioNota` (GWT-1, el
 * efecto de calendario en una línea). El resto de `compartidos.tsx` (formatoValor, NotaCosto,
 * ResumenDescartes) ya se prueba indirectamente vía las dos secciones.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { crearQueryClient } from '@/app/queryClient'
import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import { BotonesDecision, EfectoCalendarioNota } from '../components/compartidos'
import { PlanRotacionProvider, usePlanRotacion } from '../store/planRotacionStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: {
      ticker: origenTicker,
      emisor: 'X',
      rendimiento: 0.1,
      duracion: 3,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 100_000,
    },
    destino: {
      ticker: destinoTicker,
      emisor: 'X',
      rendimiento: 0.12,
      duracion: 4,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 200_000,
    },
    delta: { rendimiento_pp: 2, duracion: 1 },
    flags: {
      mismo_emisor: false,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'nota',
    costo: null,
  }
}

function EstadoDelPlan() {
  const plan = usePlanRotacion()
  return <div data-testid="estado-plan">{plan.aceptadas.length} aceptadas, {plan.descartadas.length} descartadas</div>
}

function envolver(hijos: React.ReactNode) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <PlanRotacionProvider posiciones={[{ ticker: 'A', peso: 100 }]}>
        {hijos}
        <EstadoDelPlan />
      </PlanRotacionProvider>
    </QueryClientProvider>,
  )
}

describe('BotonesDecision', () => {
  it('Aceptar despacha la candidata al plan (GWT-2)', async () => {
    const usuario = userEvent.setup()
    envolver(<BotonesDecision candidata={candidata('A', 'B')} />)

    await usuario.click(screen.getByRole('button', { name: 'Aceptar' }))
    expect(screen.getByTestId('estado-plan')).toHaveTextContent('1 aceptadas, 0 descartadas')
  })

  it('Descartar despacha la clave al plan (GWT-4)', async () => {
    const usuario = userEvent.setup()
    envolver(<BotonesDecision candidata={candidata('A', 'B')} />)

    await usuario.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(screen.getByTestId('estado-plan')).toHaveTextContent('0 aceptadas, 1 descartadas')
  })

  it('deshabilitado bloquea Aceptar pero no impide clickear Descartar', async () => {
    const usuario = userEvent.setup()
    envolver(<BotonesDecision candidata={candidata('A', 'B')} deshabilitado motivoDeshabilitado="sin TC" />)

    expect(screen.getByRole('button', { name: 'Aceptar' })).toBeDisabled()
    await usuario.click(screen.getByRole('button', { name: 'Descartar' }))
    expect(screen.getByTestId('estado-plan')).toHaveTextContent('0 aceptadas, 1 descartadas')
  })
})

function mockFetchCalendario(rentaPara: (tickers: string[]) => Record<string, number>, alertas: unknown[] = []) {
  const fetchMock = vi.fn((_entrada: RequestInfo | URL, init?: RequestInit) => {
    const cuerpoPedido = JSON.parse((init?.body as string) ?? '{}')
    const tickers = (cuerpoPedido.posiciones as { ticker: string }[]).map((p) => p.ticker)
    const renta = rentaPara(tickers)
    const cuerpo = {
      resumen: {
        hoy: '2026-08-10',
        desde: '2026-08-10',
        hasta: '2027-07-10',
        con_montos: true,
        monedas: ['usd'],
        instrumentos: 1,
        meses_sin_renta: [],
        renta_anual: { usd: 0 },
        amortizacion_anual: { usd: 0 },
        pendientes_este_mes: 0,
        flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
      },
      meses: [
        { anio: 2026, mes: 9, etiqueta: '2026-09', nombre: 'Septiembre 2026', con_renta: renta.usd > 0 ? 1 : 0, con_amortizacion: 0, sin_renta: renta.usd === 0, renta, amortizacion: { usd: 0 }, instrumentos: [] },
      ],
      alertas,
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('EfectoCalendarioNota', () => {
  it('declara el mes que se llena si se acepta (GWT-1)', async () => {
    mockFetchCalendario((tickers) => (tickers.includes('B') ? { usd: 100 } : { usd: 0 }))
    envolver(
      <EfectoCalendarioNota candidata={candidata('A', 'B')} montos={[{ ticker: 'A', monto: 1000 }]} monedaDe={() => 'usd'} tipoDeCambio={null} />,
    )

    await waitFor(() => expect(screen.getByText(/Si se acepta/)).toBeInTheDocument())
    expect(screen.getByText(/se llena Septiembre 2026 \(USD\)/)).toBeInTheDocument()
  })

  it('declara el motivo cuando no es calculable, con el ticker nombrado', async () => {
    mockFetchCalendario(
      () => ({ usd: 0 }),
      [{ codigo: 'posicion_sin_calendario', mensaje: 'x', severidad: 'advertencia', accion_requerida: null, detalle: { cantidad: 1, motivos: { B: 'sin_paridad' } } }],
    )
    envolver(
      <EfectoCalendarioNota candidata={candidata('A', 'B')} montos={[{ ticker: 'A', monto: 1000 }]} monedaDe={() => 'usd'} tipoDeCambio={null} />,
    )

    await waitFor(() => expect(screen.getByText(/no se puede afirmar/)).toBeInTheDocument())
    expect(screen.getByText(/B/)).toBeInTheDocument()
  })

  it('sin montos, no muestra nada', () => {
    envolver(<EfectoCalendarioNota candidata={candidata('A', 'B')} montos={[]} monedaDe={() => 'usd'} tipoDeCambio={null} />)
    expect(screen.queryByText(/Efecto sobre el calendario/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Si se acepta/)).not.toBeInTheDocument()
  })
})
