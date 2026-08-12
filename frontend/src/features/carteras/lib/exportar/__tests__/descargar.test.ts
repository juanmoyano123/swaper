import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ContextoExport } from '../modelo'
import { descargarBlob, nombreDeArchivo } from '../descargar'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('descargarBlob', () => {
  it('crea un object URL, dispara la descarga y lo libera', () => {
    const url = 'blob:mock-url'
    const crear = vi.spyOn(URL, 'createObjectURL').mockReturnValue(url)
    const revocar = vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {})
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    descargarBlob(new Blob(['x']), 'archivo.xlsx')

    expect(crear).toHaveBeenCalledTimes(1)
    expect(click).toHaveBeenCalledTimes(1)
    expect(revocar).toHaveBeenCalledWith(url)
  })
})

describe('nombreDeArchivo', () => {
  const contexto: ContextoExport = {
    nombre: 'Renta USD · perfil moderado',
    descripcion: null,
    snapshotEn: '2026-08-10T12:00:00Z',
    generadoEn: '2026-08-10T13:30:00Z',
  }

  it('combina el nombre, la fecha del snapshot y la extensión', () => {
    expect(nombreDeArchivo(contexto, 'xlsx')).toBe('Renta USD · perfil moderado - 2026-08-10.xlsx')
    expect(nombreDeArchivo(contexto, 'pdf')).toBe('Renta USD · perfil moderado - 2026-08-10.pdf')
  })

  it('reemplaza caracteres inválidos de un path, no los deja pasar', () => {
    const conBarra: ContextoExport = { ...contexto, nombre: 'Renta USD / perfil "moderado"' }
    expect(nombreDeArchivo(conBarra, 'xlsx')).toBe('Renta USD - perfil -moderado- - 2026-08-10.xlsx')
  })
})
