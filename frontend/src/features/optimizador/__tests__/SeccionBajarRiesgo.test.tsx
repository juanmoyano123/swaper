/**
 * `SeccionBajarRiesgo` vista desde la pantalla — F-033. La lib pura ya se prueba entera en
 * `lib/rotaciones/__tests__/bajarRiesgo.test.ts`; acá se verifica lo que sólo se rompe en la
 * pantalla: la preselección de duración, que cambiar el eje dispara la evaluación correspondiente
 * (crédito/moneda muestran "no medible" en vez de una lista vacía muda), y que el estado "no hay
 * propuesta" se declara con motivo.
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

import { SeccionBajarRiesgo } from '../components/SeccionBajarRiesgo'
import { PlanRotacionProvider } from '../store/planRotacionStore'

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

function veredicto(extra: Partial<Concentracion> = {}): Concentracion {
  return {
    perfil: 'moderado',
    limites: { tope_rend_usd: 0.15, percentil_liquidez: 25, max_emisor: 15, max_soberano: 65, max_sector: 40, min_sectores: 3 },
    topes: [
      { tipo: 'emisor', clave: 'ARG', nombre: 'República Argentina', peso: 40, tope: 15, excedido: true, exceso: 25 },
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

function resultadoRotaciones(candidatas: unknown[] = []) {
  return {
    perfil: 'moderado',
    candidatas,
    origenes_evaluados: ['AL30D'],
    fuera_del_universo: [],
    sin_rendimiento: [],
    alertas: [],
  }
}

function responderCon({
  especies = [especie()],
  concentracion = veredicto(),
  rotaciones = resultadoRotaciones(),
}: { especies?: Especie[]; concentracion?: unknown; rotaciones?: unknown } = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/rotaciones')) {
      cuerpo = rotaciones
    } else if (url.includes('/concentracion')) {
      cuerpo = concentracion
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(new Response(JSON.stringify(cuerpo), { status: 200, headers: { 'Content-Type': 'application/json' } }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar(opciones: { excluir?: ReadonlySet<string> } = {}) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <PlanRotacionProvider posiciones={[{ ticker: 'AL30D', peso: 100 }]}>
        <SeccionBajarRiesgo posiciones={[{ ticker: 'AL30D', peso: 100 }]} perfil="moderado" excluir={opciones.excluir} />
      </PlanRotacionProvider>
    </QueryClientProvider>,
  )
}

describe('preselección del eje primario', () => {
  it('arranca en Duración', async () => {
    responderCon()
    renderizar()

    const selector = (await screen.findByLabelText('Eje a mejorar')) as HTMLSelectElement
    expect(selector.value).toBe('duracion')
  })
})

describe('cambiar el eje primario', () => {
  it('crédito muestra el estado "no medible", no una lista vacía', async () => {
    responderCon()
    const usuario = userEvent.setup()
    renderizar()

    const selector = await screen.findByLabelText('Eje a mejorar')
    await usuario.selectOptions(selector, 'credito')

    const mensaje = await screen.findByRole('status')
    expect(mensaje).toHaveTextContent(/es compositivo/)
    expect(mensaje).toHaveTextContent(/Crédito/)
  })

  it('moneda muestra el estado "no medible", no una lista vacía', async () => {
    responderCon()
    const usuario = userEvent.setup()
    renderizar()

    const selector = await screen.findByLabelText('Eje a mejorar')
    await usuario.selectOptions(selector, 'moneda')

    const mensaje = await screen.findByRole('status')
    expect(mensaje).toHaveTextContent(/es compositivo/)
    expect(mensaje).toHaveTextContent(/Moneda/)
  })
})

describe('sin candidatas de rotación', () => {
  it('declara que no hay propuesta, con el motivo', async () => {
    responderCon({ rotaciones: resultadoRotaciones([]) })
    renderizar()

    expect(await screen.findByText(/No hay propuesta/)).toBeInTheDocument()
    expect(screen.getByText(/±0,5%/)).toBeInTheDocument()
  })
})

// El costo de rotar (F-035) empieza a mostrarse en la fila con F-034: hasta entonces el dato
// llegaba del backend y el esquema lo descartaba. Estos dos casos fijan la distinción que hace a
// la feature — un costo medido no se lee igual que uno que no se pudo verificar.
describe('costo de rotar en la fila', () => {
  function candidataQueSobrevive(costo: unknown) {
    // Baja la duración (3,5 → 2,5) sin mover nada más: pasa el filtro con duración como primario.
    return {
      tipo: 'mejora_perfil',
      segmento: 'usd_hard',
      origen: { ticker: 'AL30D', emisor: 'República Argentina', rendimiento: 0.11, duracion: 3.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 100_000 },
      destino: { ticker: 'GD30D', emisor: 'República Argentina', rendimiento: 0.112, duracion: 2.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 300_000 },
      delta: { rendimiento_pp: 0.2, duracion: -1 },
      flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: false, mejora_volumen: true, posible_distress: false },
      premio_ley: null,
      riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
      costo,
    }
  }

  const ESPECIES = [especie(), especie({ ticker: 'GD30D', emision: 'GD30', duracion: 2.5, volumen_usd: 300_000 })]

  it('muestra el costo medido y en cuánto lo paga la mejora', async () => {
    responderCon({
      especies: ESPECIES,
      rotaciones: resultadoRotaciones([
        candidataQueSobrevive({
          arancel_pct_por_pata: 0.75,
          spread_origen_pct: 1.2,
          spread_destino_pct: 0.8,
          total_pct: 2.5,
          verificable: true,
          elevado: false,
          payback_meses: 16.7,
        }),
      ]),
    })
    renderizar()

    expect(await screen.findByText(/Costo de rotar 2,50%/)).toBeInTheDocument()
    expect(screen.getByText(/lo paga en 16,7 meses/)).toBeInTheDocument()
  })

  it('sin punta en una pata declara que no es verificable, sin inventar un costo', async () => {
    responderCon({
      especies: ESPECIES,
      rotaciones: resultadoRotaciones([
        candidataQueSobrevive({
          arancel_pct_por_pata: 0.75,
          spread_origen_pct: 1.2,
          spread_destino_pct: null,
          total_pct: null,
          verificable: false,
          elevado: null,
          payback_meses: null,
        }),
      ]),
    })
    renderizar()

    const nota = await screen.findByText(/no verificable/)
    expect(nota).toHaveTextContent(/falta punta de mercado/)
    // El único número que aparece es el arancel, declarado como piso y rotulado "estimado" —
    // nunca un total supuesto ni presentado como una medición.
    expect(nota).toHaveTextContent(/arancel estimado 0,75% por pata/)
  })
})

// F-036: decisión de la fila y exclusión de lo ya decidido en la sesión.
describe('decisión de la fila', () => {
  const CANDIDATA = {
    tipo: 'mejora_perfil',
    segmento: 'usd_hard',
    origen: { ticker: 'AL30D', emisor: 'República Argentina', rendimiento: 0.11, duracion: 3.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 100_000 },
    destino: { ticker: 'GD30D', emisor: 'República Argentina', rendimiento: 0.112, duracion: 2.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 300_000 },
    delta: { rendimiento_pp: 0.2, duracion: -1 },
    flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: false, mejora_volumen: true, posible_distress: false },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: null,
  }
  const ESPECIES = [especie(), especie({ ticker: 'GD30D', emision: 'GD30', duracion: 2.5, volumen_usd: 300_000 })]

  it('cada fila trae Aceptar y Descartar', async () => {
    responderCon({ especies: ESPECIES, rotaciones: resultadoRotaciones([CANDIDATA]) })
    renderizar()

    expect(await screen.findByRole('button', { name: 'Aceptar' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Descartar' })).toBeInTheDocument()
  })

  it('con la clave en excluir, la fila no aparece y el conteo se declara (GWT-4)', async () => {
    responderCon({ especies: ESPECIES, rotaciones: resultadoRotaciones([CANDIDATA]) })
    renderizar({ excluir: new Set(['AL30D->GD30D']) })

    expect(await screen.findByText(/1 rotación no se propone/)).toBeInTheDocument()
    expect(screen.queryByText(/AL30D.*GD30D/)).not.toBeInTheDocument()
  })

  it('sin excluir, la fila aparece normalmente', async () => {
    responderCon({ especies: ESPECIES, rotaciones: resultadoRotaciones([CANDIDATA]) })
    renderizar()

    expect(await screen.findByText(/AL30D.*GD30D/)).toBeInTheDocument()
  })
})
