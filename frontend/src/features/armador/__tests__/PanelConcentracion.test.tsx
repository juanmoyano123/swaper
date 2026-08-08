/**
 * `PanelConcentracion` vista desde la pantalla — F-020, mismo patrón que `CarteraEditable.test`:
 * `fetch` mockeado por URL, sin montar el backend.
 *
 * Los topes y la distribución ya están probados del lado del servidor
 * (`backend/tests/test_concentracion_servicio.py`, que corre los seis GWT de la ficha). Lo que se
 * verifica acá es lo que sólo se puede romper en pantalla: que el veredicto llegue completo, que
 * un tope excedido se vea como excedido, que el panel diga **sobre qué peso** midió, y que el
 * perfil que se elige sea el que viaja en el pedido.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelConcentracion } from '../components/PanelConcentracion'
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
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

const YMCHO = especie({
  ticker: 'YMCHO',
  emision: 'YMCH',
  clase_activo: 'on_corporativo',
  emisor: 'YPF S.A.',
  sector: 'O&G',
  precio: 99,
})

/** Una respuesta del endpoint con el shape completo; cada test pisa lo que le importa. */
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
      {
        tipo: 'soberano',
        clave: 'SOBERANO_AR',
        nombre: 'Riesgo soberano argentino (todas las emisiones del Tesoro)',
        peso: 70,
        tope: 65,
        excedido: true,
        exceso: 5,
      },
      {
        tipo: 'emisor',
        clave: 'YMC',
        nombre: 'YPF S.A.',
        peso: 30,
        tope: 15,
        excedido: true,
        exceso: 15,
      },
      { tipo: 'sector', clave: 'O&G', nombre: 'O&G', peso: 30, tope: 40, excedido: false, exceso: 0 },
    ],
    excedidos: 2,
    distribucion: {
      sector: [
        { nombre: 'Soberano', peso: 70, sin_dato: false },
        { nombre: 'O&G', peso: 30, sin_dato: false },
      ],
      ley: [
        { nombre: 'Ley N.Y.', peso: 70, sin_dato: false },
        { nombre: 'ley no informada', peso: 30, sin_dato: true },
      ],
      naturaleza: [{ nombre: 'TIR en dólares (hard dollar)', peso: 100, sin_dato: false }],
    },
    sectores: {
      presentes: ['O&G', 'Soberano'],
      cantidad: 2,
      minimo: 3,
      suficiente: false,
      peso_sin_sector: 0,
    },
    peso: { declarado: 100, medido: 100 },
    fuera_del_universo: [],
    alertas: [
      {
        codigo: 'concentracion_soberana',
        mensaje: 'Riesgo soberano argentino quedó en 70.0 %, 5.0 pp por encima del tope de 65 %.',
        severidad: 'advertencia',
        accion_requerida: null,
        detalle: {},
      },
      {
        codigo: 'concentracion_emisor',
        mensaje: 'YPF S.A. quedó en 30.0 %, 15.0 pp por encima del tope por emisor de 15 %.',
        severidad: 'advertencia',
        accion_requerida: null,
        detalle: {},
      },
    ],
    ...extra,
  }
}

