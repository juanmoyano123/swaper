/**
 * Los GWT de F-039 vistos desde la pantalla, más el criterio que sostiene las tres queries
 * separadas: una falla en el cronograma no puede tumbar la ficha de precios ni las condiciones.
 *
 * Mismo patrón que `features/estado-dato/__tests__/BarraEstadoDato.test.tsx`: se mockea
 * `@/lib/supabase` (sin sesión) y `fetch` con `vi.stubGlobal`, despachando por la ruta exacta que
 * pide cada uno de los tres hooks.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { FichaInstrumento } from '../FichaInstrumento'
import type {
  Condiciones,
  Cronograma,
  EspecieFicha,
  Ficha,
  GrupoDocumentos,
  PagoCronograma,
  Prospecto,
  ResumenCronograma,
  SerieCnv,
} from '../lib/schema'

afterEach(() => {
  vi.unstubAllGlobals()
})

// --- Fixtures --------------------------------------------------------------------------------------

function especie(ticker: string, extra: Partial<EspecieFicha> = {}): EspecieFicha {
  return {
    ticker,
    emision: 'AL30',
    sufijo_liquidacion: ticker === 'AL30' ? null : ticker.slice(-1),
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.12,
    duracion: 3.5,
    vencimiento: '2030-07-09',
    ley: 'Ley Argentina',
    moneda_cupon: 'USD',
    emisor: 'Gobierno Argentino',
    precio: 65_000,
    moneda_cotizacion: 'ARS',
    volumen: 1_000_000,
    volumen_usd: 650,
    paridad: 0.875,
    dato_sano: true,
    fuente: null,
    ...extra,
  }
}

function ficha(ticker: string, hermanas: EspecieFicha[] = []): Ficha {
  return { ticker, especie: especie(ticker), hermanas }
}

function condiciones(detalle: Condiciones['condiciones']): Condiciones {
  return { ticker: 'AL30D', condiciones: detalle }
}

function condicionDetalleVacia(): NonNullable<Condiciones['condiciones']> {
  return {
    ticker: 'AL30D',
    ley: null,
    ley_origen: null,
    ley_fecha: null,
    moneda_pago: null,
    moneda_pago_origen: null,
    moneda_pago_fecha: null,
    lamina: null,
    lamina_origen: null,
    lamina_fecha: null,
    calificacion: null,
    calificacion_origen: null,
    calificacion_fecha: null,
    sector: null,
    sector_origen: null,
    sector_fecha: null,
    underlying: null,
    underlying_origen: null,
    underlying_fecha: null,
  }
}

function pago(extra: Partial<PagoCronograma> = {}): PagoCronograma {
  return { fecha: '2028-01-09', interes: 1.5, amortizacion: 0, moneda: 'USD', residual: 100.0, ...extra }
}

function resumenCronograma(extra: Partial<ResumenCronograma> = {}): ResumenCronograma {
  return {
    residual_vigente: 100.0,
    valor_tecnico: 101.2,
    cupon_corrido: 1.2,
    paridad: 0.875,
    coherente: true,
    motivo_ausente: null,
    ...extra,
  }
}

function cronograma(pagos: PagoCronograma[], resumen: Partial<ResumenCronograma> = {}): Cronograma {
  return { ticker: 'AL30D', pagos, resumen: resumenCronograma(resumen) }
}

function prospecto(ticker: string, extra: Partial<Prospecto> = {}): Prospecto {
  return {
    ticker,
    aplica: false,
    emisor: null,
    cuit: null,
    cuit_fuente: null,
    url_emisor_cnv: null,
    grupos: [],
    motivo_ausente: 'no es una obligación negociable',
    fuente: 'CNV',
    ...extra,
  }
}

function grupoDocumentos(grupo: string, extra: Partial<GrupoDocumentos['documentos'][number]> = {}): GrupoDocumentos {
  return {
    grupo,
    documentos: [
      {
        fecha: '2026-08-11',
        hora: '15:34',
        descripcion: 'Un documento de prueba',
        documento_id: '3557195',
        uuid: '96bad10a-713b-46e1-a9ac-04fa19f3a8cd',
        url_publicview: 'https://aif2.cnv.gov.ar/presentations/publicview/96bad10a-713b-46e1-a9ac-04fa19f3a8cd',
        ...extra,
      },
    ],
  }
}

/** Un grupo con historial: el primero es el más reciente, que es el orden en que la CNV los sirve. */
function grupoConHistorial(grupo: string, descripciones: string[]): GrupoDocumentos {
  return {
    grupo,
    documentos: descripciones.map((descripcion, i) => ({
      fecha: `2026-0${8 - i}-11`,
      hora: '15:34',
      descripcion,
      documento_id: `355719${i}`,
      uuid: `uuid-${grupo}-${i}`,
      url_publicview: `https://aif2.cnv.gov.ar/presentations/publicview/uuid-${grupo}-${i}`,
    })),
  }
}

