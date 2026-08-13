/**
 * Los cuatro GWT de F-016 vistos desde la pantalla, más las alertas y el contrato.
 *
 * El fixture arma una ventana de doce meses a partir del "hoy" del 07/08/2026 del enunciado de
 * F-013 (septiembre de 2026 a agosto de 2027, arrancando el mes que viene — ver
 * `backend/app/calendario/grilla.py`), con un papel (AL30) que paga en Noviembre, Marzo y Julio —
 * "marzo, julio y noviembre" del GWT-1 — y Febrero de 2027 sin ningún pago en el universo, que es
 * el mes del GWT-3.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { ArmadorPage } from '../ArmadorPage'
import type { InstrumentoDelMes, MesDelCalendario } from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

const MESES_ES = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
]

/** (año, mes) de los doce meses de la ventana: septiembre de 2026 a agosto de 2027. */
const VENTANA: Array<[number, number]> = [
  [2026, 9],
  [2026, 10],
  [2026, 11],
  [2026, 12],
  [2027, 1],
  [2027, 2],
  [2027, 3],
  [2027, 4],
  [2027, 5],
  [2027, 6],
  [2027, 7],
  [2027, 8],
]

function instrumento(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
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

/** El TX26 del GWT-4 (rendimiento `null` → `s/d`) y del GWT-3 (paga en un mes que AL30 no cubre). */
const TX26 = instrumento({
  ticker: 'TX26',
  emision: 'TX26',
  fechas: ['2026-10-15'],
  pct_renta: 0.02,
  moneda: 'ARS',
  rendimiento: null,
  naturaleza: 'tna_nominal_ars',
  naturaleza_nombre: 'TNA nominal en pesos',
  vencimiento: '2028-01-01',
})

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
  ventana[1] = mes(1, [TX26]) // Octubre 2026: paga, pero no lo tiene la cartera armada
  ventana[2] = mes(2, [instrumento()]) // Noviembre 2026
  ventana[6] = mes(6, [instrumento({ fechas: ['2027-03-09'] })]) // Marzo 2027
  ventana[10] = mes(10, [instrumento({ fechas: ['2027-07-09'] })]) // Julio 2027
  // ventana[5] (Febrero 2027) queda sin instrumentos: es el mes sin_renta del GWT-3.
  return ventana
}

