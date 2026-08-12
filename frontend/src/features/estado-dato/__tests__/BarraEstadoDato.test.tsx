/**
 * Los cuatro GWT de F-013 vistos desde la pantalla.
 *
 * El que más importa es el segundo: **la barra declara la hora del snapshot y la demora, nunca la
 * hora actual como si fuera el dato**. Es un error que no se ve mirando la pantalla, porque el
 * número siempre parece razonable, así que el test es lo único que lo agarra.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { BarraEstadoDato } from '../components/BarraEstadoDato'
import type { Alerta, Descarte, EstadoDelDato } from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

/** 11:00 del 7 de agosto de 2026, hora local. Es el snapshot del GWT-2. */
const CAPTURADO = new Date(2026, 7, 7, 11, 0).toISOString()
const VALIDO_HASTA = new Date(2026, 7, 7, 10, 40).toISOString()

function alerta(extra: Partial<Alerta> = {}): Alerta {
  return {
    codigo: 'cobertura_del_calendario',
    mensaje: 'El calendario cubre 70 de 431 emisiones del universo (16%).',
    severidad: 'advertencia',
    accion_requerida: null,
    detalle: {},
    origen: 'estado',
    ...extra,
  }
}

function descarte(extra: Partial<Descarte> = {}): Descarte {
  return {
    ticker: 'VSCQD',
    motivo: 'especie_incoherente',
    rendimiento: 346_279.17,
    segmento: 'usd_hard',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    umbral: 1.0,
    ticker_referencia: 'VSCQO',
    rendimiento_referencia: 0.0675,
    ...extra,
  }
}

