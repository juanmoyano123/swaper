/**
 * `BotonExportar` — F-042. Los generadores reales (`excel.ts`/`pdf.ts`) cargan librerías pesadas
 * con `import()` dinámico; acá se mockean enteros para probar sólo la orquestación: qué genera,
 * qué descarga, y que un error de generación se muestra en vez de tragarse en silencio.
 */

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

const generarExcelMock = vi.fn()
const generarPdfMock = vi.fn()
const descargarBlobMock = vi.fn()

vi.mock('../lib/exportar/excel', () => ({ generarExcel: (modelo: unknown) => generarExcelMock(modelo) }))
vi.mock('../lib/exportar/pdf', () => ({ generarPdf: (modelo: unknown) => generarPdfMock(modelo) }))
vi.mock('../lib/exportar/descargar', () => ({
  descargarBlob: (blob: unknown, nombre: string) => descargarBlobMock(blob, nombre),
  nombreDeArchivo: (_contexto: unknown, ext: string) => `archivo.${ext}`,
}))

import { BotonExportar } from '../components/BotonExportar'
import type { SnapshotArmador } from '../lib/esquemaSnapshot'
import type { ContextoExport } from '../lib/exportar/modelo'

afterEach(() => {
  vi.clearAllMocks()
})

const snapshot: SnapshotArmador = {
  version: 1,
  origen: 'armador',
  tipoDeCambio: 1050,
  montoTotalUsd: 10_000,
  posiciones: [{ ticker: 'AL30D', peso: 100, clase: 'renta_fija' }],
  resueltas: [
    { ticker: 'AL30D', clase: 'renta_fija', peso: 100, moneda: 'usd', precio: 70, vn: 14_285.7, cantidad: null, invertido: 10_000, invertidoUsd: 10_000 },
  ],
  totalInvertidoUsd: 10_000,
}

const contexto: ContextoExport = {
  nombre: 'Renta USD · perfil moderado',
  descripcion: null,
  snapshotEn: '2026-08-10T12:00:00Z',
  generadoEn: '2026-08-10T13:00:00Z',
}

describe('BotonExportar', () => {
  it('«Descargar Excel» arma el modelo, genera el archivo y lo descarga', async () => {
    generarExcelMock.mockResolvedValue(new Blob(['x']))
    const usuario = userEvent.setup()
    render(<BotonExportar snapshot={snapshot} contexto={contexto} />)

    await usuario.click(screen.getByRole('button', { name: 'Descargar Excel' }))

    await waitFor(() => expect(descargarBlobMock).toHaveBeenCalledTimes(1))
    expect(generarExcelMock).toHaveBeenCalledTimes(1)
    expect(generarPdfMock).not.toHaveBeenCalled()
    expect(descargarBlobMock).toHaveBeenCalledWith(expect.any(Blob), 'archivo.xlsx')
  })

  it('«Descargar PDF» genera el archivo y lo descarga, sin tocar el generador de Excel', async () => {
    generarPdfMock.mockResolvedValue(new Blob(['x']))
    const usuario = userEvent.setup()
    render(<BotonExportar snapshot={snapshot} contexto={contexto} />)

    await usuario.click(screen.getByRole('button', { name: 'Descargar PDF' }))

    await waitFor(() => expect(descargarBlobMock).toHaveBeenCalledWith(expect.any(Blob), 'archivo.pdf'))
    expect(generarExcelMock).not.toHaveBeenCalled()
  })

  it('un error al generar el archivo se muestra, no se traga en silencio', async () => {
    generarExcelMock.mockRejectedValue(new Error('no se pudo generar el archivo'))
    const usuario = userEvent.setup()
    render(<BotonExportar snapshot={snapshot} contexto={contexto} />)

    await usuario.click(screen.getByRole('button', { name: 'Descargar Excel' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('no se pudo generar el archivo')
    expect(descargarBlobMock).not.toHaveBeenCalled()
  })
})
