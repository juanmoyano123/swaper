/**
 * `PanelRenta` vista desde la pantalla — F-021, mismo patrón que `CarteraEditable.test.tsx`: mock
 * de `fetch` por URL, sin montar el backend. El motor puro se cubre aparte en `renta.test.ts`; acá
 * lo que importa es que el panel muestre lo que el motor calculó, sin normalizar nada en silencio,
 * y que las dos cordilleras nunca aparezcan mezcladas.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelRenta } from '../components/PanelRenta'
import type { Especie, InstrumentoDelMes, MesDelCalendario } from '../lib/schema'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    sufijo_liquidacion: null,
    clase_activo: 'ON',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.1123,
    duracion: 3.2,
    vencimiento: '2030-07-09',
    ley: 'ARG',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 105,
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

function instrumento(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    fechas: ['2026-09-09'],
    pct_renta: 0.01,
    pct_amortizacion: 0,
    renta: 100,
    amortizacion: null,
    moneda: 'usd',
    rendimiento: 0.11,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    vencimiento: '2030-07-09',
    ...extra,
  }
}

function mesVacio(indice: number): MesDelCalendario {
  return {
    anio: 2026,
    mes: indice + 1,
    etiqueta: `${String(indice + 1).padStart(2, '0')}/2026`,
    nombre: `Mes ${indice + 1}`,
    con_renta: 0,
    con_amortizacion: 0,
    sin_renta: true,
    renta: null,
    amortizacion: null,
    instrumentos: [],
  }
}

function calendario({
  monedas = ['usd'],
  rentaAnual,
  sobrescribir = {},
}: {
  monedas?: string[]
  rentaAnual: Record<string, number>
  sobrescribir?: Record<number, Partial<MesDelCalendario>>
}) {
  return {
    resumen: {
      hoy: '2026-08-07',
      desde: '09/2026',
      hasta: '08/2027',
      con_montos: true,
      monedas,
      instrumentos: 1,
      meses_sin_renta: [],
      renta_anual: rentaAnual,
      amortizacion_anual: null,
      pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses: Array.from({ length: 12 }, (_, indice) => ({ ...mesVacio(indice), ...sobrescribir[indice] })),
    alertas: [],
  }
}

function responderCon({
  especies = [],
  tipoDeCambio = { valor: 1500, disponible: true },
  cartera,
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  cartera: unknown
}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/calendario/cartera')) {
      cuerpo = cartera
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
      <PanelRenta />
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
  it('dice qué falta en vez de mostrar un gráfico vacío sin explicación', () => {
    responderCon({ cartera: calendario({ rentaAnual: {} }) })
    renderizar()

    expect(screen.getByText(/Sin posiciones de renta fija con monto asignado/)).toBeInTheDocument()
  })
})

describe('con una cartera resuelta en dólares', () => {
  it('GWT de F-021: muestra la renta anual sobre lo invertido con la cuenta expuesta', async () => {
    responderCon({
      especies: [especie({ precio: 100 })], // sin lámina: invertido = objetivo = monto total = 10.000
      cartera: calendario({
        monedas: ['usd'],
        rentaAnual: { usd: 717.39 },
        sobrescribir: { 3: { renta: { usd: 717.39 }, instrumentos: [instrumento({ renta: 717.39 })] } },
      }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 100' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    // 717,39 / 10.000,00 = 7,17%
    expect(await screen.findByText('7,17%')).toBeInTheDocument()
    expect(screen.getByText(/US\$ 717,39 \/ US\$ 10\.000,00 = 7,17%/)).toBeInTheDocument()
  })

  it('sin posiciones en pesos, la cordillera en pesos declara el estado vacío en vez de esconderse', async () => {
    responderCon({
      especies: [especie()],
      cartera: calendario({ monedas: ['usd'], rentaAnual: { usd: 100 } }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    expect(await screen.findByText(/Sin posiciones que cobren en pesos/)).toBeInTheDocument()
    expect(screen.queryByText('Cordillera en pesos')).not.toBeInTheDocument()
  })
})

describe('con posiciones en pesos y en dólares', () => {
  it('GWT: cada moneda de cobro sale con su propia tarjeta, nunca sumadas ni promediadas', async () => {
    const TX26 = especie({
      ticker: 'TX26',
      emision: 'TX26',
      segmento: 'cer',
      naturaleza: 'tasa_real_cer',
      naturaleza_nombre: 'Tasa real sobre CER',
      moneda_cotizacion: 'ARS',
      precio: 1000,
    })
    responderCon({
      especies: [especie({ precio: 100 }), TX26],
      cartera: calendario({
        monedas: ['usd', 'ars'],
        rentaAnual: { usd: 500, ars: 200000 },
        sobrescribir: {
          2: {
            renta: { usd: 500, ars: 200000 },
            instrumentos: [instrumento({ renta: 500 }), instrumento({ ticker: 'TX26', moneda: 'ars', renta: 200000 })],
          },
        },
      }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    expect(await screen.findByText('Cordillera en dólares')).toBeInTheDocument()
    expect(screen.getByText('Cordillera en pesos')).toBeInTheDocument()
    expect(screen.getByText('Renta anual en dólares')).toBeInTheDocument()
    expect(screen.getByText('Renta anual en pesos')).toBeInTheDocument()
  })
})

describe('mes seleccionado', () => {
  it('clic en una columna de la cordillera alterna el mes seleccionado del store', async () => {
    responderCon({
      especies: [especie({ precio: 100 })],
      cartera: calendario({
        monedas: ['usd'],
        rentaAnual: { usd: 100 },
        sobrescribir: { 2: { renta: { usd: 100 }, instrumentos: [instrumento({ renta: 100 })] } },
      }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    const columna = await screen.findByRole('button', { name: /Mes 3: US\$ 100/ })
    expect(columna).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(columna)
    expect(columna).toHaveAttribute('aria-pressed', 'true')
  })
})
