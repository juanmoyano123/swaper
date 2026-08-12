/**
 * Los GWT de F-017 (filtros de la grilla, A7), vistos desde `ArmadorPage` entera — mismo patrón de
 * `CarteraEditable.test.tsx`: mock de `fetch` ruteado por URL, sin montar el backend.
 *
 * La ventana es la misma de `ArmadorPage.test.tsx`: doce meses desde el "hoy" 07/08/2026
 * (septiembre de 2026 a agosto de 2027). Dos papeles: AL30 (usd_hard/tir_usd, ley ARG, sector
 * Soberano, duración 3.2, volumen_usd alto) paga en Noviembre, Marzo y Julio; TZX26
 * (cer/tasa_real_cer, ley null — "sin dato", sector Financiera, duración 1.0, volumen_usd bajo)
 * paga sólo en Octubre.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { ArmadorPage } from '../ArmadorPage'
import type { Especie, InstrumentoDelMes, MesDelCalendario } from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

const MESES_ES = [
  'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
  'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

/** (año, mes) de los doce meses de la ventana: septiembre de 2026 a agosto de 2027. */
const VENTANA: Array<[number, number]> = [
  [2026, 9], [2026, 10], [2026, 11], [2026, 12],
  [2027, 1], [2027, 2], [2027, 3], [2027, 4],
  [2027, 5], [2027, 6], [2027, 7], [2027, 8],
]

function al30(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    fechas: ['2026-11-09'],
    pct_renta: 0.0075,
    pct_amortizacion: 0,
    renta: null,
    amortizacion: null,
    moneda: 'USD',
    rendimiento: 0.1123,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    vencimiento: '2030-07-09',
    ...extra,
  }
}

function tzx26(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'TZX26',
    emision: 'TZX26',
    fechas: ['2026-10-15'],
    pct_renta: 0.005,
    pct_amortizacion: 0,
    renta: null,
    amortizacion: null,
    moneda: 'ARS',
    rendimiento: 0.06,
    naturaleza: 'tasa_real_cer',
    naturaleza_nombre: 'Tasa real sobre CER',
    vencimiento: '2026-12-20',
    ...extra,
  }
}

function mes(indice: number, instrumentos: InstrumentoDelMes[] = []): MesDelCalendario {
  const [anio, numeroMes] = VENTANA[indice]
  const conRenta = instrumentos.filter((i) => i.pct_renta > 0).length
  return {
    anio,
    mes: numeroMes,
    etiqueta: `${String(numeroMes).padStart(2, '0')}/${anio}`,
    nombre: `${MESES_ES[numeroMes - 1]} ${anio}`,
    con_renta: conRenta,
    con_amortizacion: 0,
    sin_renta: conRenta === 0,
    renta: null,
    amortizacion: null,
    instrumentos,
  }
}

function meses(): MesDelCalendario[] {
  const ventana = VENTANA.map((_, indice) => mes(indice))
  ventana[1] = mes(1, [tzx26()]) // Octubre 2026
  ventana[2] = mes(2, [al30()]) // Noviembre 2026
  ventana[6] = mes(6, [al30({ fechas: ['2027-03-09'] })]) // Marzo 2027
  ventana[10] = mes(10, [al30({ fechas: ['2027-07-09'] })]) // Julio 2027
  return ventana
}

function calendarioUniverso() {
  return {
    resumen: {
      hoy: '2026-08-07',
      desde: '09/2026',
      hasta: '08/2027',
      con_montos: false,
      monedas: [],
      instrumentos: 2,
      meses_sin_renta: [],
      renta_anual: null,
      amortizacion_anual: null,
      pendientes_este_mes: 0,
      flujos: {
        evaluados: 2, con_flujos: 2, pagos: 4, sin_cronograma: 0,
        sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0,
      },
    },
    meses: meses(),
    alertas: [],
  }
}

function especieAl30(): Especie {
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
    sector: 'Soberano',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
  }
}

function especieTzx26(): Especie {
  return {
    ticker: 'TZX26',
    emision: 'TZX26',
    sufijo_liquidacion: null,
    clase_activo: 'Letra',
    segmento: 'cer',
    naturaleza: 'tasa_real_cer',
    naturaleza_nombre: 'Tasa real sobre CER',
    rendimiento: 0.06,
    duracion: 1.0,
    vencimiento: '2026-12-20',
    ley: null, // GWT-4: sin dato de ley
    moneda_cupon: 'ARS',
    emisor: null,
    precio: 98,
    moneda_cotizacion: 'ARS',
    volumen: 10_000_000,
    volumen_usd: 10_000,
    paridad: null,
    lamina: null,
    sector: 'Financiera',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
  }
}