function respuesta() {
  return {
    resumen: {
      hoy: '2026-08-07',
      desde: '09/2026',
      hasta: '08/2027',
      con_montos: false,
      monedas: [],
      instrumentos: 2,
      meses_sin_renta: ['02/2027'],
      renta_anual: null,
      amortizacion_anual: null,
      pendientes_este_mes: 0,
      flujos: {
        evaluados: 431,
        con_flujos: 70,
        pagos: 140,
        sin_cronograma: 0,
        sin_paridad: 360,
        sin_paridad_que_cotizan: 0,
        vencidos: 1,
      },
    },
    meses: meses(),
    alertas: [
      {
        codigo: 'cobertura_del_calendario',
        mensaje: 'El calendario cubre 70 de 431 emisiones del universo (16%).',
        severidad: 'advertencia',
        accion_requerida: null,
        detalle: {},
      },
    ],
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

/** La grilla ya cargada: el mes de Noviembre 2026 es el primero que trae instrumentos. */
async function grillaCargada() {
  return screen.findByRole('button', { name: /Noviembre 2026/ })
}

// --- GWT-1/GWT-2: la iluminación multi-mes ---------------------------------------------------------

describe('seleccionar un papel', () => {
  it('lo ilumina en los tres meses en que paga a la vez, y lo apaga en los tres al volver a hacer clic', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    const renglonesAL30 = screen.getAllByRole('button', { name: /^AL30/ })
    expect(renglonesAL30).toHaveLength(3) // Noviembre, Marzo y Julio

    await userEvent.click(renglonesAL30[0])
    for (const renglon of screen.getAllByRole('button', { name: /^AL30/ })) {
      expect(renglon).toHaveAttribute('aria-pressed', 'true')
    }

    // El segundo clic llega desde otro de los tres meses: sigue siendo el mismo papel.
    await userEvent.click(screen.getAllByRole('button', { name: /^AL30/ })[2])
    for (const renglon of screen.getAllByRole('button', { name: /^AL30/ })) {
      expect(renglon).toHaveAttribute('aria-pressed', 'false')
    }
  })
})

// --- GWT-3: la cobertura de la selección, distinta de "nadie paga este mes" ------------------------

describe('la cobertura de la cartera seleccionada', () => {
  it('distingue el mes sin cobertura de la selección del mes sin pagos en todo el universo', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    // Sin seleccionar nada todavía: Febrero ya se distingue en su propia columna.
    const columnaFebrero = screen.getByRole('button', { name: /Febrero 2027/ })
    expect(within(columnaFebrero).getByText('sin pagos en el universo')).toBeInTheDocument()

    // Se arma la cartera con AL30 (paga en Noviembre, Marzo y Julio; no en Octubre).
    await userEvent.click(screen.getAllByRole('button', { name: /^AL30/ })[0])

    // Octubre paga (TX26), pero la cartera armada no lo cubre: sin cobertura, en rojo.
    expect(screen.getByLabelText('cobertura de Octubre 2026: sin_cobertura')).toHaveTextContent('—')
    // Noviembre sí lo cubre AL30.
    expect(screen.getByLabelText('cobertura de Noviembre 2026: cubierto')).toHaveTextContent('✓')
    // Febrero no es "la cartera no lo cubre": es que nadie en el universo paga ahí.
    expect(screen.getByLabelText('cobertura de Febrero 2027: sin_renta')).toHaveTextContent('·')
  })
})

// --- GWT-4: la tarjeta de un papel --------------------------------------------------------------------

describe('la tarjeta de un papel', () => {
  it('muestra ticker, cupón, rendimiento rotulado y año de vencimiento', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    // Sin moneda ni badge de tipo de liquidación: no hay un dato real que los declare (regla 11).
    const renglon = screen.getAllByRole('button', { name: /^AL30/ })[0]
    expect(renglon).toHaveTextContent('AL30')
    expect(renglon).toHaveTextContent('0,75%')
    expect(renglon).toHaveTextContent('11,23% TIR USD')
    expect(renglon).toHaveTextContent('2030')
  })

  it('con rendimiento null muestra s/d en vez de omitir la tarjeta', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    expect(screen.getByRole('button', { name: /^TX26/ })).toHaveTextContent('s/d')
  })
})

// --- Alertas: tal cual, sin filtrar -------------------------------------------------------------------

describe('las alertas del calendario', () => {
  it('muestra el mensaje completo de la alerta de advertencia del fixture', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    expect(
      screen.getByText('El calendario cubre 70 de 431 emisiones del universo (16%).'),
    ).toBeInTheDocument()
  })
})

// --- El contrato: un campo faltante falla fuerte, no dibuja una grilla a medias ------------------------

describe('el contrato de la respuesta', () => {
  it('un fixture completo pasa el esquema y la grilla se dibuja', async () => {
    responderCon(respuesta())
    renderizar()

    expect(await grillaCargada()).toBeInTheDocument()
  })

  it('un campo faltante en el contrato lo hace fallar con contract_mismatch', async () => {
    const buena = respuesta()
    const resumenSinHoy = Object.fromEntries(
      Object.entries(buena.resumen).filter(([clave]) => clave !== 'hoy'),
    )
    responderCon({ ...buena, resumen: resumenSinHoy })
    renderizar()

    expect(await screen.findByText(/contract_mismatch/)).toBeInTheDocument()
  })
})

// --- Etapa 2 del rediseño: secciones plegables ---------------------------------------------------

