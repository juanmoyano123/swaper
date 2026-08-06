/**
 * Los tres GIVEN/WHEN/THEN de F-028, de punta a punta a través de la interfaz, más los estados de
 * carga, error y renderizado base que le corresponden a cualquier feature.
 */

import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('read-excel-file/browser', () => ({
  readSheet: vi.fn(),
}))

import { readSheet } from 'read-excel-file/browser'

import { IngresoCarteraPanel } from '../components/IngresoCarteraPanel'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('estado inicial', () => {
  it('muestra las tres vías de ingreso y ninguna otra cosa', () => {
    render(<IngresoCarteraPanel />)
    expect(screen.getByRole('button', { name: /Pegar desde el portapapeles/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Subir un CSV o Excel/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Cargar posición por posición/ })).toBeInTheDocument()
  })
})

describe('vía 1: pegado desde el portapapeles', () => {
  it('un resumen con decimales con coma se previsualiza con la cantidad de filas leídas', async () => {
    const usuario = userEvent.setup()
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Pegar desde el portapapeles/ }))

    const textarea = screen.getByLabelText('Pegá acá el resumen de cuenta.')
    await usuario.type(
      textarea,
      'Ticker\tNominal{Enter}AL30D\t850,50{Enter}GD35\t1.200,00{Enter}MR46O\t3.000',
    )
    await usuario.click(screen.getByRole('button', { name: 'Interpretar' }))

    // Previsualización antes de confirmar, con la cantidad de filas leídas.
    const resumen = await screen.findByText(/Se leyeron/)
    expect(resumen).toHaveTextContent('Se leyeron 3 filas')
    expect(screen.getByRole('button', { name: 'Confirmar cartera' })).toBeInTheDocument()

    // Los tres tickers declarados aparecen tal como se pegaron.
    expect(screen.getByText('AL30D')).toBeInTheDocument()
    expect(screen.getByText('GD35')).toBeInTheDocument()
    expect(screen.getByText('MR46O')).toBeInTheDocument()

    // El decimal con coma se interpretó bien: 850,50 y no 85.050 ni "s/d".
    const fila = screen.getByText('AL30D').closest('tr')
    expect(fila).not.toBeNull()
    expect(within(fila as HTMLElement).getByText('850,50')).toBeInTheDocument()
  })

  it('un pegado sin encabezado reconocible pide el mapeo en vez de asumir el orden', async () => {
    const usuario = userEvent.setup()
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Pegar desde el portapapeles/ }))
    await usuario.type(screen.getByLabelText('Pegá acá el resumen de cuenta.'), 'AL30D\t850,50{Enter}GD35\t1200')
    await usuario.click(screen.getByRole('button', { name: 'Interpretar' }))

    expect(
      await screen.findByText('No se pudo reconocer un encabezado. Decile a cada columna qué campo es.'),
    ).toBeInTheDocument()
  })
})