function estado(extra: Partial<EstadoDelDato> = {}): EstadoDelDato {
  return {
    consultado_en: new Date(2026, 7, 7, 11, 15).toISOString(),
    dato: {
      capturado_en: CAPTURADO,
      dato_valido_hasta: VALIDO_HASTA,
      antiguedad_minutos: 15,
      demora: {
        minutos: 20,
        fuente: 'BYMA (API abierta)',
        por_que: 'La API abierta de BYMA publica con retraso declarado respecto del mercado.',
      },
    },
    corrida: null,
    fuentes: {
      credenciales_vencidas: [],
      caidas: [],
      hay_credencial_vencida: false,
      hay_fuente_caida: false,
      requiere_intervencion: false,
    },
    universo: {
      leidos: 2894,
      renta_variable: 1417,
      sin_segmento: 535,
      evaluados: 942,
      con_rendimiento: 217,
      descartados: 0,
      operables: 217,
      emisiones: 431,
    },
    descartes: { total: 0, items: [], truncado: false },
    cobertura: [
      {
        campo: 'tna',
        rotulo: 'TNA',
        por_que: 'Es el rendimiento del segmento de tasa fija.',
        presentes: 0,
        total: 2894,
        faltantes: 2894,
        porcentaje: 0,
      },
    ],
    tipo_de_cambio: { valor: 1521.53, disponible: true, pares: 216 },
    calendario: {
      emisiones: 431,
      con_calendario: 70,
      sin_paridad: 360,
      sin_cronograma: 0,
      vencidos: 1,
    },
    alertas: [alerta()],
    resumen: {
      alertas: 1,
      por_severidad: { error: 0, advertencia: 1, info: 0 },
      peor_severidad: 'advertencia',
      requiere_intervencion: false,
    },
    costo: {
      desde_cache: false,
      analisis_calculado_en: new Date(2026, 7, 7, 11, 15).toISOString(),
      analisis_duracion_ms: 662,
    },
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

function renderizar() {
  const cliente = crearQueryClient()
  cliente.setDefaultOptions({ queries: { retry: false } })
  return render(
    <QueryClientProvider client={cliente}>
      <BarraEstadoDato />
    </QueryClientProvider>,
  )
}

/**
 * La franja ya cargada.
 *
 * No alcanza con `findByRole('status')`: el estado de carga usa el mismo rol —a propósito, porque
 * la franja nunca desaparece— así que resuelve al instante contra el "consultando…". Lo que marca
 * que llegó la respuesta es el botón de detalle, que sólo existe con datos.
 */
async function franjaCargada() {
  await screen.findByRole('button', { name: /ver detalle/ })
  return screen.getByRole('status')
}

// --- GWT-1: la barra está visible sin navegar a ninguna parte ------------------------------------

describe('la franja', () => {
  it('se dibuja apenas monta, antes de que llegue la respuesta', () => {
    responderCon(estado())
    renderizar()

    expect(screen.getByRole('status')).toHaveTextContent('consultando el estado del dato')
  })

  it('sigue visible y lo dice cuando el backend no contesta', async () => {
    // Es el punto de la feature: una barra que desaparece deja seis pantallas mostrando números
    // sin ninguna declaración sobre ellos.
    responderCon({ error: { code: 'internal_error', message: 'roto' } }, 500)
    renderizar()

    expect(await screen.findByText(/No se pudo leer el estado del dato/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'reintentar' })).toBeInTheDocument()
  })
})

// --- GWT-2: la hora del snapshot y la demora, nunca la hora actual --------------------------------

describe('la hora del dato', () => {
  it('declara la hora del snapshot y no la del reloj', async () => {
    responderCon(estado())
    renderizar()

    const franja = await franjaCargada()
    expect(franja).toHaveTextContent('dato de 07/08/2026, 11:00')
    expect(franja).not.toHaveTextContent('11:15')
  })

  it('declara la demora de la fuente y hasta qué momento del mercado llega el dato', async () => {
    responderCon(estado())
    renderizar()

    const franja = await franjaCargada()
    expect(franja).toHaveTextContent('refleja el mercado hasta 07/08/2026, 10:40')
    expect(franja).toHaveTextContent('BYMA (API abierta) declara 20 min de demora')
  })

  it('informa la edad del dato sin juzgarla', async () => {
    // No hay umbral de "dato viejo": fijarlo sería decidir cuánta desactualización es aceptable
    // para operar, que no lo decide la interfaz.
    responderCon(estado())
    renderizar()

    expect(await screen.findByText(/hace 15 min/)).toBeInTheDocument()
  })

  it('sin snapshot lo dice en vez de mostrar una hora vacía', async () => {
    responderCon(
      estado({
        dato: {
          capturado_en: null,
          dato_valido_hasta: null,
          antiguedad_minutos: null,
          demora: { minutos: 20, fuente: 'BYMA (API abierta)', por_que: 'x' },
        },
      }),
    )
    renderizar()

    expect(await screen.findByText(/sin dato de mercado/)).toBeInTheDocument()
  })
})

// --- GWT-3: el detalle de los descartes, con motivo y valor ---------------------------------------

describe('el detalle desplegable', () => {
  it('empieza cerrado y se abre al pedirlo', async () => {
    responderCon(estado())
    renderizar()

    const boton = await screen.findByRole('button', { name: /ver detalle/ })
    expect(boton).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(boton)

    expect(screen.getByRole('button', { name: /ocultar detalle/ })).toHaveAttribute(
      'aria-expanded',
      'true',
    )
  })

  it('muestra cada descarte con su motivo y el valor que lo disparó', async () => {
    responderCon(
      estado({
        descartes: { total: 1, items: [descarte()], truncado: false },
        universo: { ...estado().universo, descartados: 1 },
      }),
    )
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText('VSCQD')).toBeInTheDocument()
    // El valor que lo disparó, con la unidad de su segmento al lado: 4,8 es un descarte en CER y
    // un instrumento sano en tasa fija.
    expect(screen.getByText('34.627.917,00%')).toBeInTheDocument()
    expect(screen.getByText(/TIR en dólares/)).toBeInTheDocument()
    expect(screen.getByText(/su hermana.*VSCQO.*6,75%/)).toBeInTheDocument()
  })

  it('explica el cero de descartes en vez de dejarlo pasar como dato sano', async () => {
    // Es lo que pasa contra la base real: la sanidad descarta cero porque 535 especies de renta
    // fija no tienen tipo de tasa y no pasan por ninguna de las dos capas.
    responderCon(estado())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText(/535 especies de renta fija no tienen/)).toBeInTheDocument()
  })

  it('muestra la cobertura de cada campo con el porqué al lado', async () => {
    responderCon(estado())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText('TNA')).toBeInTheDocument()
    expect(screen.getByText('0/2.894 · 0,0%')).toBeInTheDocument()
    expect(screen.getByText('Es el rendimiento del segmento de tasa fija.')).toBeInTheDocument()
  })

  it('avisa cuando no hay ninguna corrida registrada', async () => {
    responderCon(estado())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText(/No hay ninguna corrida registrada/)).toBeInTheDocument()
  })
})

