/**
 * Los cuatro GWT de F-029 vistos desde la pantalla, más los estados de carga y error.
 *
 * Lo que se verifica de fondo es que **nada de lo que no resolvió se esconda**: la posición no
 * reconocida ocupa su fila, con su monto, y en ningún lado aparece un ticker parecido propuesto
 * como reemplazo.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import { ResolucionCartera } from '../components/ResolucionCartera'
import type { Resolucion } from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

function cruda(
  tickerDeclarado: string,
  { nominal = null, monto = 1000 }: { nominal?: number | null; monto?: number | null } = {},
): PosicionCruda {
  return {
    id: `id-${tickerDeclarado}`,
    fila: 1,
    tickerDeclarado,
    nominal,
    monto,
    valida: true,
    motivo: null,
  }
}

function resuelta(ticker: string, extra: Record<string, unknown> = {}) {
  return {
    id: `id-${ticker}`,
    fila: 1,
    ticker_declarado: ticker,
    nominal: null,
    monto: 1000,
    resuelta: true,
    ticker,
    emision: ticker.slice(0, 4),
    sufijo_liquidacion: 'D',
    moneda_cotizacion: 'USD',
    plazo_liquidacion: '2',
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    dato_sano: true,
    motivo: null,
    motivo_descripcion: null,
    ...extra,
  }
}

function noResuelta(ticker: string, extra: Record<string, unknown> = {}) {
  return {
    ...resuelta(ticker),
    resuelta: false,
    ticker: null,
    emision: null,
    sufijo_liquidacion: null,
    moneda_cotizacion: null,
    plazo_liquidacion: null,
    segmento: null,
    naturaleza: null,
    dato_sano: null,
    motivo: 'no_esta_en_el_universo',
    motivo_descripcion: 'No está en el universo',
    ...extra,
  }
}

function cobertura(extra: Partial<Resolucion['cobertura']> = {}): Resolucion['cobertura'] {
  return {
    posiciones: 1,
    resueltas: 1,
    no_resueltas: 0,
    posiciones_con_monto: 1,
    posiciones_sin_monto: 0,
    posiciones_sin_monto_no_resueltas: 0,
    monto_declarado: 1000,
    monto_no_resuelto: 0,
    porcentaje_no_resuelto: 0,
    ...extra,
  }
}

function responderCon(cuerpo: unknown, status = 200) {
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar(posiciones: PosicionCruda[]) {
  const cliente = crearQueryClient()
  // Sin reintentos: la política real reintenta dos veces con backoff ante un 5xx, así que el test
  // del estado de error mediría el backoff en vez de la pantalla. Que el 5xx se reintente en
  // producción ya está probado en `crearQueryClient`.
  cliente.setDefaultOptions({ queries: { retry: false } })

  return render(
    <QueryClientProvider client={cliente}>
      <ResolucionCartera posiciones={posiciones} />
    </QueryClientProvider>,
  )
}

// --- GWT-1: la posición conocida queda vinculada a su emisión, especie y plazo -------------------

describe('una posición que resuelve', () => {
  it('muestra la especie, la emisión y el plazo de liquidación', async () => {
    responderCon({
      posiciones: [resuelta('AL30D')],
      cobertura: cobertura(),
      alertas: [],
    })

    renderizar([cruda('AL30D')])

    expect(await screen.findByText(/1 de 1/)).toBeInTheDocument()
    expect(screen.getByText(/emisión AL30/)).toBeInTheDocument()
    expect(screen.getByText(/plazo 2/)).toBeInTheDocument()
  })

  it('muestra el plazo sin traducir el código de la fuente', async () => {
    responderCon({ posiciones: [resuelta('AL30D')], cobertura: cobertura(), alertas: [] })

    renderizar([cruda('AL30D')])

    await screen.findByText(/plazo 2/)
    expect(screen.queryByText(/48hs/)).not.toBeInTheDocument()
    expect(screen.queryByText(/contado inmediato/i)).not.toBeInTheDocument()
  })

  it('muestra s/d cuando el plazo no está, sin completarlo con el estándar', async () => {
    responderCon({
      posiciones: [resuelta('AL30D', { plazo_liquidacion: null })],
      cobertura: cobertura(),
      alertas: [],
    })

    renderizar([cruda('AL30D')])

    expect(await screen.findByText(/plazo s\/d/)).toBeInTheDocument()
  })
})

// --- GWT-2 y GWT-4: lo no reconocido se marca, se queda, y no se reemplaza -----------------------

describe('una posición que no resuelve', () => {
  it('queda en la cartera con su monto, marcada y con el motivo', async () => {
    responderCon({
      posiciones: [noResuelta('NOEXISTE', { monto: 5000 })],
      cobertura: cobertura({
        resueltas: 0,
        no_resueltas: 1,
        monto_declarado: 5000,
        monto_no_resuelto: 5000,
        porcentaje_no_resuelto: 100,
      }),
      alertas: [],
    })

    renderizar([cruda('NOEXISTE', { monto: 5000 })])

    // Se espera a la resolución y no al ticker: el ticker ya está en pantalla mientras carga.
    expect(await screen.findByText(/no reconocida/)).toBeInTheDocument()
    expect(screen.getByText('NOEXISTE')).toBeInTheDocument()
    expect(screen.getByText(/No está en el universo/)).toBeInTheDocument()
    expect(screen.getByText(/monto 5\.000,00/)).toBeInTheDocument()
  })

  it('no propone el ticker más parecido en ningún lado de la pantalla', async () => {
    responderCon({
      posiciones: [
        resuelta('RUCEO'),
        noResuelta('RUCEX', { motivo: 'sin_tipo_de_tasa', motivo_descripcion: 'Sin tipo de tasa' }),
      ],
      cobertura: cobertura({ posiciones: 2, no_resueltas: 1 }),
      alertas: [],
    })

    const { container } = renderizar([cruda('RUCEO'), cruda('RUCEX')])

    await screen.findByText(/no reconocida/)
    const filaDeRucex = screen.getByText('RUCEX').closest('li')
    expect(filaDeRucex).not.toBeNull()
    // RUCEO existe en la pantalla porque es otra posición de la cartera, pero no adentro de la
    // fila de RUCEX: nadie lo propone como su reemplazo.
    expect(filaDeRucex?.textContent).not.toContain('RUCEO')
    expect(container.textContent).not.toMatch(/quisiste decir|sugerencia|más parecido/i)
  })

  it('distingue una acción de un ticker inexistente', async () => {
    responderCon({
      posiciones: [
        noResuelta('GGAL', {
          motivo: 'renta_variable',
          motivo_descripcion: 'Renta variable: no es un instrumento de renta fija',
        }),
      ],
      cobertura: cobertura({ resueltas: 0, no_resueltas: 1 }),
      alertas: [],
    })

    renderizar([cruda('GGAL')])

    expect(await screen.findByText(/Renta variable/)).toBeInTheDocument()
    expect(screen.queryByText(/No está en el universo/)).not.toBeInTheDocument()
  })
})

// --- GWT-3: el diagnóstico declara cantidad, porcentaje y base ----------------------------------

describe('el diagnóstico de cobertura', () => {
  it('declara la cantidad y el porcentaje del monto sin resolver', async () => {
    responderCon({
      posiciones: [resuelta('AL30D'), noResuelta('NOEXISTE')],
      cobertura: cobertura({
        posiciones: 11,
        resueltas: 9,
        no_resueltas: 2,
        posiciones_con_monto: 11,
        monto_declarado: 11000,
        monto_no_resuelto: 2000,
        porcentaje_no_resuelto: 18.18,
      }),
      alertas: [],
    })

    renderizar([cruda('AL30D'), cruda('NOEXISTE')])

    expect(await screen.findByText(/9 de 11/)).toBeInTheDocument()
    expect(screen.getByText(/2 sin resolver, 18,2% del monto/)).toBeInTheDocument()
  })

  it('declara sobre qué base se calculó cuando hay posiciones sin monto', async () => {
    responderCon({
      posiciones: [resuelta('AL30D'), noResuelta('NOEXISTE', { monto: null, nominal: 50000 })],
      cobertura: cobertura({
        posiciones: 2,
        resueltas: 1,
        no_resueltas: 1,
        posiciones_con_monto: 1,
        posiciones_sin_monto: 1,
        posiciones_sin_monto_no_resueltas: 1,
        monto_declarado: 1000,
        monto_no_resuelto: 0,
        porcentaje_no_resuelto: 0,
      }),
      alertas: [],
    })

    renderizar([cruda('AL30D'), cruda('NOEXISTE', { monto: null, nominal: 50000 })])

    expect(await screen.findByText(/se calculó sobre 1 de 2 posiciones/)).toBeInTheDocument()
    expect(screen.getByText(/no se las cuenta como cero/)).toBeInTheDocument()
  })

  it('muestra s/d y no 0,0% cuando no hay base para el porcentaje', async () => {
    responderCon({
      posiciones: [noResuelta('NOEXISTE', { monto: null, nominal: 10 })],
      cobertura: cobertura({
        resueltas: 0,
        no_resueltas: 1,
        posiciones_con_monto: 0,
        posiciones_sin_monto: 1,
        posiciones_sin_monto_no_resueltas: 1,
        monto_declarado: 0,
        monto_no_resuelto: 0,
        porcentaje_no_resuelto: null,
      }),
      alertas: [],
    })

    renderizar([cruda('NOEXISTE', { monto: null, nominal: 10 })])

    expect(await screen.findByText(/1 sin resolver, s\/d del monto/)).toBeInTheDocument()
    expect(screen.queryByText(/0,0% del monto/)).not.toBeInTheDocument()
  })

  it('muestra las alertas del backend con su acción requerida', async () => {
    responderCon({
      posiciones: [noResuelta('NOEXISTE')],
      cobertura: cobertura({ resueltas: 0, no_resueltas: 1 }),
      alertas: [
        {
          codigo: 'posiciones_no_resueltas',
          mensaje: '1 de 1 posiciones no se reconocieron en el universo (NOEXISTE).',
          severidad: 'advertencia',
          accion_requerida: 'Verificar el ticker con el resumen de cuenta.',
          detalle: {},
        },
      ],
    })

    renderizar([cruda('NOEXISTE')])

    expect(await screen.findByText(/no se reconocieron en el universo/)).toBeInTheDocument()
    expect(screen.getByText(/Verificar el ticker con el resumen de cuenta/)).toBeInTheDocument()
  })
})

// --- Los estados de la consulta -----------------------------------------------------------------

describe('estados de la consulta', () => {
  it('mientras resuelve muestra la cartera declarada y el estado de carga', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))

    renderizar([cruda('AL30D', { monto: 1234.5 })])

    expect(await screen.findByRole('status')).toHaveTextContent(/Cargando/)
    // La cartera no desaparece de la pantalla mientras se resuelve.
    expect(screen.getByText('AL30D')).toBeInTheDocument()
    expect(screen.getByText(/monto 1\.234,50/)).toBeInTheDocument()
  })

  it('si la resolución falla, muestra el error y deja reintentar sin perder la cartera', async () => {
    const usuario = userEvent.setup()
    const fetchMock = responderCon(
      { error: { code: 'service_unavailable', message: 'La base no está disponible' } },
      503,
    )

    renderizar([cruda('AL30D')])

    expect(await screen.findByRole('alert')).toHaveTextContent(/no está disponible/)
    expect(screen.getByText('AL30D')).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Reintentar' }))
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(1))
  })
})
