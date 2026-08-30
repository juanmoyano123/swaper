/**
 * `PanelArmadoAsistido` — F-019. Mock de `fetch` directo, mismo patrón que
 * `useArmadoAsistido.test.ts`: lo que importa acá es que el formulario mande los cinco parámetros
 * del mandato y que las alertas de la respuesta se muestren.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createElement } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import { crearQueryClient } from '@/app/queryClient'

import { PanelArmadoAsistido } from '../components/PanelArmadoAsistido'
import { ArmadorProvider, useArmador } from '../store/carteraStore'

afterEach(() => {
  vi.unstubAllGlobals()
})

function mockFetch(status: number, cuerpo: unknown) {
  const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
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

function CarteraVisible() {
  const { pos, montoTotal } = useArmador()
  return (
    <>
      <p data-testid="cartera">{pos.map((p) => `${p.ticker}:${p.peso}`).join(',')}</p>
      <p data-testid="montoTotal">{montoTotal}</p>
    </>
  )
}

function renderizar() {
  const cliente = crearQueryClient()
  return render(
    createElement(
      QueryClientProvider,
      { client: cliente },
      createElement(ArmadorProvider, null, createElement(PanelArmadoAsistido), createElement(CarteraVisible)),
    ),
  )
}

const RESULTADO_OK = {
  posiciones: [
    { ticker: 'GD35', pct_cartera: 70, monto: 70000, clase: 'renta_fija' },
    { ticker: 'AL30', pct_cartera: 30, monto: 30000, clase: 'renta_fija' },
  ],
  mix_aplicado: { usd_hard: 100 },
  origen_mix: 'cobertura devaluacion',
  perfil: 'moderado',
  sectores: { presentes: 2, minimo: 3, suficiente: false },
  pct_rv_aplicado: 0,
  alertas: [
    {
      codigo: 'diversificacion_sectorial_insuficiente',
      mensaje: 'la cartera tiene 2 sectores y el perfil pide al menos 3',
      severidad: 'advertencia',
      accion_requerida: null,
      detalle: {},
    },
  ],
}

/** La llamada a `/api/v1/armado`, esperando a que ocurra. El panel también consulta el universo
 *  —para poder ofrecer las calificaciones del filtro—, así que la del armado no es la primera. */
async function esperarLlamadaDeArmado(fetchMock: ReturnType<typeof mockFetch>) {
  let llamada: [string, RequestInit | undefined] | undefined
  await waitFor(() => {
    llamada = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/v1/armado')) as
      | [string, RequestInit | undefined]
      | undefined
    expect(llamada).toBeDefined()
  })
  return llamada!
}

