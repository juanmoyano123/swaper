/**
 * `SeccionSubirTir` vista desde la pantalla — F-034. La lib pura ya se prueba entera en
 * `lib/rotaciones/__tests__/subirTir.test.ts`; acá se verifica lo que sólo se rompe en el render:
 * que la contrapartida aparezca en la misma fila que la mejora (GWT-1), que una propuesta sin
 * deltas no se dibuje pero sí se cuente (GWT-2), que "ningún eje empeora" se diga con todas las
 * letras (GWT-3) y que la cobertura parcial viaje al lado del delta (GWT-4).
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'
import type { Concentracion } from '@/lib/cartera/esquemaConcentracion'
import type { Especie } from '@/lib/cartera/esquemaEspecie'

import { SeccionSubirTir } from '../components/SeccionSubirTir'

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
    limites: { tope_rend_usd: 0.15, percentil_liquidez: 25, max_emisor: 15, max_soberano: 65, max_sector: 40, min_sectores: 3 },
    topes: [
      { tipo: 'emisor', clave: 'ARG', nombre: 'República Argentina', peso: 100, tope: 15, excedido: true, exceso: 85 },
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

function especieRotacion(ticker: string, extra: Record<string, unknown> = {}) {
  return {
    ticker,
    emisor: 'República Argentina',
    rendimiento: 0.11,
    duracion: 3.5,
    moneda_cupon: 'USD',
    ley: 'Ley N.Y.',
    calificacion: null,
    lamina: 1,
    frecuencia_cupon: 'semestral',
    volumen_usd: 100_000,
    ...extra,
  }
}

function candidata(extra: { destino?: Record<string, unknown>; deltaDuracion?: number | null; costo?: unknown } = {}) {
  const destino = especieRotacion('AE38', { duracion: 5.8, ley: 'Ley Argentina', volumen_usd: 300_000, ...extra.destino })
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: especieRotacion('AL30D'),
    destino,
    delta: { rendimiento_pp: 1.8, duracion: extra.deltaDuracion === undefined ? 2.3 : extra.deltaDuracion },
    flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: true, mejora_volumen: true, posible_distress: false },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: extra.costo === undefined ? null : extra.costo,
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
  especies = [especie(), especie({ ticker: 'AE38', emision: 'AE38', duracion: 5.8, ley: 'Ley Argentina', volumen_usd: 300_000 })],
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

function renderizar(posiciones = [{ ticker: 'AL30D', peso: 100 }]) {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <SeccionSubirTir posiciones={posiciones} perfil="moderado" />
    </QueryClientProvider>,
  )
}

describe('GWT-1: la mejora y su contrapartida, en la misma fila', () => {
  it('declara el rendimiento, la duración y el cambio de ley juntos', async () => {
    responderCon({ rotaciones: resultadoRotaciones([candidata()]) })
    renderizar()

    const fila = await screen.findByRole('listitem')
    expect(fila).toHaveTextContent('AL30D → AE38')
    expect(fila).toHaveTextContent('Δ rendimiento +1,80%')
    expect(fila).toHaveTextContent('duración 3,5 años → 5,8 años')
    // El eje legislación se nombra por lo que mide —peso bajo ley extranjera— y no como un puntaje
    // que "baja", con los literales de ley tal como los declara la fuente.
    expect(fila).toHaveTextContent('peso bajo ley extranjera 100,0% → 0,0%')
    expect(fila).toHaveTextContent('Ley N.Y. → Ley Argentina')
  })
})

describe('GWT-2: sin deltas calculables no se muestra, pero se cuenta', () => {
  it('no dibuja la fila y declara cuántas quedaron sin mostrar y por qué', async () => {
    responderCon({ rotaciones: resultadoRotaciones([candidata({ deltaDuracion: null })]) })
    renderizar()

    expect(await screen.findByText(/1 rotación que sube el rendimiento/)).toBeInTheDocument()
    expect(screen.getByText(/1 sin mostrar/)).toBeInTheDocument()
    expect(screen.getByText(/duración — sin dato para medirlo/i)).toBeInTheDocument()
    // La lista de propuestas no existe. Se busca por su nombre accesible y no por `listitem`
    // suelto: el resumen de descartes también es una lista, y contarlo sería un falso negativo.
    expect(screen.queryByRole('list', { name: 'Rotaciones que suben el rendimiento' })).not.toBeInTheDocument()
  })
})

describe('el recuento de lo evaluado', () => {
  it('pluraliza sin romper la acentuación: "rotaciones", no "rotaciónes"', async () => {
    responderCon({
      rotaciones: resultadoRotaciones([candidata(), candidata({ destino: { ticker: 'AL35D' }, deltaDuracion: null })]),
    })
    renderizar()

    expect(await screen.findByText(/2 rotaciones que suben el rendimiento/)).toBeInTheDocument()
    expect(screen.queryByText(/rotaciónes/)).not.toBeInTheDocument()
  })
})

describe('GWT-3: sin contrapartida, se dice con todas las letras', () => {
  it('declara que ningún eje empeora en vez de dejar el lugar vacío', async () => {
    // Destino con menos duración y más volumen, misma ley y mismo emisor: nada empeora.
    responderCon({
      especies: [especie(), especie({ ticker: 'GD30D', emision: 'GD30', duracion: 2.5, volumen_usd: 300_000 })],
      rotaciones: resultadoRotaciones([
        candidata({
          destino: { ticker: 'GD30D', duracion: 2.5, ley: 'Ley N.Y.', volumen_usd: 300_000 },
          deltaDuracion: -1,
        }),
      ]),
    })
    renderizar()

    const fila = await screen.findByRole('listitem')
    expect(fila).toHaveTextContent(/Ningún eje empeora/)
  })
})

describe('GWT-4: la cobertura parcial viaja junto al delta', () => {
  it('declara sobre qué parte del peso está medido el eje', async () => {
    // Media cartera en una especie sin duración informada: el delta de la rotación sigue siendo
    // calculable, así que la fila se muestra y lo que falta se declara al lado.
    responderCon({
      especies: [
        especie(),
        especie({ ticker: 'AE38', emision: 'AE38', duracion: 5.8, ley: 'Ley Argentina', volumen_usd: 300_000 }),
        especie({ ticker: 'SINDUR', emision: 'SINDUR', duracion: null, volumen_usd: 50_000 }),
      ],
      rotaciones: resultadoRotaciones([candidata()]),
    })
    renderizar([
      { ticker: 'AL30D', peso: 50 },
      { ticker: 'SINDUR', peso: 50 },
    ])

    const fila = await screen.findByRole('listitem')
    expect(fila).toHaveTextContent(/cobertura parcial: duración medida sobre el 50% del peso actual/)
  })
})

describe('sin rotaciones que suban el rendimiento', () => {
  it('lo declara en vez de mostrar una lista vacía muda', async () => {
    responderCon({ rotaciones: resultadoRotaciones([]) })
    renderizar()

    // Por texto y no por `role="status"`: el estado de carga también lo usa, y buscarlo por rol
    // devolvería "Cargando…" antes de que la evaluación termine.
    expect(await screen.findByText(/no encontró rotaciones que suban el rendimiento/)).toBeInTheDocument()
  })

  it('las candidatas de mejora de perfil no cuentan como descarte de este modo', async () => {
    responderCon({
      rotaciones: resultadoRotaciones([{ ...candidata(), tipo: 'mejora_perfil' }]),
    })
    renderizar()

    expect(await screen.findByText(/no encontró rotaciones que suban el rendimiento/)).toBeInTheDocument()
    expect(screen.queryByText(/sin mostrar/)).not.toBeInTheDocument()
  })
})

describe('costo de rotar', () => {
  it('muestra el costo medido en la fila', async () => {
    responderCon({
      rotaciones: resultadoRotaciones([
        candidata({
          costo: {
            arancel_pct_por_pata: 0.75,
            spread_origen_pct: 1.2,
            spread_destino_pct: 0.8,
            total_pct: 2.5,
            verificable: true,
            elevado: false,
            payback_meses: 16.7,
          },
        }),
      ]),
    })
    renderizar()

    const fila = await screen.findByRole('listitem')
    expect(fila).toHaveTextContent(/Costo de rotar 2,50%/)
    expect(fila).toHaveTextContent(/lo paga en 16,7 meses/)
  })
})
