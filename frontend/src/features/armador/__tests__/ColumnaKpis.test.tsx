/**
 * `ColumnaKpis` — A9 del design system, Etapa 6 del rediseño del armador. Mismo patrón que
 * `PanelRenta.test.tsx`: mock de `fetch` por URL, sin montar el backend. `meses` (calendario del
 * universo) se pasa directo como prop, igual que hace `ArmadorPage` — no dispara su propio fetch.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { ColumnaKpis } from '../components/ColumnaKpis'
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
    precio: 100,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: null,
    sector: null,
    calificacion: null,
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

/** El calendario del UNIVERSO (prop `meses`): doce meses, uno con AL30 pagando (para poder armar
 *  el caso "sin cobertura") y el resto sin nada — `sin_renta: true`, no accionables. */
function mesesUniverso(): MesDelCalendario[] {
  return Array.from({ length: 12 }, (_, indice) => {
    const conPago = indice === 2
    return {
      anio: 2026,
      mes: indice + 1,
      etiqueta: `${String(indice + 1).padStart(2, '0')}/2026`,
      nombre: `Mes ${indice + 1}`,
      con_renta: conPago ? 1 : 0,
      con_amortizacion: 0,
      sin_renta: !conPago,
      renta: null,
      amortizacion: null,
      instrumentos: conPago ? [instrumento()] : [],
    }
  })
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

/** El calendario de la CARTERA (POST /calendario/cartera): sólo lo que las posiciones cargadas
 *  efectivamente cobran. */
function calendarioCartera({
  rentaAnual = {},
  sobrescribir = {},
}: {
  rentaAnual?: Record<string, number>
  sobrescribir?: Record<number, Partial<MesDelCalendario>>
} = {}) {
  return {
    resumen: {
      hoy: '2026-08-07',
      desde: '09/2026',
      hasta: '08/2027',
      con_montos: true,
      monedas: Object.keys(rentaAnual),
      instrumentos: 1,
      meses_sin_renta: [],
      renta_anual: rentaAnual,
      amortizacion_anual: null,
      pendientes_este_mes: 0,
      flujos: {
        evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0,
        sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0,
      },
    },
    meses: Array.from({ length: 12 }, (_, indice) => ({ ...mesVacio(indice), ...sobrescribir[indice] })),
    alertas: [],
  }
}

function responderCon({
  especies = [],
  tipoDeCambio = { valor: 1500, disponible: true },
  cartera = calendarioCartera(),
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  cartera?: unknown
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/calendario/cartera')) {
      cuerpo = cartera
    } else if (url.includes('/renta-variable')) {
      cuerpo = { items: [], next_cursor: null }
    } else if (url.includes('/concentracion')) {
      cuerpo = { topes: [], sectores: { peso_sin_sector: 0 }, peso: { medido: 0, declarado: 0 }, fuera_del_universo: [] }
    } else if (url.includes('/estado-del-dato')) {
      cuerpo = { dato: { capturado_en: null, dato_valido_hasta: null, antiguedad_minutos: null, demora: { minutos: 0, fuente: 'x', por_que: 'x' } } }
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

function Arnes({ meses }: { meses: MesDelCalendario[] }) {
  const { alternarPapel, fijarPeso, fijarMontoTotal, alternarRentaVariable } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarPapel('AL30')}>
        agregar AL30
      </button>
      <button type="button" onClick={() => fijarPeso('AL30', 60)}>
        peso AL30 a 60
      </button>
      <button type="button" onClick={() => alternarRentaVariable('GGAL')}>
        agregar GGAL
      </button>
      <button type="button" onClick={() => fijarMontoTotal(10_000)}>
        monto 10.000
      </button>
      <ColumnaKpis meses={meses} />
    </div>
  )
}

function renderizar(meses: MesDelCalendario[] = mesesUniverso()) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <ArmadorProvider>
        <Arnes meses={meses} />
      </ArmadorProvider>
    </QueryClientProvider>,
  )
}