/** Una serie con sus pocos documentos: el drill-down de F-072. Los uuid vienen en mayúsculas porque
 *  así los sirve `DetallesDeFormularios` —la otra plantilla de la CNV los da en minúscula— y el
 *  backend los reemite tal cual, sin normalizarlos. */
function serieCnv(uuid: string): SerieCnv {
  return {
    ticker: 'TLCMO',
    uuid,
    aplica: true,
    series: [
      {
        serie_id: '88539',
        nombre: 'Clase 29',
        url_detalles_formulario:
          'https://www.cnv.gov.ar/SitioWeb/Empresas/DetallesDeFormularios?serieID=88539&nombreserie=Clase+29&idfiscal=30639453738&nombresociedad=TELECOM',
        documentos: [
          {
            fecha: '2026-05-24',
            hora: '10:16 Hs',
            formulario: 'Aviso de Suscripción',
            documento_id: '3527921',
            uuid: 'BC077304-DF6B-4B0E-8320-EE82DFDF520C',
            url_publicview:
              'https://aif2.cnv.gov.ar/presentations/publicview/BC077304-DF6B-4B0E-8320-EE82DFDF520C',
          },
          {
            fecha: '2026-05-26',
            hora: '08:52 Hs',
            formulario: 'Suplemento',
            documento_id: '3527952',
            uuid: 'AC613AE1-04AE-4D55-AA2A-88F3A7DB9F29',
            url_publicview:
              'https://aif2.cnv.gov.ar/presentations/publicview/AC613AE1-04AE-4D55-AA2A-88F3A7DB9F29',
          },
        ],
        motivo_ausente: null,
      },
    ],
    motivo_ausente: null,
    fuente: 'CNV',
  }
}

const CONTRATO_ERROR = (mensaje: string) => ({
  error: { code: 'not_found', message: mensaje, details: null, request_id: null },
})

interface Ruta {
  status?: number
  body: unknown
}

/** Un `fetch` falso que despacha por la ruta exacta que pide cada uno de los tres hooks.
 *  `Ruta | undefined` porque `rutasOk` construye el mapa combinando claves fijas con
 *  `overrides: Partial<Record<...>>`, y el spread deja esas claves como posiblemente ausentes
 *  aunque en runtime siempre estén — el guard de abajo ya cubre ese caso. */