describe('plegar una sección', () => {
  it('oculta su contenido y muestra el resumen en su lugar', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    const boton = screen.getByRole('button', { name: /^Cordillera/ })
    expect(boton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getAllByRole('button', { name: /^AL30/ }).length).toBeGreaterThan(0)

    await userEvent.click(boton)

    expect(boton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: /^AL30/ })).not.toBeInTheDocument()
    expect(screen.getByText('sin papeles elegidos todavía')).toBeInTheDocument()
  })

  it('el resumen de Cartera cuenta las posiciones elegidas', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()
    await userEvent.click(screen.getAllByRole('button', { name: /^AL30/ })[0])

    await userEvent.click(screen.getByRole('button', { name: /^Cartera\b/ }))

    expect(screen.getByText(/1 posición · Σ/)).toBeInTheDocument()
  })

  it('persiste al volver a montar la página, como un refresh', async () => {
    responderCon(respuesta())
    const { unmount } = renderizar()
    await grillaCargada()

    await userEvent.click(screen.getByRole('button', { name: /^Cordillera/ }))
    expect(screen.queryByRole('button', { name: /^AL30/ })).not.toBeInTheDocument()

    unmount()
    renderizar()
    await screen.findByText('sin papeles elegidos todavía')

    expect(screen.queryByRole('button', { name: /^AL30/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Cordillera/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })
})


describe('ordenar las secciones', () => {
  /** Los rótulos de las secciones en el orden en que están en el DOM.
   *
   *  Se leen de los `<section>` que monta `SeccionDeArmador`, y no de los botones filtrados por
   *  `expanded`: ese filtro lanza cuando ninguna sección está en el estado buscado, que es
   *  exactamente lo que pasa al remontar con todo plegado. */
  function ordenEnPantalla(): string[] {
    return [...document.querySelectorAll('section')]
      .map((s) => ROTULOS_DE_SECCION.find((r) => s.textContent?.trimStart().startsWith(r)))
      .filter((r): r is string => r !== undefined)
  }

  it('arranca en el orden de fábrica, con renta variable última', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    expect(ordenEnPantalla()).toEqual(ROTULOS_DE_SECCION)
  })

  it('subir renta variable la mueve un lugar y la persiste al remontar', async () => {
    responderCon(respuesta())
    const { unmount } = renderizar()
    await grillaCargada()

    await userEvent.click(screen.getByRole('button', { name: /Ordenar secciones/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Subir Renta variable' }))

    // De última pasa a anteúltima: queda antes de Análisis.
    expect(ordenEnPantalla().at(-2)).toBe('Renta variable')

    unmount()
    renderizar()
    await grillaCargada()
    expect(ordenEnPantalla().at(-2)).toBe('Renta variable')
  })

  it('restaurar el orden original la devuelve al final', async () => {
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    await userEvent.click(screen.getByRole('button', { name: /Ordenar secciones/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Subir Renta variable' }))
    await userEvent.click(screen.getByRole('button', { name: 'Restaurar orden original' }))

    expect(ordenEnPantalla()).toEqual(ROTULOS_DE_SECCION)
  })

  it('la sección conserva su color de identidad al moverse', async () => {
    // El acento viaja con la sección: si dependiera de la posición, mover Renta variable arriba le
    // cambiaría el color y el asesor perdería la referencia visual que venía usando.
    responderCon(respuesta())
    renderizar()
    await grillaCargada()

    const colorDe = (rotulo: string) =>
      screen
        .getByRole('button', { name: new RegExp(`^${rotulo}`) })
        .closest('section')
        ?.style.getPropertyValue('border-left-color')

    const antes = colorDe('Renta variable')
    await userEvent.click(screen.getByRole('button', { name: /Ordenar secciones/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Subir Renta variable' }))

    expect(colorDe('Renta variable')).toBe(antes)
  })
})

/** En el orden de fábrica, que es contra el que se comparan los movimientos. */
const ROTULOS_DE_SECCION = [
  'Cordillera',
  'Armador de cartera',
  'Cartera',
  'Calendario de pagos',
  'Análisis',
  'Renta variable',
]
