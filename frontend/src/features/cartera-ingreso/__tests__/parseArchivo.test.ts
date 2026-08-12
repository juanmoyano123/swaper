import { describe, expect, it, vi } from 'vitest'

vi.mock('read-excel-file/browser', () => ({
  readSheet: vi.fn(async () => [
    ['Especie', 'Nominal'],
    ['AL30D', 1200],
    ['GD35', 850.5],
  ]),
}))

import { readSheet } from 'read-excel-file/browser'

import { leerArchivo } from '../lib/parseArchivo'

describe('leerArchivo', () => {
  it('lee un CSV como texto y lo divide en filas', async () => {
    const archivo = new File(['Especie,Nominal\nAL30D,1200'], 'cartera.csv', { type: 'text/csv' })
    const filas = await leerArchivo(archivo)
    expect(filas).toEqual([
      ['Especie', 'Nominal'],
      ['AL30D', '1200'],
    ])
  })

  it('delega un .xlsx en read-excel-file y convierte cada celda a texto', async () => {
    const archivo = new File(['contenido binario simulado'], 'cartera.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const filas = await leerArchivo(archivo)
    expect(readSheet).toHaveBeenCalledWith(archivo)
    // El número que devuelve read-excel-file para una celda numérica se pasa a texto plano, así
    // el resto del pipeline lo interpreta con la misma `parseNumeroArg` que usa un CSV.
    expect(filas).toEqual([
      ['Especie', 'Nominal'],
      ['AL30D', '1200'],
      ['GD35', '850.5'],
    ])
  })

  it('rechaza un formato que no reconoce', async () => {
    const archivo = new File(['x'], 'cartera.pdf', { type: 'application/pdf' })
    await expect(leerArchivo(archivo)).rejects.toThrow(/no se reconoce/)
  })
})
