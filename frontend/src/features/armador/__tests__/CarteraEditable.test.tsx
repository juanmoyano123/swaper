/**
 * `CarteraEditable` vista desde la pantalla — F-018, patrón de
 * `features/estado-dato/__tests__/BarraEstadoDato.test.tsx` (mock de `fetch` por URL, sin montar
 * el backend). El motor puro se cubre aparte en `resolver.test.ts`; acá lo que importa es que la
 * cabecera y las filas muestren lo que el motor calculó, sin normalizar nada en silencio.
 *
 * No hay todavía forma de agregar un papel desde `CarteraEditable` sola —eso lo hacen
 * `RenglonPapel`/`DetalleMes`, que viven en la grilla de F-016—, así que el arnés expone las
 * mismas acciones del store que usaría el resto de la pantalla.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { CarteraEditable } from '../components/CarteraEditable'
import type { Especie } from '../lib/schema'
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
    periodicidad: 'semestral',
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
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

const GD30 = especie({ ticker: 'GD30', emision: 'GD30', precio: 100, emisor: 'República Argentina' })

function calendarioVacio() {
  return {
    resumen: {
      hoy: '2026-08-07',
      desde: '09/2026',
      hasta: '08/2027',
      con_montos: true,
      monedas: ['USD'],
      instrumentos: 2,
      meses_sin_renta: [],
      renta_anual: null,
      amortizacion_anual: null,
      pendientes_este_mes: 0,
      flujos: {
        evaluados: 2,
        con_flujos: 2,
        pagos: 2,
        sin_cronograma: 0,
        sin_paridad: 0,
        sin_paridad_que_cotizan: 0,
        vencidos: 0,
      },
    },
    meses: Array.from({ length: 12 }, (_, indice) => ({
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
    })),
    alertas: [],
  }
}

function fondoFci(extra: Record<string, unknown> = {}) {
  return {
    codigo_cafci: '1234',
    fondo: 'Fondo Ahorro Pesos',
    codigo_cnv: null,
    seccion: 'Renta Fija',
    tipo_renta: 'Renta Fija',
    naturaleza: 'variacion_cuotaparte',
    naturaleza_nombre: 'Variación de cuotaparte',
    moneda: 'ARS',
    region: null,
    horizonte: null,
    fecha_vcp: '2026-08-22',
    vcp: 15_000,
    vcp_anterior: null,
    var_diaria_pct: null,
    var_mes_pct: null,
    var_anio_pct: null,
    var_12m_pct: null,
    cuotapartes: null,
    cuotapartes_anterior: null,
    patrimonio: null,
    patrimonio_anterior: null,
    market_share: null,
    gerente: null,
    depositaria: null,
    calificacion: null,
    calificado: null,
    tipo_dinero: null,
    comision_ingreso: null,
    honorarios_adm_sg: null,
    honorarios_adm_sd: null,
    gastos_ord_gestion: null,
    comision_rescate: null,
    comision_transferencia: null,
    honorarios_exito: null,
    moneda_fondo: null,
    discrepancia_moneda: false,
    plazo_liq: null,
    dias_para_rescatar: null,
    minimo_inversion: null,
    advertencia_distribucion: '',
    ...extra,
  }
}

function responderCon({
  especies = [],
  tipoDeCambio = { valor: 1500, disponible: true },
  calendario = calendarioVacio(),
  lamina,
  acciones = [],
  fondosFci = [],
}: {
  especies?: Especie[]
  tipoDeCambio?: { valor: number | null; disponible: boolean }
  calendario?: unknown
  /** F-025: respuesta de `POST .../lamina`. Sin esto, ese endpoint no está mockeado — como los
   *  demás, tirar si un test lo golpea sin haberlo declarado. */
  lamina?: { status: number; cuerpo: unknown }
  /** Tanda 13: la tabla muestra también el bloque de renta variable, así que pide su universo. */
  acciones?: unknown[]
  /** F-046: los fondos que el picker de `SelectorFci` filtra en cliente. */
  fondosFci?: ReturnType<typeof fondoFci>[]
} = {}) {
  const fetchMock = vi.fn((entrada: RequestInfo | URL, _init?: RequestInit) => {
    const url = typeof entrada === 'string' ? entrada : entrada.toString()
    let cuerpo: unknown
    let status = 200
    if (url.includes('/emisiones/especies')) {
      cuerpo = { items: especies, next_cursor: null }
    } else if (url.includes('/tipo-de-cambio')) {
      cuerpo = { tipo_de_cambio: tipoDeCambio, alertas: [] }
    } else if (url.includes('/calendario/cartera')) {
      cuerpo = calendario
    } else if (url.includes('/renta-variable/especies')) {
      cuerpo = { items: url.includes('clase=accion') ? acciones : [], next_cursor: null }
    } else if (url.includes('/fci/fondos')) {
      cuerpo = { items: fondosFci, next_cursor: null }
    } else if (url.includes('/lamina')) {
      if (!lamina) throw new Error(`fetch no mockeado en este test: ${url}`)
      status = lamina.status
      cuerpo = lamina.cuerpo
    } else {
      throw new Error(`fetch no mockeado en este test: ${url}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(cuerpo), { status, headers: { 'Content-Type': 'application/json' } }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Expone las acciones del store que en la pantalla real dispara la grilla de F-016. */
function Arnes() {
  const { alternarPapel, agregarFci, fijarPeso, fijarMontoTotal, alternarRentaVariable } =
    useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarPapel('AL30')}>
        agregar AL30
      </button>
      <button type="button" onClick={() => alternarRentaVariable('GGAL')}>
        agregar GGAL
      </button>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        agregar GD30
      </button>
      <button type="button" onClick={() => agregarFci('FCI Ahorro', 20)}>
        agregar FCI
      </button>
      <button type="button" onClick={() => fijarPeso('AL30', 50)}>
        peso AL30 a 50
      </button>
      <button type="button" onClick={() => fijarPeso('GD30', 47.4)}>
        peso GD30 a 47,4
      </button>
      <button type="button" onClick={() => fijarMontoTotal(10_000)}>
        monto 10.000
      </button>
      <CarteraEditable />
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
  it('lo dice en vez de mostrar una tabla vacía', () => {
    responderCon()
    renderizar()

    expect(screen.getByText(/Sin posiciones/)).toBeInTheDocument()
  })
})

// --- GWT-2: la suma de pesos pedidos se muestra tal cual, sin normalizar --------------------------

describe('la cabecera', () => {
  it('marca la Σ de pesos pedidos en --ac2 cuando no suma 100, y no la normaliza', async () => {
    responderCon({ especies: [especie(), GD30] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso GD30 a 47,4' }))

    // Por el rótulo de la cabecera y no por el texto suelto: el subtotal del bloque de soberanos
    // muestra el mismo 97,40% cuando la cartera tiene un bloque solo.
    const cabecera = (await screen.findByText('Σ pedida total (incl. RV)')).closest('div')
    const suma = within(cabecera as HTMLElement).getByText('97,40%')
    expect(suma).toHaveStyle({ color: 'var(--ac2)' })
  })

  it('muestra el invertido como s/d hasta que haya monto total cargado', async () => {
    responderCon({ especies: [especie()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))

    // Sin monto total (0 por defecto) `resolver` no calcula nada: invertido queda sin dato.
    expect(await screen.findByText('AL30')).toBeInTheDocument()
    const filaInvertido = screen.getByText('Invertido').closest('div')
    expect(within(filaInvertido as HTMLElement).getByText('s/d')).toBeInTheDocument()
  })
})

// --- Fila con diferencia entre pedido y real, y GWT-4: fila de FCI ---------------------------------

describe('una fila resuelta', () => {
  it('marca la diferencia entre peso pedido y peso real cuando supera 0,6 pp', async () => {
    responderCon({ especies: [especie(), GD30] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso GD30 a 47,4' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    const fila = await screen.findByRole('row', { name: 'AL30' })
    // Σ pedido resoluble = 97,4: el real de AL30 se recalcula sobre ese total, no sobre 100
    // (50 / 97,4 * 100 = 51,33), y por eso difiere de 50 en más de 0,6 pp — se marca en --ac2.
    const pesoReal = within(fila).getByText('51,33%')
    expect(pesoReal).toHaveStyle({ color: 'var(--ac2)' })
  })
})

describe('una línea de FCI (GWT-4)', () => {
  it('suma al peso pedido pero todo lo demás queda en s/d', async () => {
    responderCon({ especies: [especie()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar FCI' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    await screen.findByRole('row', { name: 'AL30' })
    const filaFci = screen.getByRole('row', { name: 'FCI Ahorro' })

    // El peso pedido del FCI sigue viajando: es un input con ese valor.
    expect(within(filaFci).getByRole('spinbutton')).toHaveValue(20)
    // Todo lo demás —cuotapartes, invertido, peso real— se declara sin dato, nunca en blanco.
    expect(within(filaFci).getByText(/cuotapartes s\/d · invertido s\/d/)).toBeInTheDocument()
    expect(within(filaFci).getByText('s/d')).toBeInTheDocument()
    // Sin `codigoCafci` (agregado acá sin él, a propósito): es un FCI legado, declarado.
    expect(within(filaFci).getByText(/FCI sin identificar/)).toBeInTheDocument()
  })
})

describe('F-046: el picker de FCI reemplaza al texto libre', () => {
  it('buscar y elegir un fondo lo agrega con su codigoCafci, sin texto libre', async () => {
    responderCon({ fondosFci: [fondoFci({ codigo_cafci: '1234', fondo: 'Fondo Ahorro Pesos' })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Agregar FCI' }))
    await userEvent.type(screen.getByRole('textbox', { name: /buscar FCI/ }), 'ahorro')

    const opcion = await screen.findByRole('option', { name: /Fondo Ahorro Pesos/ })
    await userEvent.click(opcion)

    const fila = await screen.findByRole('row', { name: 'Fondo Ahorro Pesos' })
    // El picker desaparece después de elegir, y la fila queda identificada (sin la nota de "sin
    // identificar", a diferencia del GWT-4 de más arriba).
    expect(within(fila).queryByText(/FCI sin identificar/)).not.toBeInTheDocument()
    expect(screen.queryByRole('option')).not.toBeInTheDocument()
  })

  it('un fondo que no matchea ninguna búsqueda se declara, no se inventa un resultado', async () => {
    responderCon({ fondosFci: [fondoFci({ fondo: 'Fondo Ahorro Pesos' })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Agregar FCI' }))
    await userEvent.type(screen.getByRole('textbox', { name: /buscar FCI/ }), 'xyz-inexistente')

    expect(await screen.findByText(/Ningún fondo coincide/)).toBeInTheDocument()
  })

  it('re-identificar un FCI legado le pisa el codigoCafci sin tocar su peso', async () => {
    responderCon({ fondosFci: [fondoFci({ codigo_cafci: '5678', fondo: 'Fondo Ahorro Pesos' })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar FCI' })) // legado, sin código
    const filaFci = await screen.findByRole('row', { name: 'FCI Ahorro' })
    expect(within(filaFci).getByRole('spinbutton')).toHaveValue(100) // única posición: 100%

    await userEvent.click(within(filaFci).getByRole('button', { name: 'identificar contra CAFCI' }))
    await userEvent.type(within(filaFci).getByRole('textbox', { name: /buscar el fondo/ }), 'ahorro')
    await userEvent.click(await screen.findByRole('option', { name: /Fondo Ahorro Pesos/ }))

    // El ticker/nombre de la fila no cambia (identificar no es lo mismo que reemplazar la posición)
    // y ya no muestra la nota de "sin identificar".
    const filaActualizada = screen.getByRole('row', { name: 'FCI Ahorro' })
    expect(within(filaActualizada).queryByText(/FCI sin identificar/)).not.toBeInTheDocument()
    expect(within(filaActualizada).getByRole('spinbutton')).toHaveValue(100)
  })
})

// --- F-024: redondeo por lámina y resumen de cobertura --------------------------------------------

describe('F-024: redondeo por lámina', () => {
  it('GWT-1: con lámina informada, la fila redondea el VN a su múltiplo y muestra pedido y real distintos', async () => {
    responderCon({ especies: [especie({ lamina: 100 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    const fila = await screen.findByRole('row', { name: 'AL30' })
    // objetivo 5.000 USD / (105/100) = 4.761,9..., floor a múltiplo de 100 → 4.700.
    expect(within(fila).getByText(/VN 4\.700/)).toBeInTheDocument()
    expect(within(fila).getByRole('spinbutton')).toHaveValue(50)
    // Única posición: su peso real es 100%, distinto del 50% pedido — la pantalla no los iguala.
    expect(within(fila).getByText('100,00%')).toBeInTheDocument()
  })

  it('GWT-2: sin lámina informada, la fila lo marca y no redondea a ningún múltiplo', async () => {
    responderCon({ especies: [especie({ lamina: null })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    const fila = await screen.findByRole('row', { name: 'AL30' })
    // F-025: en vez del texto fijo "lámina no informada", la fila ofrece un input para cargarla.
    expect(within(fila).getByLabelText('cargar lámina de AL30')).toBeInTheDocument()
    // Sin lámina, el VN de F-018 no cae en ningún múltiplo inventado: 4.761,90... redondeado a
    // enteros para mostrar (4.762), no floreado a 100 como en GWT-1 (4.700).
    expect(within(fila).getByText(/VN 4\.762/)).toBeInTheDocument()
  })

  it('GWT-3: la cabecera declara cuántas posiciones y qué % quedaron sin lámina, y el total ajustado excluye esa parte', async () => {
    responderCon({
      especies: [
        especie({ lamina: 100 }),
        especie({ ticker: 'GD30', emision: 'GD30', precio: 100, emisor: 'República Argentina', lamina: null }),
      ],
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    // No se toca el peso de GD30: al agregarse segunda queda en 50 (equiponderado automático de
    // `alternarPapel`), así que las dos posiciones piden el mismo 50% y el cálculo de referencia
    // es simple.
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    await screen.findByRole('row', { name: 'AL30' })

    expect(
      await screen.findByText(/1 de 2 posiciones sin lámina informada — \d+,\d\d% de la cartera fuera del total ajustado/),
    ).toBeInTheDocument()

    const filaAjustado = screen.getByText('Invertido ajustado').closest('div')
    // Sólo AL30 (con lámina) entra al total ajustado: 4.700 VN x 105 / 100 = US$ 4.935,00.
    expect(within(filaAjustado as HTMLElement).getByText('US$ 4.935,00')).toBeInTheDocument()
  })

  it('cobertura total: si todas las posiciones tienen lámina, la leyenda lo dice y no hay faltante que declarar', async () => {
    responderCon({ especies: [especie({ lamina: 100 })] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'peso AL30 a 50' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    await screen.findByRole('row', { name: 'AL30' })

    expect(
      await screen.findByText('todas las posiciones con lámina informada: el total ajustado cubre la cartera'),
    ).toBeInTheDocument()
  })
})

describe('vaciar', () => {
  it('pide confirmación antes de vaciar una cartera con posiciones', async () => {
    responderCon({ especies: [especie()] })
    const confirmMock = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await screen.findByRole('row', { name: 'AL30' })

    await userEvent.click(screen.getByRole('button', { name: 'Vaciar' }))

    expect(confirmMock).toHaveBeenCalled()
    // El usuario canceló: la posición sigue ahí.
    expect(screen.getByRole('row', { name: 'AL30' })).toBeInTheDocument()

    confirmMock.mockRestore()
  })
})

// --- F-025: carga asistida de lámina --------------------------------------------------------------

describe('F-025: carga asistida de lámina', () => {
  function llamadaALamina(fetchMock: ReturnType<typeof responderCon>) {
    return fetchMock.mock.calls.find(([entrada]) =>
      (typeof entrada === 'string' ? entrada : entrada.toString()).includes('/lamina'),
    )
  }

  it('tipear y confirmar dispara la carga con el ticker y el valor correctos', async () => {
    const fetchMock = responderCon({
      especies: [especie({ lamina: null })],
      lamina: {
        status: 200,
        cuerpo: {
          guardado: true,
          ticker: 'AL30',
          lamina: 100,
          lamina_origen: 'carga manual',
          lamina_fecha: '2026-08-08',
        },
      },
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    const fila = await screen.findByRole('row', { name: 'AL30' })

    await userEvent.type(within(fila).getByLabelText('cargar lámina de AL30'), '100')
    await userEvent.click(within(fila).getByLabelText('confirmar lámina de AL30'))

    await vi.waitFor(() => expect(llamadaALamina(fetchMock)).toBeDefined())
    const [entrada, init] = llamadaALamina(fetchMock)!
    expect((typeof entrada === 'string' ? entrada : entrada.toString())).toContain(
      '/api/v1/condiciones/AL30/lamina',
    )
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init?.body as string)).toEqual({ valor: 100 })
  })

  it('en conflicto, muestra los dos valores en pugna y no dispara un alert nativo', async () => {
    const alertaNativa = vi.fn()
    vi.stubGlobal('alert', alertaNativa)
    responderCon({
      especies: [especie({ lamina: null })],
      lamina: {
        status: 409,
        cuerpo: {
          guardado: false,
          ticker: 'AL30',
          conflicto: { campo: 'lamina', emision: 'AL30', valores: { AL30: 1000, AL30D: 500 } },
        },
      },
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    const fila = await screen.findByRole('row', { name: 'AL30' })

    await userEvent.type(within(fila).getByLabelText('cargar lámina de AL30'), '1000')
    await userEvent.click(within(fila).getByLabelText('confirmar lámina de AL30'))

    const conflicto = await within(fila).findByRole('alert')
    expect(conflicto).toHaveTextContent('AL30=1000')
    expect(conflicto).toHaveTextContent('AL30D=500')
    expect(alertaNativa).not.toHaveBeenCalled()
    // El input sigue disponible para reintentar con otro valor, no se reemplaza por el mensaje.
    expect(within(fila).getByLabelText('cargar lámina de AL30')).toBeInTheDocument()
  })
})

// --- Refinamiento visual: encabezados de columna, leyenda del s/d y placeholder de calendario ---

describe('encabezados de columna', () => {
  it('muestra "% real" y "Paga en" para que el s/d y el minicalendario se entiendan de un vistazo', async () => {
    responderCon({ especies: [especie()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await screen.findByRole('row', { name: 'AL30' })

    expect(screen.getByRole('columnheader', { name: '% real' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Paga en' })).toBeInTheDocument()
  })

  it('la leyenda al pie explica qué significa el s/d y las celdas del minicalendario', async () => {
    responderCon({ especies: [especie()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await screen.findByRole('row', { name: 'AL30' })

    expect(screen.getByText(/sin precio o sin tipo de cambio — el dato falta, no es cero/)).toBeInTheDocument()
  })
})

// --- Tanda 13: la tabla muestra la cartera entera agrupada en bloques ----------------------------

/** Una acción del universo de renta variable, como la devuelve `/renta-variable/especies`. */
function accionGgal(extra: Record<string, unknown> = {}) {
  return {
    ticker: 'GGAL',
    clase_activo: 'accion',
    precio: 5000,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 4900,
    variacion: 0.02,
    volumen: 1_000_000,
    volumen_usd: 666,
    px_bid: null,
    px_ask: null,
    operaciones: null,
    fuente: 'byma',
    emision: null,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_largo: 'Grupo Financiero Galicia S.A.',
    perfil_fuente: 'SEC EDGAR',
    perfil_capturado_en: '2026-08-01T00:00:00Z',
    ...extra,
  }
}

describe('bloques por clase de activo', () => {
  it('agrupa la renta fija y la renta variable en la misma tabla, con subtotal por bloque', async () => {
    responderCon({
      especies: [especie({ clase_activo: 'bono_soberano' })],
      acciones: [accionGgal()],
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))

    expect(await screen.findByText('Soberanos y subsoberanos')).toBeInTheDocument()
    expect(screen.getByText('Renta variable')).toBeInTheDocument()
    // Las dos posiciones entraron con 50 y 50 tras el rebalanceo: ese es el subtotal de cada bloque.
    expect(screen.getAllByText('50,00%')).toHaveLength(2)
  })

  it('la fila de una acción muestra la denominación de la empresa donde el bono muestra el emisor', async () => {
    responderCon({ especies: [especie()], acciones: [accionGgal()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))

    const fila = await screen.findByRole('row', { name: 'GGAL' })
    expect(within(fila).getByText('Grupo Financiero Galicia S.A.')).toBeInTheDocument()
  })

  it('la acción declara "no aplica" en la columna de pagos: no tiene cronograma que mostrar', async () => {
    responderCon({ especies: [especie()], acciones: [accionGgal()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))

    const fila = await screen.findByRole('row', { name: 'GGAL' })
    // No es "s/d": el dato no falta, es que una acción no paga cupones (regla 2). El title explica
    // la diferencia, que es justamente lo que un "s/d" ahí borraría.
    expect(within(fila).getByText('no aplica')).toHaveAttribute(
      'title',
      'La renta variable no tiene cronograma de cupones: no hay meses de pago que mostrar.',
    )
  })

  it('el % pedido de la acción se edita desde la misma tabla', async () => {
    responderCon({ especies: [especie()], acciones: [accionGgal()] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))

    const fila = await screen.findByRole('row', { name: 'GGAL' })
    expect(within(fila).getByLabelText('ponderación pedida de GGAL')).toHaveValue(100)
  })

  it('un ticker sin cruce contra el universo queda visible en "sin clasificar", no escondido', async () => {
    responderCon({ especies: [] })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))

    expect(await screen.findByText('Sin clasificar')).toBeInTheDocument()
    expect(screen.getByRole('row', { name: 'AL30' })).toBeInTheDocument()
  })

  it('con renta fija resuelta y renta variable pendiente de resolver, el % real no infla al 100%', async () => {
    // Bug del relevamiento de confiabilidad de datos del 16/08/2026: `rv.subtotalUsd ?? 0` hacía
    // que `totalCarteraUsd` ignorara la porción de RV pendiente (GGAL en ARS, sin tipo de cambio)
    // y el % real de AL30 —que es la ÚNICA posición de RF— saliera 100% en vez de sin dato: el
    // denominador correcto todavía no se conoce, no es "0 de renta variable".
    responderCon({
      especies: [especie()],
      acciones: [accionGgal({ moneda_cotizacion: 'ARS' })],
      tipoDeCambio: { valor: null, disponible: false },
    })
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GGAL' }))
    await userEvent.click(screen.getByRole('button', { name: 'monto 10.000' }))

    const fila = await screen.findByRole('row', { name: 'AL30' })
    expect(within(fila).queryByText('100,00%')).not.toBeInTheDocument()
    expect(within(fila).getByText('s/d')).toBeInTheDocument()
  })
})


describe('sacar una posición desde la cartera', () => {
  it('quita el bono y reparte su peso pro-rata entre los que quedan', async () => {
    // La edición post-armado tiene que poder deshacer una sugerencia sin volver a la grilla: el
    // asesor está mirando la cartera, no la oferta.
    responderCon({ especies: [especie(), GD30] })
    renderizar()
    await userEvent.click(screen.getByRole('button', { name: 'agregar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'agregar GD30' }))

    await userEvent.click(screen.getByRole('button', { name: 'sacar AL30 de la cartera' }))

    expect(screen.queryByRole('row', { name: 'AL30' })).not.toBeInTheDocument()
    // El que queda se lleva todo: pro-rata sobre una sola posición es el 100%.
    expect(screen.getByRole('row', { name: 'GD30' })).toBeInTheDocument()
    expect(
      within(screen.getByRole('row', { name: 'GD30' })).getByLabelText(
        'ponderación pedida de GD30',
      ),
    ).toHaveValue(100)
  })
})