// --- GWT-4: token vencido distinguido de API caída ------------------------------------------------

describe('token vencido contra API caída', () => {
  const vencida = alerta({
    codigo: 'credencial_vencida',
    mensaje: 'La credencial de Docta no es válida.',
    severidad: 'error',
    accion_requerida: 'Regenerar el link firmado desde el panel de Docta.',
    origen: 'ingesta',
  })
  const caida = alerta({
    codigo: 'fuente_no_disponible',
    mensaje: 'BYMA no está disponible: timeout tras 5 intentos.',
    severidad: 'error',
    accion_requerida: null,
    origen: 'ingesta',
  })

  function conLasDos() {
    return estado({
      alertas: [vencida, caida],
      fuentes: {
        credenciales_vencidas: [vencida],
        caidas: [caida],
        hay_credencial_vencida: true,
        hay_fuente_caida: true,
        requiere_intervencion: true,
      },
      resumen: {
        alertas: 2,
        por_severidad: { error: 2, advertencia: 0, info: 0 },
        peor_severidad: 'error',
        requiere_intervencion: true,
      },
    })
  }

  it('avisa en la franja que algo requiere acción', async () => {
    responderCon(conLasDos())
    renderizar()

    const franja = await franjaCargada()
    expect(franja).toHaveTextContent('2 errores')
    expect(franja).toHaveTextContent('requiere acción')
  })

  it('separa la que se arregla a mano de la que se arregla esperando', async () => {
    responderCon(conLasDos())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    const accionables = screen.getByRole('heading', {
      name: 'Requieren que alguien haga algo',
    }).parentElement
    const solas = screen.getByRole('heading', {
      name: /Se resuelven solas/,
    }).parentElement

    expect(accionables).toHaveTextContent('La credencial de Docta no es válida.')
    expect(accionables).toHaveTextContent('Regenerar el link firmado desde el panel de Docta.')
    expect(accionables).not.toHaveTextContent('BYMA no está disponible')

    expect(solas).toHaveTextContent('BYMA no está disponible')
    expect(solas).not.toHaveTextContent('La credencial de Docta')
  })

  it('no reescribe el mensaje del backend', async () => {
    // La alerta ya está redactada para que se sepa qué hacer. Una segunda redacción haría que el
    // mismo hecho se cuente de dos formas distintas según por dónde se lo mire.
    responderCon(conLasDos())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText(vencida.mensaje)).toBeInTheDocument()
    expect(screen.getByText(caida.mensaje)).toBeInTheDocument()
  })
})

// --- El hallazgo que hoy no expone ninguna pantalla ------------------------------------------------

describe('la cobertura del calendario', () => {
  it('se ve en la franja sin desplegar nada', async () => {
    // 70 de 431. Es el número que más cambia lo que alguien cree estar viendo: sin este rótulo, la
    // grilla de doce meses se lee como si mostrara el universo entero.
    responderCon(estado())
    renderizar()

    expect(await franjaCargada()).toHaveTextContent('calendario 70/431')
  })

  it('trae su alerta completa en el detalle', async () => {
    responderCon(estado())
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText(/El calendario cubre 70 de 431 emisiones/)).toBeInTheDocument()
  })
})

// --- Una sola consulta para las seis pantallas -----------------------------------------------------

describe('el costo del lado del cliente', () => {
  it('pide el estado una sola vez aunque se abra y se cierre el detalle', async () => {
    const fetchMock = responderCon(estado())
    renderizar()

    const boton = await screen.findByRole('button', { name: /ver detalle/ })
    await userEvent.click(boton)
    await userEvent.click(screen.getByRole('button', { name: /ocultar detalle/ }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
  })

  it('declara cuando el análisis salió del caché del backend', async () => {
    responderCon(
      estado({
        costo: {
          desde_cache: true,
          analisis_calculado_en: new Date(2026, 7, 7, 11, 2).toISOString(),
          analisis_duracion_ms: 662,
        },
      }),
    )
    renderizar()

    await userEvent.click(await screen.findByRole('button', { name: /ver detalle/ }))

    expect(screen.getByText(/en caché desde 07\/08\/2026, 11:02/)).toBeInTheDocument()
  })
})
