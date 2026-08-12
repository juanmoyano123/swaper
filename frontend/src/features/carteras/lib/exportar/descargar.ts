/**
 * F-042 — el mecanismo de descarga en el navegador. No existía ninguno en el proyecto antes de
 * esta feature: `createObjectURL` + un `<a download>` sintético es el patrón estándar, sin
 * dependencias nuevas. `revokeObjectURL` libera la memoria del blob apenas el click dispara la
 * descarga — no hace falta esperar a que termine, el navegador ya tomó los bytes.
 */

import type { ContextoExport } from './modelo'

export function descargarBlob(blob: Blob, nombreArchivo: string): void {
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  document.body.removeChild(enlace)
  URL.revokeObjectURL(url)
}

const CARACTERES_INVALIDOS = /[\\/:*?"<>|]/g

/** El nombre de archivo no puede llevar los caracteres que Windows/macOS prohíben en un path —
 *  un nombre de cartera con "/" (p. ej. "Renta USD / perfil moderado") rompería la descarga. */
function nombreSeguro(texto: string): string {
  return texto.replace(CARACTERES_INVALIDOS, '-').trim()
}

export function nombreDeArchivo(contexto: ContextoExport, extension: 'xlsx' | 'pdf'): string {
  const fecha = contexto.snapshotEn.slice(0, 10) // yyyy-mm-dd, siempre disponible (ISO)
  return `${nombreSeguro(contexto.nombre)} - ${fecha}.${extension}`
}
