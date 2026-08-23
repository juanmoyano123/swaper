/**
 * `ComparacionCarteras` — F-037: la cartera original contra la propuesta, lado a lado, con la
 * misma vara (GWT-1), los meses que cambian de cobertura marcados (GWT-2) y el costo total
 * acumulado junto a los deltas de renta y rendimiento (GWT-3).
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { Concentracion, NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { CalendarioUniverso, MesDelCalendario } from '@/lib/cartera/esquemaCalendario'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import type { Candidata, CostoRotacion } from '@/lib/rotaciones/esquemaRotaciones'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'

import { ComparacionCarteras } from '../components/ComparacionCarteras'
import { useCarteraPropuesta } from '../hooks/useCarteraPropuesta'
import { PlanRotacionProvider, usePlanRotacionAcciones } from '../store/planRotacionStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

const ETIQUETAS = Array.from({ length: 12 }, (_, i) => `m${i + 1}`)

function especie(extra: Partial<Especie>): Especie {
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
    periodicidad: 'semestral',
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

function candidata(costo: CostoRotacion | null, rendimientoDestino: number | null): Candidata {
  return {
    tipo: 'mejora_perfil',
    segmento: 'usd_hard',
    origen: { ticker: 'AL30D', emisor: 'República Argentina', rendimiento: 0.11, duracion: 3.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 100_000 },
    destino: { ticker: 'GD30D', emisor: 'República Argentina', rendimiento: rendimientoDestino ?? 0.13, duracion: 2.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 300_000 },
    delta: { rendimiento_pp: 2, duracion: -1 },
    flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: false, mejora_volumen: true, posible_distress: false },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo,
  }
}

const COSTO_VERIFICABLE: CostoRotacion = {
  arancel_pct_por_pata: 0.75,
  spread_origen_pct: 0.6,
  spread_destino_pct: 0.65,
  total_pct: 2,
  verificable: true,
  elevado: false,
  payback_meses: 12,
}

function mesVacio(etiqueta: string): MesDelCalendario {
  return { anio: 2026, mes: 1, etiqueta, nombre: etiqueta, con_renta: 0, con_amortizacion: 0, sin_renta: true, renta: { usd: 0 }, amortizacion: { usd: 0 }, instrumentos: [] }
}

function calendarioOriginal(): CalendarioUniverso {
  const meses = ETIQUETAS.map((e) => mesVacio(e))
  meses[0] = {
    ...mesVacio('m1'),
    con_renta: 1,
    sin_renta: false,
    renta: { usd: 100 },
    instrumentos: [
      { ticker: 'AL30D', emision: 'AL30', fechas: ['2026-09-09'], pct_renta: 0.1, pct_amortizacion: 0, renta: 100, amortizacion: 0, moneda: 'usd', rendimiento: 0.11, naturaleza: 'tir_usd', naturaleza_nombre: 'TIR en dólares (hard dollar)', vencimiento: null },
    ],
  }
  return {
    resumen: {
      hoy: '2026-08-10', desde: '2026-08-10', hasta: '2027-07-10', con_montos: true, monedas: ['usd'],
      instrumentos: 1, meses_sin_renta: [], renta_anual: { usd: 100 }, amortizacion_anual: { usd: 0 }, pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses,
    alertas: [],
  }
}

function calendarioPropuesto(): CalendarioUniverso {
  const meses = ETIQUETAS.map((e) => mesVacio(e))
  meses[1] = {
    ...mesVacio('m2'),
    con_renta: 1,
    sin_renta: false,
    renta: { usd: 150 },
    instrumentos: [
      { ticker: 'GD30D', emision: 'GD30', fechas: ['2026-10-09'], pct_renta: 0.15, pct_amortizacion: 0, renta: 150, amortizacion: 0, moneda: 'usd', rendimiento: 0.13, naturaleza: 'tir_usd', naturaleza_nombre: 'TIR en dólares (hard dollar)', vencimiento: null },
    ],
  }
  return {
    resumen: {
      hoy: '2026-08-10', desde: '2026-08-10', hasta: '2027-07-10', con_montos: true, monedas: ['usd'],
      instrumentos: 1, meses_sin_renta: [], renta_anual: { usd: 150 }, amortizacion_anual: { usd: 0 }, pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses,
    alertas: [],
  }
}

function concentracion(): Concentracion {
  return {
    perfil: 'moderado',
    limites: { tope_rend_usd: 0.15, percentil_liquidez: 25, max_emisor: 15, max_soberano: 65, max_sector: 40, min_sectores: 3 },
    topes: [],
    excedidos: 0,
    distribucion: { sector: [], ley: [], naturaleza: [] },
    sectores: { presentes: ['Soberano'], cantidad: 1, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    fci: [],
    alertas: [],
  }
}

function responderCon(especies: Especie[]) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: { valor: null, disponible: false } }
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion()
    } else if (url.includes('/calendario/cartera')) {
      const cuerpoPedido = JSON.parse((init?.body as string) ?? '{}')
      const tickers = (cuerpoPedido.posiciones as { ticker: string }[]).map((p) => p.ticker)
      cuerpo = tickers.includes('GD30D') ? calendarioPropuesto() : calendarioOriginal()
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function BotonAceptarDeTest({ candidata: c }: { candidata: Candidata }) {
  const acciones = usePlanRotacionAcciones()
  return (
    <button type="button" onClick={() => acciones.aceptar(c)}>
      aceptar
    </button>
  )
}

function BloqueDeTest({ montosOriginales, perfil }: { montosOriginales: PosicionConMonto[]; perfil: NombreDePerfil }) {
  const propuesta = useCarteraPropuesta(montosOriginales)
  return (
    <ComparacionCarteras
      montosOriginales={montosOriginales}
      montos={propuesta.montos}
      monedaDe={propuesta.monedaDe}
      tipoDeCambio={propuesta.tipoDeCambio}
      perfil={perfil}
    />
  )
}

function renderizar(c: Candidata, especies: Especie[]) {
  responderCon(especies)
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  const montosOriginales: PosicionConMonto[] = [{ ticker: 'AL30D', monto: 1000 }]
  return render(
    <QueryClientProvider client={cliente}>
      <PlanRotacionProvider posiciones={[{ ticker: 'AL30D', peso: 100 }]}>
        <BotonAceptarDeTest candidata={c} />
        <BloqueDeTest montosOriginales={montosOriginales} perfil="moderado" />
      </PlanRotacionProvider>
    </QueryClientProvider>,
  )
}

const ESPECIES = [especie({ ticker: 'AL30D' }), especie({ ticker: 'GD30D', emision: 'GD30', duracion: 2.5, volumen_usd: 300_000, rendimiento: 0.13 })]

describe('ComparacionCarteras', () => {
  it('sin rotaciones aceptadas, no muestra nada', () => {
    renderizar(candidata(COSTO_VERIFICABLE, 0.13), ESPECIES)
    expect(screen.queryByLabelText('Comparación de la cartera original contra la propuesta')).not.toBeInTheDocument()
  })

  it('al aceptar, aparecen las dos columnas con las mismas 4 naturalezas y los 6 ejes cada una (GWT-1)', async () => {
    const usuario = userEvent.setup()
    renderizar(candidata(COSTO_VERIFICABLE, 0.13), ESPECIES)

    await usuario.click(screen.getByRole('button', { name: 'aceptar' }))

    expect(await screen.findByLabelText('Comparación de la cartera original contra la propuesta')).toBeInTheDocument()
    const original = within(screen.getByLabelText('Cartera original'))
    const propuesta = within(screen.getByLabelText('Cartera propuesta'))
    expect(original.getByLabelText('Vector de riesgo')).toBeInTheDocument()
    expect(propuesta.getByLabelText('Vector de riesgo')).toBeInTheDocument()
    // Las cuatro naturalezas fijas aparecen en las dos columnas, aunque una (tna_nominal_ars) no
    // tenga ninguna posición en ninguna cartera — nunca se omite una fila por falta de dato.
    expect(original.getAllByText(/de la cartera/)).toHaveLength(4)
    expect(propuesta.getAllByText(/de la cartera/)).toHaveLength(4)
  })

  it('marca el mes que se vacía y el que se llena en la cordillera propuesta (GWT-2)', async () => {
    const usuario = userEvent.setup()
    renderizar(candidata(COSTO_VERIFICABLE, 0.13), ESPECIES)

    await usuario.click(screen.getByRole('button', { name: 'aceptar' }))
    await screen.findByLabelText('Comparación de la cartera original contra la propuesta')

    expect(await screen.findByTitle('Se vacía')).toBeInTheDocument()
    expect(screen.getByTitle('Se llena')).toBeInTheDocument()
    expect(screen.getByText(/▼ m1/)).toBeInTheDocument()
    expect(screen.getByText(/▲ m2/)).toBeInTheDocument()
  })

  it('el costo total acumulado está a la vista junto a los deltas de renta y rendimiento (GWT-3)', async () => {
    const usuario = userEvent.setup()
    renderizar(candidata(COSTO_VERIFICABLE, 0.13), ESPECIES)

    await usuario.click(screen.getByRole('button', { name: 'aceptar' }))
    const resultado = within(await screen.findByLabelText('Resultado neto'))

    expect(resultado.getByText(/Costo total de rotación acumulado/)).toHaveTextContent('US$ 20,00')
    expect(resultado.getByText(/Renta anual en dólares/)).toHaveTextContent('10,00% → 15,00% (+5,00%)')
    expect(resultado.getByText(/TIR en dólares/)).toHaveTextContent('11,00% → 13,00% (+2,00%)')
  })

  it('costo no verificable: se declara el par nombrado y el total no lo incluye', async () => {
    const usuario = userEvent.setup()
    renderizar(candidata(null, 0.13), ESPECIES)

    await usuario.click(screen.getByRole('button', { name: 'aceptar' }))
    const resultado = within(await screen.findByLabelText('Resultado neto'))

    expect(resultado.getByText(/Costo total de rotación acumulado/)).toHaveTextContent('s/d')
    expect(resultado.getByText(/No entran al total/)).toHaveTextContent('AL30D->GD30D')
  })

  it('sin rendimiento informado en un lado, el delta declara s/d en vez de inventarlo', async () => {
    const usuario = userEvent.setup()
    const especiesSinRendimientoDestino = [
      especie({ ticker: 'AL30D' }),
      especie({ ticker: 'GD30D', emision: 'GD30', duracion: 2.5, volumen_usd: 300_000, rendimiento: null }),
    ]
    renderizar(candidata(COSTO_VERIFICABLE, null), especiesSinRendimientoDestino)

    await usuario.click(screen.getByRole('button', { name: 'aceptar' }))
    const resultado = within(await screen.findByLabelText('Resultado neto'))

    expect(resultado.getByText(/TIR en dólares/)).toHaveTextContent('11,00% → s/d')
  })
})