function mockearRutas(mapa: Record<string, Ruta | undefined>) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const ruta = mapa[url]
    if (!ruta) {
      throw new Error(`ruta no mockeada en el test: ${url}`)
    }
    return Promise.resolve(
      new Response(JSON.stringify(ruta.body), {
        status: ruta.status ?? 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderizar(ticker: string | undefined) {
  const cliente = crearQueryClient()
  return render(
    <QueryClientProvider client={cliente}>
      <FichaInstrumento ticker={ticker} />
    </QueryClientProvider>,
  )
}

const RUTA_FICHA = (t: string) => `/api/v1/instrumentos/${t}`
const RUTA_CONDICIONES = (t: string) => `/api/v1/instrumentos/${t}/condiciones`
const RUTA_CRONOGRAMA = (t: string) => `/api/v1/instrumentos/${t}/cronograma`
const RUTA_SENSIBILIDAD = (t: string) => `/api/v1/instrumentos/${t}/sensibilidad`
const RUTA_PROSPECTO = (t: string) => `/api/v1/instrumentos/${t}/prospecto`
const RUTA_SERIE = (t: string, uuid: string) =>
  `/api/v1/instrumentos/${t}/prospecto/${uuid}/serie`

/** Las cinco rutas resolviendo en éxito, con datos mínimos — el punto de partida de la mayoría de
 * los tests, que después pisan sólo la que les interesa.
 *
 * La sensibilidad la agregó F-040 (tanda 8b): es la cuarta query independiente de la ficha, y sin
 * mockearla los tests de "las queries son independientes" veían dos alertas en pantalla en vez de
 * una — la del panel que el test rompe a propósito, más la de esta ruta cayendo en el `throw` de
 * ruta no mockeada. Se responde `calculable: false`, que es el caso más barato y no dibuja tabla.
 *
 * El prospecto lo agregó F-072: el hook se pide siempre (no depende de la clase del ticker que
 * todavía no se conoce cuando se dispara), así que toda especie por defecto —`bono_soberano`—
 * necesita esta ruta mockeada aunque el panel no la vaya a mostrar. */
function rutasOk(ticker: string, overrides: Partial<Record<string, Ruta>> = {}) {
  return {
    [RUTA_FICHA(ticker)]: { body: ficha(ticker) },
    [RUTA_CONDICIONES(ticker)]: { body: condiciones(null) },
    [RUTA_CRONOGRAMA(ticker)]: { body: cronograma([]) },
    [RUTA_SENSIBILIDAD(ticker)]: {
      body: {
        ticker,
        tir_actual: null,
        naturaleza: null,
        naturaleza_nombre: null,
        calculable: false,
        motivo: 'sin TIR vigente: no se calcula',
        escenarios: [],
        omitidos_bps: [],
      },
    },
    [RUTA_PROSPECTO(ticker)]: { body: prospecto(ticker) },
    ...overrides,
  }
}

// --- GWT-1: el mismo papel en las tres monedas, sin sumarse ni promediarse ------------------------

describe('el bloque de las tres monedas', () => {
  it('renderiza una tarjeta por la especie pedida y por cada hermana, con las puntas en s/d', async () => {
    const hermanas = [especie('AL30', { sufijo_liquidacion: null }), especie('AL30C')]
    mockearRutas(rutasOk('AL30D', { [RUTA_FICHA('AL30D')]: { body: ficha('AL30D', hermanas) } }))

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(screen.getByText('AL30')).toBeInTheDocument()
    expect(screen.getByText('AL30C')).toBeInTheDocument()

    const puntas = screen.getAllByTitle('las puntas no viajan por la fuente hoy')
    expect(puntas).toHaveLength(3)
    for (const bloque of puntas) {
      expect(bloque).toHaveTextContent('compra s/d')
      expect(bloque).toHaveTextContent('venta s/d')
    }

    expect(screen.getByText(/no se suman ni se convierten entre sí/)).toBeInTheDocument()
  })

  it('sin hermanas muestra una sola tarjeta', async () => {
    mockearRutas(rutasOk('S30J6'))

    renderizar('S30J6')

    await screen.findByText('S30J6')
    expect(screen.getAllByTitle('las puntas no viajan por la fuente hoy')).toHaveLength(1)
  })
})

// --- Un ticker que no está en el universo de hoy --------------------------------------------------

describe('un ticker fuera del universo', () => {
  it('muestra un mensaje explícito y no una pantalla en blanco', async () => {
    mockearRutas({
      ...rutasOk('NOEXISTE'),
      [RUTA_FICHA('NOEXISTE')]: {
        status: 404,
        body: CONTRATO_ERROR('NOEXISTE no está en el universo de hoy'),
      },
    })

    renderizar('NOEXISTE')

    expect(await screen.findByText('NOEXISTE no está en el universo de hoy.')).toBeInTheDocument()
  })
})

// --- GWT-2: calificación ausente → "no informado", nunca vacío ni inferido -------------------------

describe('condiciones de emisión', () => {
  it('sin fila curada, los seis campos dicen "no informado"', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    await screen.findByText('AL30D')
    expect(screen.getAllByText('no informado')).toHaveLength(6)
  })

  it('un campo presente muestra su valor y trae origen y fecha en el título', async () => {
    const detalle = {
      ...condicionDetalleVacia(),
      ley: 'Ley Argentina',
      ley_origen: 'condiciones_emision.csv (curado)',
      ley_fecha: '2026-08-05',
    }
    mockearRutas(
      rutasOk('AL30D', { [RUTA_CONDICIONES('AL30D')]: { body: condiciones(detalle) } }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    // La ficha (fuera de condiciones) también dice "Ley Argentina" — el título distingue cuál es
    // el campo de condiciones curado.
    const valor = await screen.findByTitle(/condiciones_emision\.csv/)
    expect(valor).toHaveTextContent('Ley Argentina')
    expect(valor.getAttribute('title')).toContain('05/08/2026')
    // El resto de los campos de esta ficha sigue "no informado": no se contagia entre campos.
    expect(screen.getAllByText('no informado')).toHaveLength(5)
  })
})

// --- Renta variable: "no aplica", no "s/d" --------------------------------------------------------

describe('un instrumento de renta variable', () => {
  it('muestra "no aplica" en rendimiento y duración', async () => {
    const accion = especie('GGAL', { clase_activo: 'accion', rendimiento: 0.5, duracion: 1 })
    mockearRutas(rutasOk('GGAL', { [RUTA_FICHA('GGAL')]: { body: { ...ficha('GGAL'), especie: accion } } }))

    renderizar('GGAL')

    await screen.findByText('GGAL')
    expect(screen.getAllByText('no aplica')).toHaveLength(2)
  })
})

// --- El tipo del instrumento, con la etiqueta compartida del monitor ------------------------------

describe('el tipo del instrumento', () => {
  it('la grilla declara la clase con su etiqueta legible', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    await screen.findByText('AL30D')
    expect(screen.getByText('Tipo')).toBeInTheDocument()
    expect(screen.getByText('Soberano')).toBeInTheDocument()
  })
})

// --- GWT-3: el cronograma completo, interés separado de amortización -------------------------------

describe('el cronograma', () => {
  it('separa interés de amortización en filas distintas cuando el pago trae los dos', async () => {
    const pagos = [
      pago({ fecha: '2028-01-09', interes: 1.5, amortizacion: 0 }),
      pago({ fecha: '2030-07-09', interes: 1.5, amortizacion: 100 }),
    ]
    mockearRutas(
      rutasOk('AL30D', { [RUTA_CRONOGRAMA('AL30D')]: { body: cronograma(pagos) } }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    const filas = await screen.findAllByRole('row')
    // Encabezado + 1 fila de renta pura + 2 filas del pago de vencimiento (renta y amortización).
    expect(filas).toHaveLength(4)
    expect(screen.getAllByText('renta')).toHaveLength(2)
    expect(screen.getByText('amortización')).toBeInTheDocument()
  })

  it('sin pagos declara que no hay cronograma cargado, no un error', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    expect(
      await screen.findByText('Sin cronograma cargado para esta emisión.'),
    ).toBeInTheDocument()
  })
})

// --- Residual y valor técnico (relevamiento de confiabilidad de datos, 17/08/2026) ---------------

describe('residual y valor técnico', () => {
  it('muestra el residual de cada pago y la lectura de valor técnico contra la paridad', async () => {
    const pagos = [pago({ fecha: '2028-01-09', interes: 1.5, amortizacion: 0, residual: 100.0 })]
    mockearRutas(
      rutasOk('AL30D', {
        [RUTA_CRONOGRAMA('AL30D')]: {
          body: cronograma(pagos, {
            residual_vigente: 100.0,
            valor_tecnico: 101.2,
            paridad: 0.875,
            motivo_ausente: null,
          }),
        },
      }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    const lectura = (await screen.findByText('Residual vigente:')).closest('p')
    expect(lectura).toHaveTextContent('Residual vigente: 100,0 de 100')
    expect(lectura).toHaveTextContent('Valor técnico: 101,20')
    expect(lectura).toHaveTextContent('cotiza al 87,50% del técnico')
    // El residual de la única fila del cronograma, no sólo el de la lectura de arriba.
    const filas = await screen.findAllByRole('row')
    expect(filas[1]).toHaveTextContent('100,0')
  })

  it('sin residual coherente, declara sin dato y el motivo en vez de un número', async () => {
    const pagos = [pago({ residual: null })]
    mockearRutas(
      rutasOk('AL30D', {
        [RUTA_CRONOGRAMA('AL30D')]: {
          body: cronograma(pagos, {
            residual_vigente: null,
            valor_tecnico: null,
            paridad: null,
            coherente: false,
            motivo_ausente:
              'el residual que declara la fuente contradice la suma de amortizaciones ya pagadas: no se calcula un valor técnico sobreestimado',
          }),
        },
      }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    expect(screen.getByText(/Valor técnico: s\/d/)).toBeInTheDocument()
    expect(screen.getByText(/contradice la suma de amortizaciones/)).toBeInTheDocument()
    // El residual de la fila también se declara vacío, nunca un número contradictorio.
    const filas = await screen.findAllByRole('row')
    expect(filas[1]).toHaveTextContent('s/d')
  })

  it('con moneda cruzada, declara la paridad sin calcular y no la esconde del todo', async () => {
    mockearRutas(
      rutasOk('AL30D', {
        [RUTA_CRONOGRAMA('AL30D')]: {
          body: cronograma([pago()], {
            residual_vigente: 100.0,
            valor_tecnico: 101.2,
            paridad: null,
            motivo_ausente: 'cotiza en una moneda distinta de la que paga el flujo',
          }),
        },
      }),
    )

    renderizar('AL30D')

    await screen.findByText('AL30D')
    expect(screen.getByText(/sin paridad: cotiza en una moneda distinta/)).toBeInTheDocument()
  })
})

// --- Tres queries independientes: una en error no tumba a las otras dos ----------------------------

describe('las tres queries son independientes', () => {
  it('un cronograma que falla no tapa la ficha de precios ni las condiciones', async () => {
    const detalle = { ...condicionDetalleVacia(), sector: 'Soberano' }
    mockearRutas({
      ...rutasOk('AL30D', { [RUTA_CONDICIONES('AL30D')]: { body: condiciones(detalle) } }),
      [RUTA_CRONOGRAMA('AL30D')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    // Dos "Soberano": el tipo de la ficha (clase_activo) y el sector de condiciones. Lo que este
    // test cuida es que el de condiciones haya llegado pese al cronograma roto.
    expect(await screen.findAllByText('Soberano')).toHaveLength(2)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('condiciones que fallan no tapan la ficha de precios ni el cronograma', async () => {
    mockearRutas({
      ...rutasOk('AL30D', {
        [RUTA_CRONOGRAMA('AL30D')]: { body: cronograma([pago()]) },
      }),
      [RUTA_CONDICIONES('AL30D')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(await screen.findByText('renta')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })
})

// --- Prospecto de emisión (F-072) -------------------------------------------------------------

describe('prospecto de emisión', () => {
  it('para un bono soberano no se muestra el panel, aunque la ruta responda', async () => {
    mockearRutas(rutasOk('AL30D'))

    renderizar('AL30D')

    expect(await screen.findByText('AL30D')).toBeInTheDocument()
    expect(screen.queryByText('Prospecto de emisión')).not.toBeInTheDocument()
  })

  it('para una ON con documentos, agrupa y muestra "Ver en CNV" por fila', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo', emisor: 'TELECOM ARGENTINA S.A.' })
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            emisor: 'TELECOM ARGENTINA S.A.',
            cuit: '30639453738',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [grupoDocumentos('Suplementos')],
            motivo_ausente: null,
          }),
        },
      }),
    )

    renderizar('TLCMO')

    expect(await screen.findByText('Prospecto de emisión')).toBeInTheDocument()
    expect(await screen.findByText('Suplementos')).toBeInTheDocument()
    expect(await screen.findByText('Un documento de prueba')).toBeInTheDocument()
    expect(await screen.findByText('Ver en CNV')).toBeInTheDocument()
    expect(await screen.findByText('Ver todos los documentos del emisor en CNV')).toBeInTheDocument()
  })

  it('por defecto muestra sólo lo último de cada grupo, con el conteo del historial', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo', emisor: 'TELECOM ARGENTINA S.A.' })
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            emisor: 'TELECOM ARGENTINA S.A.',
            cuit: '30639453738',
            cuit_fuente: 'ARCA',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [
              grupoConHistorial('Prospectos', ['Prospecto de hoy', 'Prospecto viejo']),
              grupoConHistorial('Suplementos', ['Suplemento de hoy', 'Suplemento viejo']),
            ],
            motivo_ausente: null,
          }),
        },
      }),
    )

    renderizar('TLCMO')

    expect(await screen.findByText('Prospecto de hoy')).toBeInTheDocument()
    expect(await screen.findByText('Suplemento de hoy')).toBeInTheDocument()
    expect(screen.queryByText('Prospecto viejo')).not.toBeInTheDocument()
    expect(screen.queryByText('Suplemento viejo')).not.toBeInTheDocument()
    // El conteo por grupo avisa que hay historial detrás; el link a la CNV está desde el arranque.
    expect(screen.getAllByText('· 2')).toHaveLength(2)
    expect(await screen.findByText('Ver todos los documentos del emisor en CNV')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Ver historial completo (4 documentos)' }))

    expect(await screen.findByText('Prospecto viejo')).toBeInTheDocument()
    expect(await screen.findByText('Suplemento viejo')).toBeInTheDocument()
    expect(await screen.findByText('Ver todos los documentos del emisor en CNV')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Mostrar menos' }))

    expect(screen.queryByText('Prospecto viejo')).not.toBeInTheDocument()
  })

  it('con un solo documento por grupo no ofrece historial', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo', emisor: 'TELECOM ARGENTINA S.A.' })
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            cuit: '30639453738',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [grupoDocumentos('Suplementos')],
            motivo_ausente: null,
          }),
        },
      }),
    )

    renderizar('TLCMO')

    expect(await screen.findByText('Un documento de prueba')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Ver historial completo/ })).not.toBeInTheDocument()
  })

  it('sin documentos, declara el motivo en vez de una tabla vacía', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo', emisor: 'TELECOM ARGENTINA S.A.' })
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            emisor: 'TELECOM ARGENTINA S.A.',
            motivo_ausente: 'el emisor todavía no tiene CUIT curado',
          }),
        },
      }),
    )

    renderizar('TLCMO')

    expect(await screen.findByText('Prospecto de emisión')).toBeInTheDocument()
    expect(await screen.findByText('el emisor todavía no tiene CUIT curado')).toBeInTheDocument()
  })

  it('un prospecto que falla no tapa el resto de la ficha', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo' })
    mockearRutas({
      ...rutasOk('TLCMO', { [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } } }),
      [RUTA_PROSPECTO('TLCMO')]: { status: 500, body: CONTRATO_ERROR('roto') },
    })

    renderizar('TLCMO')

    expect(await screen.findByText('TLCMO')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
  })

  it('esconde los grupos administrativos hasta que se pide el historial completo', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo' })
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            cuit: '30639453738',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [
              grupoConHistorial('Suplementos', ['Suplemento de hoy']),
              grupoConHistorial('Aviso de Pago', ['Un aviso de pago']),
              grupoConHistorial('Informe Trimestral ON', ['Un informe trimestral']),
              grupoConHistorial('Otra Información', ['Otra cosa']),
            ],
            motivo_ausente: null,
          }),
        },
      }),
    )

    renderizar('TLCMO')

    // Lo de la colocación se ve; lo administrativo —245 de los 508 documentos de Telecom son avisos
    // de pago— no entierra al resto.
    expect(await screen.findByText('Suplemento de hoy')).toBeInTheDocument()
    expect(screen.queryByText('Un aviso de pago')).not.toBeInTheDocument()
    expect(screen.queryByText('Un informe trimestral')).not.toBeInTheDocument()
    expect(screen.queryByText('Otra cosa')).not.toBeInTheDocument()

    // El historial completo sigue mostrando todo, sin filtrar: no se esconde nada, se posterga.
    await userEvent.click(
      screen.getByRole('button', { name: 'Ver historial completo (4 documentos)' }),
    )

    expect(await screen.findByText('Un aviso de pago')).toBeInTheDocument()
    expect(await screen.findByText('Un informe trimestral')).toBeInTheDocument()
    expect(await screen.findByText('Otra cosa')).toBeInTheDocument()
  })

  it('al tocar "Ver serie" muestra los documentos de esa serie y el link a la CNV', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo' })
    const uuid = '96bad10a-713b-46e1-a9ac-04fa19f3a8cd'
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            cuit: '30639453738',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [grupoDocumentos('Suplementos')],
            motivo_ausente: null,
          }),
        },
        [RUTA_SERIE('TLCMO', uuid)]: { body: serieCnv(uuid) },
      }),
    )

    renderizar('TLCMO')

    // La serie no se pide sola: recién al tocar el botón. Antes de eso no hay nada de la serie.
    expect(await screen.findByText('Un documento de prueba')).toBeInTheDocument()
    expect(screen.queryByText('Clase 29')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Ver serie' }))

    expect(await screen.findByText('Clase 29')).toBeInTheDocument()
    expect(await screen.findByText('Aviso de Suscripción')).toBeInTheDocument()
    expect(await screen.findByText('Suplemento')).toBeInTheDocument()
    const link = await screen.findByRole('link', { name: 'Abrir en CNV' })
    expect(link).toHaveAttribute('href', expect.stringContaining('serieID=88539'))
  })

  it('declara cuando el documento no dice a qué serie corresponde', async () => {
    const especieOn = especie('TLCMO', { clase_activo: 'on_corporativo' })
    const uuid = '96bad10a-713b-46e1-a9ac-04fa19f3a8cd'
    mockearRutas(
      rutasOk('TLCMO', {
        [RUTA_FICHA('TLCMO')]: { body: { ...ficha('TLCMO'), especie: especieOn } },
        [RUTA_PROSPECTO('TLCMO')]: {
          body: prospecto('TLCMO', {
            aplica: true,
            cuit: '30639453738',
            url_emisor_cnv: 'https://www.cnv.gov.ar/SitioWeb/Empresas/Empresa/30639453738',
            grupos: [grupoDocumentos('Suplementos')],
            motivo_ausente: null,
          }),
        },
        [RUTA_SERIE('TLCMO', uuid)]: {
          body: {
            ticker: 'TLCMO',
            uuid,
            aplica: false,
            series: [],
            motivo_ausente: 'este documento no declara a qué serie corresponde',
            fuente: 'CNV',
          },
        },
      }),
    )

    renderizar('TLCMO')

    await userEvent.click(await screen.findByRole('button', { name: 'Ver serie' }))

    expect(
      await screen.findByText('este documento no declara a qué serie corresponde'),
    ).toBeInTheDocument()
  })
})

// --- El contrato de tipos existente: `ticker` puede no llegar todavía ------------------------------

describe('sin ticker', () => {
  it('mantiene el estado vacío original, sin disparar ningún fetch', () => {
    const fetchMock = mockearRutas({})

    renderizar(undefined)

    expect(screen.getByText('No hay datos de este instrumento todavía.')).toBeInTheDocument()
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