describe('PanelArmadoAsistido', () => {
  it('envía los parámetros del mandato al pedir el armado', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.selectOptions(screen.getByLabelText('Moneda de referencia'), 'usd')
    await userEvent.selectOptions(screen.getByLabelText('Objetivo de cobertura'), 'devaluacion')
    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'conservador')
    await userEvent.selectOptions(screen.getByLabelText('Horizonte'), 'largo')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    expect(JSON.parse(init?.body as string)).toEqual({
      monto: 100000,
      moneda: 'usd',
      cobertura: 'devaluacion',
      perfil: 'conservador',
      horizonte: 'largo',
      // El perfil conservador no lleva renta variable, como la cartera conservadora del Excel.
      pct_rv: 0,
      rubro_rv: null,
      // F-078: los cinco ejes siempre, con los defaults del perfil elegido. El backend no mergea
      // parcialmente contra sus propios defaults —`topes_rv` presente significa "exactamente
      // esto"—, así que omitir un eje lo apagaría en vez de dejarle el suyo.
      topes_rv: {
        max_pct_rubro: 30,
        max_pct_pais: 40,
        max_pct_region: 60,
        // Apagado de fábrica en los tres perfiles: la moneda de cotización es forma de
        // liquidación, no exposición (ver `TOPES_RV_PERFIL`).
        max_pct_moneda: null,
        max_pct_mercado: 60,
      },
      // El piso de la grilla viaja como piso del armado: `FILTROS_ARMADOR_INICIALES` arranca en 6%.
      min_rend: 6,
    })
  })

  it('el % de renta variable se precarga con el default del perfil', async () => {
    renderizar()

    const campo = screen.getByLabelText('% renta variable')
    // Moderado, el perfil inicial: un cuarto en acciones.
    expect(campo).toHaveValue(25)

    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'agresivo')
    expect(campo).toHaveValue(60)

    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'conservador')
    expect(campo).toHaveValue(0)
  })

  it('el % de renta variable se puede editar después de elegir el perfil', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.clear(screen.getByLabelText('% renta variable'))
    await userEvent.type(screen.getByLabelText('% renta variable'), '40')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    expect(JSON.parse(init?.body as string).pct_rv).toBe(40)
  })

  it('la temática elegida viaja como el rubro literal de la SEC (vía filtro_rv desde F-079)', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.selectOptions(screen.getByLabelText('Temática (CEDEARs)'), 'tecnologicas')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    const cuerpo = JSON.parse(init?.body as string)
    // F-079: Tecnológicas pasó a referenciar el preset compartido de `lib/presetsRv.ts` en vez de
    // un `rubroRv` inline, así que el rubro literal de la SEC ahora viaja dentro de `filtro_rv`.
    expect(cuerpo.rubro_rv).toBeNull()
    expect(cuerpo.filtro_rv.rubros).toEqual(['Office of Technology'])
  })

  it('en éxito, precarga la cartera y muestra las alertas de la respuesta', async () => {
    mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    await waitFor(() =>
      expect(screen.getByTestId('cartera')).toHaveTextContent('GD35:70,AL30:30'),
    )
    expect(
      screen.getByText('la cartera tiene 2 sectores y el perfil pide al menos 3'),
    ).toBeInTheDocument()
  })

  it('el botón queda deshabilitado sin un monto válido', () => {
    renderizar()

    expect(screen.getByRole('button', { name: 'Armar cartera asistida' })).toBeDisabled()
  })

  it('el monto del asistido es el mismo capital que reparte la cartera, no un campo aparte', async () => {
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '80000')

    // Escribir acá mueve el `montoTotal` del store, que es el que usan los resolvers para
    // calcular nominales: antes eran dos números sin relación y cargar el capital en esta ficha
    // no cambiaba nada de lo que se veía más abajo.
    expect(screen.getByTestId('montoTotal')).toHaveTextContent('80000')
  })

  it('avisa cuando la renta variable pedida no entró — el pedido no se ignora en silencio', async () => {
    // El caso real de hoy: con temática puesta no hay ninguna acción con sector informado, así que
    // el backend devuelve pct_rv_aplicado 0 y deja la renta fija ocupando la cartera entera.
    mockFetch(200, {
      ...RESULTADO_OK,
      pct_rv_aplicado: 0,
      alertas: [
        {
          codigo: 'rv_sin_candidatos',
          mensaje: 'ninguna especie de renta variable pasó los filtros pedidos',
          severidad: 'advertencia',
          accion_requerida: null,
          detalle: {},
        },
      ],
    })
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    expect(
      await screen.findByText(/Pediste 25% en renta variable y entró 0%/),
    ).toBeInTheDocument()
  })

  it('no avisa nada cuando lo pedido y lo aplicado coinciden', async () => {
    mockFetch(200, { ...RESULTADO_OK, pct_rv_aplicado: 25 })
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    await waitFor(() => expect(screen.getByTestId('cartera')).toHaveTextContent('GD35'))
    expect(screen.queryByText(/Pediste/)).not.toBeInTheDocument()
  })
})

// --- F-078: los topes de renta variable ---------------------------------------------------------

