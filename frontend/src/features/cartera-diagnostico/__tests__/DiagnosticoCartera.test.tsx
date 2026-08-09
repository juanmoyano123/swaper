/**
 * `DiagnosticoCartera` vista desde la pantalla — F-030. Mismo patrón que `PanelConcentracion.test`
 * y `PanelRenta.test` del armador: `fetch` mockeado por URL, sin montar el backend. El motor puro
 * se cubre aparte en `valuacion.test.ts` y la paridad con el armador en `paridad.test.ts`; acá lo
 * que importa es que la pantalla muestre lo que esos motores calcularon, sin llamar a los
 * endpoints de renta/concentración cuando no hay nada valuable, y sin esconder lo excluido.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { PosicionCruda } from '@/features/cartera-ingreso/types'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import type { MesDelCalendario } from '@/lib/cartera/esquemaCalendario'
import type { Concentracion } from '@/lib/cartera/esquemaConcentracion'

import { DiagnosticoCartera } from '../components/DiagnosticoCartera'

afterEach(() => {
  vi.unstubAllGlobals()
})

function cruda(tickerDeclarado: string, extra: Partial<PosicionCruda> = {}): PosicionCruda {
  return {
    id: `id-${tickerDeclarado}`,
    fila: 1,
    tickerDeclarado,
    nominal: null,
    monto: 1000,
    valida: true,
    motivo: null,
    ...extra,
  }
}

function resueltaF029(ticker: string, extra: Record<string, unknown> = {}) {
  return {
    id: `id-${ticker}`,
    fila: 1,
    ticker_declarado: ticker,
    nominal: 1000,
    monto: null,
    resuelta: true,
    ticker,
    emision: ticker,
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

function noResueltaF029(ticker: string, extra: Record<string, unknown> = {}) {
  return {
    ...resueltaF029(ticker),
    nominal: null,
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

function cobertura(extra: Record<string, unknown> = {}) {
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
    dato_sano: true,
    hermanas: [],
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
      flujos: {
        evaluados: 1,
        con_flujos: 1,
        pagos: 1,
        sin_cronograma: 0,
        sin_paridad: 0,
        sin_paridad_que_cotizan: 0,
        vencidos: 0,
      },
    },
    meses: Array.from({ length: 12 }, (_, indice) => ({ ...mesVacio(indice), ...sobrescribir[indice] })),
    alertas: [],
  }
}

function concentracion(extra: Partial<Concentracion> = {}): Concentracion {
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
    distribucion: {
      sector: [{ nombre: 'Soberano', peso: 100, sin_dato: false }],
      ley: [{ nombre: 'Ley N.Y.', peso: 100, sin_dato: false }],
      naturaleza: [{ nombre: 'TIR en dólares (hard dollar)', peso: 100, sin_dato: false }],
    },
    sectores: { presentes: ['Soberano'], cantidad: 1, minimo: 3, suficiente: false, peso_sin_sector: 0 },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    alertas: [
      {
        codigo: 'concentracion_soberana',
        mensaje: 'Riesgo soberano argentino quedó en 100,0 %, 35,0 pp por encima del tope de 65 %.',
        severidad: 'advertencia',
        accion_requerida: null,
        detalle: {},
      },
    ],
    ...extra,
  }
}

function responderCon({
  resolucion,
  especies = [especie()],
  tipoDeCambio = { valor: 1500, disponible: true },
  cartera,
  veredicto,
}: {
  resolucion: unknown
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  cartera?: unknown
  veredicto?: unknown
}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/posiciones/resolver')) {
      cuerpo = resolucion
    } else if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/calendario/cartera')) {
      cuerpo = cartera ?? calendario({ rentaAnual: {} })
    } else if (url.includes('/concentracion')) {
      cuerpo = veredicto ?? concentracion()
    } else {
      throw new Error(`fetch no mockeado en este test: ${url} ${init?.method ?? ''}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function pedidosA(fetchMock: ReturnType<typeof responderCon>, ruta: string) {
  return fetchMock.mock.calls.filter(([entrada]) => String(entrada).includes(ruta))
}

function renderizar(posiciones: PosicionCruda[]) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <DiagnosticoCartera posiciones={posiciones} />
    </QueryClientProvider>,
  )
}

describe('sin posiciones cargadas', () => {
  it('no renderiza nada y no llama a ningún endpoint', () => {
    const fetchMock = responderCon({ resolucion: { posiciones: [], cobertura: cobertura(), alertas: [] } })
    const { container } = renderizar([])
    expect(container).toBeEmptyDOMElement()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('ninguna posición valuable', () => {
  it('lo declara y no llama a calendario ni a concentración', async () => {
    const fetchMock = responderCon({
      resolucion: {
        posiciones: [resueltaF029('AL30D', { nominal: null, monto: 5000 })],
        cobertura: cobertura(),
        alertas: [],
      },
    })

    renderizar([cruda('AL30D', { nominal: null, monto: 5000 })])

    expect(await screen.findByText(/Cartera no valuable/)).toBeInTheDocument()
    expect(screen.getByText(/sin nominal declarado/)).toBeInTheDocument()
    expect(pedidosA(fetchMock, '/calendario/cartera')).toHaveLength(0)
    expect(pedidosA(fetchMock, '/concentracion')).toHaveLength(0)
  })
})

describe('una cartera valuada', () => {
  it('muestra renta, rendimientos por naturaleza, plazo y concentración', async () => {
    responderCon({
      resolucion: {
        posiciones: [resueltaF029('AL30D')],
        cobertura: cobertura(),
        alertas: [],
      },
      cartera: calendario({
        monedas: ['usd'],
        rentaAnual: { usd: 71.7 },
        sobrescribir: {
          3: {
            renta: { usd: 71.7 },
            instrumentos: [
              {
                ticker: 'AL30D',
                emision: 'AL30',
                fechas: ['2026-12-09'],
                pct_renta: 0.00717,
                pct_amortizacion: 0,
                renta: 71.7,
                amortizacion: null,
                moneda: 'usd',
                rendimiento: 0.11,
                naturaleza: 'tir_usd',
                naturaleza_nombre: 'TIR en dólares (hard dollar)',
                vencimiento: '2030-07-09',
              },
            ],
          },
        },
      }),
    })

    renderizar([cruda('AL30D')])

    expect(await screen.findByText(/1 posición valuada de 1 cargadas/)).toBeInTheDocument()
    expect(screen.getByText('TIR en dólares (hard dollar)')).toBeInTheDocument()
    expect(screen.getByText(/Plazo promedio: 3,5 años/)).toBeInTheDocument()
    expect(await screen.findByText('Renta mensual en dólares')).toBeInTheDocument()
    expect(await screen.findByText('Riesgo soberano')).toBeInTheDocument()
  })

  it('no llama a calendario ni a concentración con listas vacías', async () => {
    const fetchMock = responderCon({
      resolucion: { posiciones: [resueltaF029('AL30D')], cobertura: cobertura(), alertas: [] },
    })

    renderizar([cruda('AL30D')])

    await screen.findByText('Riesgo soberano')

    const cuerpoCalendario = JSON.parse(String(pedidosA(fetchMock, '/calendario/cartera')[0]?.[1]?.body))
    expect(cuerpoCalendario.posiciones).toEqual([{ ticker: 'AL30D', monto: 1000 }])

    const cuerpoConcentracion = JSON.parse(String(pedidosA(fetchMock, '/concentracion')[0]?.[1]?.body))
    expect(cuerpoConcentracion.posiciones).toEqual([{ ticker: 'AL30D', peso: 100 }])
  })
})

describe('posiciones excluidas', () => {
  it('se declaran, con su motivo, sin duplicar el mensaje de F-029 para las no resueltas', async () => {
    responderCon({
      resolucion: {
        posiciones: [resueltaF029('AL30D'), noResueltaF029('NOEXISTE')],
        cobertura: cobertura({ posiciones: 2, no_resueltas: 1 }),
        alertas: [],
      },
    })

    renderizar([cruda('AL30D'), cruda('NOEXISTE')])

    expect(await screen.findByText(/1 posición valuada de 2 cargadas/)).toBeInTheDocument()
    expect(await screen.findByText(/1 posición excluida de renta, rendimientos y concentración/)).toBeInTheDocument()
    expect(screen.getByText(/no resueltas contra el universo/)).toBeInTheDocument()
  })
})