function responderCon({
  especies = [especie(), YMCHO],
  tipoDeCambio = { valor: 1500, disponible: true },
  concentracion = veredicto(),
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  concentracion?: unknown
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion
    } else {
      throw new Error(`fetch no mockeado en este test: ${url} ${init?.method ?? ''}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function pedidosDeConcentracion(fetchMock: ReturnType<typeof responderCon>) {
  return fetchMock.mock.calls.filter(([entrada]) => String(entrada).includes('/concentracion'))
}

/** Expone las acciones que en la pantalla real dispara la grilla de F-016. */
function Arnes() {
  const { alternarPapel, fijarPeso, fijarMontoTotal } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        agregar GD30
      </button>
      <button type="button" onClick={() => alternarPapel('YMCHO')}>
        agregar YMCHO
      </button>
      <button type="button" onClick={() => fijarPeso('GD30', 70)}>
        peso GD30 a 70
      </button>
      <button type="button" onClick={() => fijarMontoTotal(10_000)}>
        monto 10.000
      </button>
      <PanelConcentracion />
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

async function conDosPosiciones() {
  await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))
  await userEvent.click(screen.getByRole('button', { name: 'agregar YMCHO' }))
}

describe('sin posiciones', () => {
  it('lo dice y no llama al endpoint, que exige al menos una', () => {
    const fetchMock = responderCon()
    renderizar()

    expect(screen.getByText(/Sin posiciones de renta fija/)).toBeInTheDocument()
    expect(pedidosDeConcentracion(fetchMock)).toHaveLength(0)
  })
})

describe('los topes', () => {
  it('muestra los tres ejes abiertos, sin componer un score de riesgo', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('Riesgo soberano')).toBeInTheDocument()
    expect(screen.getByText('Por emisor')).toBeInTheDocument()
    expect(screen.getByText('Por sector')).toBeInTheDocument()
  })

  it('marca en --neg el tope excedido y dice cuánto sobra', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('YPF S.A.')).toHaveStyle({ color: 'var(--neg)' })
    expect(screen.getByText('+15,0% sobre el tope')).toBeInTheDocument()
    // El que está dentro del tope no se tiñe.
    expect(screen.getByText('30,0% / 40%')).toHaveStyle({ color: 'var(--ac)' })
  })

  it('muestra el peso contra su tope y no como porcentaje del tope', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('70,0% / 65%')).toBeInTheDocument()
  })
})

describe('la distribución', () => {
  it('trae los tres cortes y muestra lo no informado como su propio tramo', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText('Legislación')).toBeInTheDocument()
    expect(screen.getByText('Naturaleza de tasa')).toBeInTheDocument()
    // El tramo sin dato se muestra con su peso, nunca repartido entre los conocidos.
    expect(screen.getByText('ley no informada')).toBeInTheDocument()
    expect(screen.getByText('Ley N.Y.')).toBeInTheDocument()
  })
})

describe('el mínimo de sectores', () => {
  it('advierte nombrando los sectores presentes cuando la cartera queda por debajo', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    const linea = await screen.findByText(/2 de 3 sectores mínimos/)
    expect(linea).toHaveTextContent('O&G, Soberano')
    expect(linea).toHaveStyle({ color: 'var(--ac2)' })
  })

  it('no advierte cuando alcanza el mínimo', async () => {
    responderCon({
      concentracion: veredicto({
        sectores: {
          presentes: ['Agro', 'Financiera', 'O&G'],
          cantidad: 3,
          minimo: 3,
          suficiente: true,
          peso_sin_sector: 0,
        },
      }),
    })
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText(/3 de 3 sectores mínimos/)).toHaveStyle({ color: 'var(--dim)' })
  })

  it('declara el peso sin sector informado, que no acredita diversificación', async () => {
    responderCon({
      concentracion: veredicto({
        sectores: {
          presentes: ['Soberano'],
          cantidad: 1,
          minimo: 3,
          suficiente: false,
          peso_sin_sector: 42.5,
        },
      }),
    })
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText(/42,5% sin sector informado/)).toBeInTheDocument()
  })
})

describe('las advertencias', () => {
  it('informan y no bloquean: se muestran y el panel sigue mostrando todo', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    const lista = await screen.findByRole('list', { name: 'Advertencias de concentración' })
    const avisos = within(lista).getAllByRole('listitem')
    expect(avisos).toHaveLength(2)
    expect(avisos[0]).toHaveTextContent('informa, no bloquea')
    // Y los topes siguen ahí: nada se oculta por haber advertido.
    expect(screen.getByText('Riesgo soberano')).toBeInTheDocument()
  })

  it('dice explícitamente cuando no hay ninguna, en vez de dejar el hueco', async () => {
    responderCon({ concentracion: veredicto({ alertas: [] }) })
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText(/dentro de todos los topes del perfil/)).toBeInTheDocument()
  })
})

describe('sobre qué peso se midió', () => {
  it('lo declara antes de mostrar cualquier número', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()

    // Sin monto total, `resolver` no calcula: se mide sobre la ponderación pedida, y se dice.
    expect(screen.getByText(/ninguna se pudo resolver a peso real/)).toBeInTheDocument()
  })

  it('usa el peso real cuando existe, y lo dice', async () => {
    responderCon()
    renderizar()
    await conDosPosiciones()
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    expect(await screen.findByText(/Medido sobre el peso real de las 2 posiciones/)).toBeInTheDocument()
  })

  it('manda el peso real, no la ponderación pedida', async () => {
    const fetchMock = responderCon()
    renderizar()
    await conDosPosiciones()
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))
    await screen.findByText(/Medido sobre el peso real/)

    const ultimo = pedidosDeConcentracion(fetchMock).at(-1)
    const init = ultimo?.[1] as RequestInit | undefined
    const cuerpo = JSON.parse(String(init?.body))
    // Precios distintos (70 y 99) con lámina 1: el peso real se separa del 50/50 pedido.
    expect(cuerpo.posiciones).toHaveLength(2)
    expect(cuerpo.posiciones.every((p: { peso: number }) => p.peso !== 50)).toBe(true)
  })

  it('declara la Σ declarada y la medida por separado, sin normalizar a 100', async () => {
    responderCon({
      concentracion: veredicto({
        peso: { declarado: 100, medido: 65 },
        fuera_del_universo: ['FCI Ahorro'],
      }),
    })
    renderizar()
    await conDosPosiciones()

    expect(await screen.findByText(/Σ declarada 100,0% · medida 65,0%/)).toBeInTheDocument()
    expect(screen.getByText(/1 posición\(es\) fuera del universo/)).toBeInTheDocument()
  })
})

describe('el perfil', () => {
  it('arranca en moderado y viaja en la URL del pedido', async () => {
    const fetchMock = responderCon()
    renderizar()
    await conDosPosiciones()
    await screen.findByText('Riesgo soberano')

    expect(String(pedidosDeConcentracion(fetchMock).at(-1)?.[0])).toContain('perfil=moderado')
  })

  it('cambiarlo vuelve a pedir contra el otro perfil', async () => {
    const fetchMock = responderCon()
    renderizar()
    await conDosPosiciones()
    await screen.findByText('Riesgo soberano')

    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'conservador')

    await vi.waitFor(() => {
      expect(String(pedidosDeConcentracion(fetchMock).at(-1)?.[0])).toContain('perfil=conservador')
    })
  })
})