function responderCon({
  especiesStatus = 200,
}: {
  especiesStatus?: number
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    if (url.includes('/emisiones/especies')) {
      if (especiesStatus !== 200) {
        return Promise.resolve(
          new Response(JSON.stringify({ error: { code: 'internal_error', message: 'falló' } }), {
            status: especiesStatus,
          }),
        )
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({ items: [especieAl30(), especieTzx26()], next_cursor: null }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
    }
    if (url.includes('/calendario/universo')) {
      return Promise.resolve(
        new Response(JSON.stringify(calendarioUniverso()), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    }
    throw new Error(`fetch no mockeado en este test: ${url}`)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      {/* F-026 monta `BloqueRentaVariable` dentro de `ArmadorPage`, y ese componente abre la
          ficha del instrumento con `useAbrirInstrumento` (`useNavigate`): sin Router acá, montar
          la página entera revienta aunque este archivo no toque nada de renta variable. */}
      <MemoryRouter>
        <ArmadorPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Espera a que el calendario Y el universo hayan terminado de cargar — no sólo el calendario, que
 *  llega antes: hacer clic o leer selects antes de que el universo resuelva encuentra la barra
 *  todavía en su estado `deshabilitado` (opciones vacías). */
async function grillaCargada() {
  await screen.findByRole('button', { name: /Noviembre 2026/ })
  await waitFor(() => {
    expect(screen.queryByText('cargando el universo para poder filtrar')).not.toBeInTheDocument()
  })
}

/** Grilla cargada y con el default de fábrica (TIR ≥ 6% + cupones) ya sacado — el punto de
 *  partida de los GWT de F-017, que se enfocan en segmento/duración/liquidez/sector/ley, no en el
 *  default nuevo (probado aparte, ver "default de fábrica"). */
async function grillaSinFiltroDeFabrica() {
  await grillaCargada()
  await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))
  await screen.findByText('2 de 2 papeles pasan los filtros')
}

// --- GWT-1: sin segmento, unidad declarada por renglón -----------------------------------------------

describe('GWT-1: sin filtro de segmento', () => {
  it('la barra dice "unidad declarada por renglón" y cada renglón muestra su propia unidad', async () => {
    responderCon()
    renderizar()
    await grillaSinFiltroDeFabrica()

    expect(screen.getByText('unidad declarada por renglón')).toBeInTheDocument()

    // AL30 paga en tres meses de la ventana: tres renglones, todos con la misma unidad.
    const renglonAl30 = screen.getAllByRole('button', { name: /^AL30/ })[0]
    expect(renglonAl30).toHaveTextContent('TIR USD')

    const renglonTzx26 = screen.getByRole('button', { name: /^TZX26/ })
    expect(renglonTzx26).toHaveTextContent('Tasa real CER')
  })
})

// --- GWT-2: segmento CER, tasa real declarada en el encabezado ----------------------------------------

describe('GWT-2: filtro de segmento en CER', () => {
  it('deja sólo papeles CER y declara la unidad en el encabezado de la barra', async () => {
    responderCon()
    renderizar()
    await grillaSinFiltroDeFabrica()

    await userEvent.click(screen.getByRole('button', { name: 'CER' }))

    expect(screen.getByText('unidad: Tasa real CER')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^TZX26/ })).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /^AL30/ })).toHaveLength(0)
  })
})

// --- GWT-3: filtros simultáneos, conteo visible, limpiar los saca a todos de una vez -------------------

describe('GWT-3: duración, liquidez y sector aplicados simultáneamente', () => {
  it('muestra el conteo correcto con los tres activos y vuelve a "M de M" al limpiar', async () => {
    responderCon()
    renderizar()
    await grillaSinFiltroDeFabrica()

    expect(screen.getByText('2 de 2 papeles pasan los filtros')).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/Duración máx/), '5')
    await userEvent.selectOptions(screen.getByLabelText(/Liquidez mín/), '≥ p50')
    await userEvent.selectOptions(screen.getByLabelText('Sector'), 'Soberano')

    // AL30 (duración 3,2, percentil 100, sector Soberano) pasa los tres; TZX26 (sector Financiera)
    // queda afuera del filtro de sector.
    expect(await screen.findByText('1 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^AL30/ }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^TZX26/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('2 de 2 papeles pasan los filtros')).toBeInTheDocument()
  })
})

// --- GWT-4: ley null agrupa aparte, nunca bajo una ley concreta ----------------------------------------

describe('GWT-4: filtro por ley', () => {
  it('agrupa el instrumento sin ley como "ley no informada", nunca bajo una ley concreta', async () => {
    responderCon()
    renderizar()
    await grillaSinFiltroDeFabrica()

    await userEvent.selectOptions(screen.getByLabelText('Ley'), 'ARG')
    expect(screen.queryByRole('button', { name: /^TZX26/ })).not.toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Ley'), 'ley no informada')
    expect(screen.getByRole('button', { name: /^TZX26/ })).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /^AL30/ })).toHaveLength(0)
  })
})

// --- Default de fábrica: TIR ≥ 6% y "sólo con cupones" activos al montar -------------------------------