describe('vía 2: archivo subido', () => {
  it('un CSV con columnas en distinto orden al esperado pide el mapeo en vez de asumir el orden', async () => {
    const usuario = userEvent.setup()
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Subir un CSV o Excel/ }))

    // Nominal antes que Especie: no es el orden "esperado" (ticker primero).
    const contenido = 'Nominal,Especie\n1200,AL30D\n850.50,GD35'
    const archivo = new File([contenido], 'cartera.csv', { type: 'text/csv' })
    await usuario.upload(screen.getByLabelText('Archivo de cartera'), archivo)

    // No hay previsualización directa: hay que confirmar el mapeo primero.
    expect(screen.queryByText(/Se leyeron/)).not.toBeInTheDocument()
    expect(
      await screen.findByText('Se reconocieron algunas columnas por su nombre. Revisá el mapeo antes de continuar.'),
    ).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Confirmar mapeo' }))

    expect(await screen.findByText(/Se leyeron/)).toBeInTheDocument()
    expect(screen.getByText('AL30D')).toBeInTheDocument()
  })

  it('muestra el error si el formato no se reconoce', async () => {
    // `applyAccept: false`: el atributo `accept` del input ya impide elegir un .pdf desde el
    // selector nativo, pero un archivo puede llegar igual con otra extensión por fuera de ese
    // diálogo (arrastrado y soltado, por ejemplo). El guardarraíl de `leerArchivo` es quien tiene
    // que frenarlo, y este test lo ejercita directamente sin depender del filtro del navegador.
    const usuario = userEvent.setup({ applyAccept: false })
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Subir un CSV o Excel/ }))

    const archivo = new File(['contenido'], 'cartera.pdf', { type: 'application/pdf' })
    await usuario.upload(screen.getByLabelText('Archivo de cartera'), archivo)

    expect(await screen.findByRole('alert')).toHaveTextContent(/no se reconoce/)
    // El estado de error no tapa el motivo real con un mensaje genérico.
    expect(screen.getByRole('alert')).toHaveTextContent('cartera.pdf')

    await usuario.click(screen.getByRole('button', { name: 'Volver' }))
    expect(screen.getByLabelText('Archivo de cartera')).toBeInTheDocument()
  })

  it('mientras se lee un .xlsx se muestra el estado de carga', async () => {
    const usuario = userEvent.setup()
    // El tipo real de `readSheet` está sobrecargado para el uso con `schema`, que acá no se usa;
    // se castea el mock a la forma simple que sí usa `leerArchivo` (fila de celdas sueltas).
    let resolver: (filas: (string | number)[][]) => void = () => {}
    vi.mocked(readSheet).mockReturnValue(
      new Promise<(string | number)[][]>((resolve) => (resolver = resolve)) as unknown as ReturnType<
        typeof readSheet
      >,
    )

    render(<IngresoCarteraPanel />)
    await usuario.click(screen.getByRole('button', { name: /Subir un CSV o Excel/ }))

    const archivo = new File(['x'], 'cartera.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    await usuario.upload(screen.getByLabelText('Archivo de cartera'), archivo)

    expect(await screen.findByRole('status')).toHaveTextContent('Cargando el archivo…')

    resolver([
      ['Ticker', 'Nominal'],
      ['AL30D', 100],
    ])

    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument())
  })
})

describe('vía 3: carga manual', () => {
  it('un nominal no numérico se agrega marcado como inválido, con motivo, sin descartarlo', async () => {
    const usuario = userEvent.setup()
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Cargar posición por posición/ }))

    await usuario.type(screen.getByLabelText('Ticker'), 'GD35')
    await usuario.type(screen.getByLabelText('Nominal'), 'no-es-un-numero')
    await usuario.click(screen.getByRole('button', { name: 'Agregar' }))

    // Sigue en la lista, no desapareció.
    expect(screen.getByText('GD35')).toBeInTheDocument()
    expect(screen.getByText(/no-es-un-numero.*no es un número/)).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Confirmar carga' }))

    expect(await screen.findByText(/1 inválida/)).toBeInTheDocument()
    const filaInvalida = screen.getByText('GD35').closest('tr')
    expect(within(filaInvalida as HTMLElement).getByText(/no es un número/)).toBeInTheDocument()
    // Nunca se interpreta como cero: la celda de nominal no muestra "0".
    expect(within(filaInvalida as HTMLElement).queryByText('0')).not.toBeInTheDocument()
  })

  it('permite cargar dos posiciones válidas y confirmar la cartera', async () => {
    const usuario = userEvent.setup()
    render(<IngresoCarteraPanel />)

    await usuario.click(screen.getByRole('button', { name: /Cargar posición por posición/ }))

    await usuario.type(screen.getByLabelText('Ticker'), 'AL30D')
    await usuario.type(screen.getByLabelText('Nominal'), '1000')
    await usuario.click(screen.getByRole('button', { name: 'Agregar' }))

    await usuario.type(screen.getByLabelText('Ticker'), 'GD35')
    await usuario.type(screen.getByLabelText('Monto'), '2.500,75')
    await usuario.click(screen.getByRole('button', { name: 'Agregar' }))

    await usuario.click(screen.getByRole('button', { name: 'Confirmar carga' }))
    expect(await screen.findByText(/Se leyeron/)).toBeInTheDocument()

    await usuario.click(screen.getByRole('button', { name: 'Confirmar cartera' }))

    expect(await screen.findByText(/Cartera cargada: 2 posiciones/)).toBeInTheDocument()
  })
})