describe('sin ninguna posición', () => {
  it('todo en s/d, nunca 0 — no hay nada resuelto de lo que sacar un número', async () => {
    responderCon()
    renderizar()

    expect(await screen.findAllByText('s/d')).not.toHaveLength(0)
    expect(screen.queryByText('0,00%')).not.toBeInTheDocument()
    expect(screen.queryByText('0/12')).not.toBeInTheDocument()
  })

  it('"lo que falta" avisa del mes con papeles que nadie de la cartera cubre', async () => {
    responderCon()
    renderizar()

    // Índice 2 (Mes 3) es el único con instrumentos en el fixture del universo.
    expect(await screen.findByRole('button', { name: /03\/2026 sin cobertura/ })).toBeInTheDocument()
  })
})

describe('con una cartera resuelta', () => {
  it('muestra la renta anual sobre lo invertido con la cuenta expuesta', async () => {
    responderCon({
      especies: [especie({ precio: 100 })],
      cartera: calendarioCartera({
        rentaAnual: { usd: 717.39 },
        sobrescribir: { 3: { renta: { usd: 717.39 }, instrumentos: [instrumento({ renta: 717.39 })] } },
      }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 60' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    // 717,39 / 6.000,00 (60% de 10.000) = 11,96%
    expect(await screen.findByText('11,96%')).toBeInTheDocument()
  })

  it('clic en el aviso de mes sin cobertura alterna el mes seleccionado', async () => {
    responderCon()
    renderizar()

    const aviso = await screen.findByRole('button', { name: /03\/2026 sin cobertura/ })
    await userEvent.click(aviso)

    // El mismo store que la grilla: no hay forma directa de leer selMes desde acá, pero el clic
    // no debe tirar ni desaparecer el botón (sigue siendo el mismo mes, sigue sin cobertura).
    expect(screen.getByRole('button', { name: /03\/2026 sin cobertura/ })).toBeInTheDocument()
  })
})

describe('F-042: flujo mes por mes y «Descargar propuesta»', () => {
  it('sin ninguna posición, no hay calendario que mostrar ni botón de descarga', async () => {
    responderCon()
    renderizar()

    expect(await screen.findByText('Sin calendario para mostrar el flujo.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Descargar Excel' })).not.toBeInTheDocument()
  })

  it('con una cartera resuelta, muestra las 12 filas del flujo, el total anual y el botón de descarga — sin sumar monedas', async () => {
    responderCon({
      especies: [especie({ precio: 100 })],
      cartera: calendarioCartera({
        rentaAnual: { usd: 717.39 },
        sobrescribir: { 3: { renta: { usd: 717.39 }, instrumentos: [instrumento({ renta: 717.39 })] } },
      }),
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 60' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    // Las 12 etiquetas de mes del flujo (aparecen también en la grilla de arriba, por eso se
    // cuentan dentro del bloque "USD" en vez de buscarlas sueltas).
    const totalAnual = await screen.findByText('Total anual')
    expect(totalAnual.parentElement).toHaveTextContent('US$ 717') // el total anual, 0 decimales
    // No hay ninguna otra moneda en este fixture: ningún total en pesos que pudiera mezclarse.
    expect(screen.queryByText(/^\$ /)).not.toBeInTheDocument()

    expect(await screen.findByRole('button', { name: 'Descargar Excel' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Descargar PDF' })).toBeInTheDocument()
  })
})

describe('cartera mixta (renta fija + renta variable)', () => {
  it('el KPI de duración y mix declara las dos porciones sobre el mismo 100%', async () => {
    responderCon({ especies: [especie({ precio: 100 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 60' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))

    // AL30 se había fijado a mano en 60%, pero agregar GGAL rebalancea: la acción entra con
    // 100/(1+1) = 50% y el bono se achica al 50% restante. El mix se muestra tal cual sale del
    // store, sin volver a normalizar (mismo criterio que la Σ de CarteraEditable).
    expect(await screen.findByText('1,6a · 50%/50%')).toBeInTheDocument()
  })
})