describe('default de fábrica', () => {
  it('arranca con TIR mín. en 6 y "sólo con cupones" marcado, dejando sólo AL30 (TIR USD 11,23%)', async () => {
    responderCon()
    renderizar()
    await grillaCargada()

    expect(screen.getByLabelText(/TIR mín/)).toHaveValue(6)
    expect(screen.getByLabelText('Sólo con cupones')).toBeChecked()

    // TZX26 es tasa real CER, sin TIR: el default la deja afuera.
    expect(screen.getByText('1 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^AL30/ }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^TZX26/ })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('2 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^TZX26/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/TIR mín/)).toHaveValue(null)
    expect(screen.getByLabelText('Sólo con cupones')).not.toBeChecked()
  })
})

// --- Cero explicado: no se dibujan doce columnas vacías --------------------------------------------

describe('cero sobrevivientes', () => {
  it('muestra el mensaje con el conteo y no dibuja la grilla de doce columnas', async () => {
    responderCon()
    renderizar()
    await grillaCargada()

    // Ninguno de los dos papeles del fixture tiene ley "NY".
    await userEvent.type(screen.getByLabelText(/Duración máx/), '0.1')

    expect(
      await screen.findByText(/Ningún papel de la ventana pasa los filtros activos \(0 de 2\)\./),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Noviembre 2026/ })).not.toBeInTheDocument()
  })
})

// --- Etapa 5 del rediseño del armador: filtro de calificación, literal y sin ordenar ------------------

describe('filtro de calificación', () => {
  function responderConCalificaciones() {
    const fetchMock = vi.fn((entrada: RequestInfo | URL) => {
      const url = typeof entrada === 'string' ? entrada : entrada.toString()
      if (url.includes('/emisiones/especies')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                { ...especieAl30(), calificacion: 'AAA(arg) (FIX)' },
                especieTzx26(), // calificacion: null, del fixture base
              ],
              next_cursor: null,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
        )
      }
      if (url.includes('/calendario/universo')) {
        return Promise.resolve(
          new Response(JSON.stringify(calendarioUniverso()), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }
      throw new Error(`fetch no mockeado en este test: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
  }

  it('la tarjeta muestra la calificación, incluida "sin calif." cuando falta', async () => {
    responderConCalificaciones()
    renderizar()
    await grillaSinFiltroDeFabrica()

    expect(screen.getAllByRole('button', { name: /^AL30/ })[0]).toHaveTextContent('AAA(arg) (FIX)')
    expect(screen.getByRole('button', { name: /^TZX26/ })).toHaveTextContent('sin calif.')
  })

  it('deja sólo el papel con la calificación elegida', async () => {
    responderConCalificaciones()
    renderizar()
    await grillaSinFiltroDeFabrica()

    await userEvent.click(screen.getByText('todas'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'AAA(arg) (FIX)' }))

    expect(await screen.findByText('1 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^AL30/ }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('button', { name: /^TZX26/ })).not.toBeInTheDocument()
  })

  it('"sin calificación" deja sólo los que no la tienen informada, nunca los que sí', async () => {
    responderConCalificaciones()
    renderizar()
    await grillaSinFiltroDeFabrica()

    await userEvent.click(screen.getByText('todas'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'sin calificación' }))

    expect(await screen.findByText('1 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^TZX26/ })).toBeInTheDocument()
    expect(screen.queryAllByRole('button', { name: /^AL30/ })).toHaveLength(0)
  })

  it('limpiar filtros también vacía la selección de calificación', async () => {
    responderConCalificaciones()
    renderizar()
    await grillaSinFiltroDeFabrica()

    await userEvent.click(screen.getByText('todas'))
    await userEvent.click(screen.getByRole('checkbox', { name: 'AAA(arg) (FIX)' }))
    await screen.findByText('1 de 2 papeles pasan los filtros')

    await userEvent.click(screen.getByRole('button', { name: 'limpiar filtros' }))

    expect(await screen.findByText('2 de 2 papeles pasan los filtros')).toBeInTheDocument()
    expect(screen.getByText('todas')).toBeInTheDocument()
  })
})

// --- Universo caído: la grilla se muestra sin filtrar, la barra se declara no disponible --------------

describe('universo caído', () => {
  it('la grilla se muestra sin filtrar y la barra declara que los filtros no están disponibles', async () => {
    responderCon({ especiesStatus: 500 })
    renderizar()

    // Sin el universo, la grilla igual se dibuja con los meses tal cual llegaron.
    expect(await screen.findByRole('button', { name: /Noviembre 2026/ })).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^AL30/ }).length).toBeGreaterThan(0)
    expect(screen.getByRole('button', { name: /^TZX26/ })).toBeInTheDocument()

    expect(await screen.findByText('el universo no cargó: filtros no disponibles')).toBeInTheDocument()
    expect(screen.getByLabelText(/Duración máx/)).toBeDisabled()
  })
})