describe('los topes de renta variable', () => {
  it('vienen precargados con los del perfil y a la vista, no escondidos en el backend', async () => {
    renderizar()

    // Moderado, el perfil inicial.
    expect(screen.getByLabelText('Máx. % por sector (SIC)')).toHaveValue(40)
    expect(screen.getByLabelText('Máx. % por país')).toHaveValue(50)
    expect(screen.getByLabelText('Máx. % por región')).toHaveValue(70)
    expect(screen.getByLabelText('Máx. % por mercado')).toHaveValue(70)
    // La moneda arranca apagada en los tres perfiles: es forma de liquidación, no exposición.
    expect(screen.getByLabelText('Máx. % por moneda')).toHaveValue(null)
  })

  it('cambiar de perfil los vuelve a poner, igual que con el % de renta variable', async () => {
    renderizar()

    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'conservador')
    expect(screen.getByLabelText('Máx. % por sector (SIC)')).toHaveValue(30)

    await userEvent.selectOptions(screen.getByLabelText('Perfil'), 'agresivo')
    expect(screen.getByLabelText('Máx. % por sector (SIC)')).toHaveValue(55)
  })

  it('son inputs numéricos con rango, no sliders: el design system no tiene ninguno', async () => {
    renderizar()

    const rubro = screen.getByLabelText('Máx. % por sector (SIC)')
    expect(rubro).toHaveAttribute('type', 'number')
    expect(rubro).toHaveAttribute('min', '1')
    expect(rubro).toHaveAttribute('max', '100')
  })

  it('vaciar un campo apaga ese eje: viaja como null, no como cero', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.clear(screen.getByLabelText('Máx. % por país'))
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    const cuerpo = JSON.parse(init?.body as string)
    // `null` y no `0`: el backend valida `gt=0`, y un 0 significaría "ninguna categoría puede
    // pesar nada", que es incumplible por construcción. Apagado es apagado.
    expect(cuerpo.topes_rv.max_pct_pais).toBeNull()
    // Los otros cuatro siguen viajando: el backend no mergea contra sus defaults, así que omitir
    // uno lo apagaría en vez de dejarle el suyo.
    expect(cuerpo.topes_rv).toEqual({
      max_pct_rubro: 40,
      max_pct_pais: null,
      max_pct_region: 70,
      max_pct_moneda: null,
      max_pct_mercado: 70,
    })
  })

  it('un tope escrito a mano se acota a 1..100 en el input, no de vuelta con un 422', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    const region = screen.getByLabelText('Máx. % por región')
    await userEvent.clear(region)
    await userEvent.type(region, '150')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    expect(JSON.parse(init?.body as string).topes_rv.max_pct_region).toBe(100)
  })

  it('explica en pantalla que un campo vacío apaga el eje', async () => {
    renderizar()
    expect(screen.getByText(/Un campo vacío apaga ese tope/)).toBeInTheDocument()
  })
})

// --- F-078: las temáticas multidimensionales viajan como filtro_rv ------------------------------

describe('la temática de renta variable', () => {
  it('una temática de un solo rubro (Tecnológicas) viaja por filtro_rv desde F-079, con rubro_rv en null', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.selectOptions(screen.getByLabelText('Temática (CEDEARs)'), 'tecnologicas')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    const cuerpo = JSON.parse(init?.body as string)
    // F-079: Tecnológicas pasó a referenciar el preset compartido de `lib/presetsRv.ts` —mismo
    // `sic_oficina`, mismo conjunto de especies— en vez de un `rubroRv` inline. El backend sigue
    // aceptando las dos formas y las pliega en la misma dimensión (`normalizar_filtro_rv`).
    expect(cuerpo.rubro_rv).toBeNull()
    expect(cuerpo.filtro_rv).toEqual({ modo: 'interseccion', rubros: ['Office of Technology'] })
  })

  it('metales preciosos viaja como filtro_rv en unión, con rubro_rv en null', async () => {
    const fetchMock = mockFetch(200, RESULTADO_OK)
    renderizar()

    await userEvent.type(screen.getByLabelText('Monto a invertir (USD)'), '100000')
    await userEvent.selectOptions(screen.getByLabelText('Temática (CEDEARs)'), 'metales-preciosos')
    await userEvent.click(screen.getByRole('button', { name: 'Armar cartera asistida' }))

    const [, init] = await esperarLlamadaDeArmado(fetchMock)
    const cuerpo = JSON.parse(init?.body as string)
    // Nunca los dos a la vez: `rubro_rv` junto con un `filtro_rv.rubros` distinto es 422.
    expect(cuerpo.rubro_rv).toBeNull()
    expect(cuerpo.filtro_rv).toEqual({
      modo: 'union',
      estrategias_etf: ['activo_fisico'],
      sic_codigos: ['1040'],
      palabras_en_nombre: ['gold', 'silver', 'oro', 'plata'],
    })
  })

  it('muestra la definición del preset elegido, no sólo su nombre', async () => {
    renderizar()

    await userEvent.selectOptions(screen.getByLabelText('Temática (CEDEARs)'), 'metales-preciosos')

    // Un preset que no dice qué deja afuera es magia: la nota nombra el cobre y el uranio.
    expect(screen.getByText(/Deja afuera la minería metálica genérica/)).toBeInTheDocument()
  })
})
