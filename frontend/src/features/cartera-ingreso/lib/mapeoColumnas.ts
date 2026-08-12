/**
 * Reconocimiento de encabezados por nombre, para no obligar al asesor a mapear a mano una columna
 * que dice literalmente "Nominal".
 *
 * Sirve para dos cosas distintas: precargar el selector de mapeo con una propuesta (que el asesor
 * siempre puede corregir), y decidir si un texto pegado trae encabezado reconocible o hay que
 * pedirlo. Lo que NO hace es inferir nada del contenido de las celdas ni de la posición de la
 * columna — solo compara el nombre del encabezado contra una lista fija de sinónimos conocidos.
 */

import type { CampoPosicion, MapeoColumnas } from '../types'

const SINONIMOS: Record<Exclude<CampoPosicion, 'ignorar'>, string[]> = {
  ticker: ['ticker', 'especie', 'simbolo', 'símbolo', 'instrumento', 'activo', 'papel', 'codigo', 'código'],
  nominal: ['nominal', 'cantidad', 'vn', 'valor nominal', 'v.n.', 'tenencia', 'nominales', 'cant'],
  monto: ['monto', 'importe', 'valuacion', 'valuación', 'valor', 'total', 'saldo'],
}

function normalizar(texto: string): string {
  return texto
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
}

/** A qué campo corresponde un encabezado, si alguno de los sinónimos conocidos lo nombra. */
function reconocerCampo(encabezado: string): CampoPosicion {
  const norm = normalizar(encabezado)
  for (const [campo, sinonimos] of Object.entries(SINONIMOS) as [
    Exclude<CampoPosicion, 'ignorar'>,
    string[],
  ][]) {
    if (sinonimos.some((s) => normalizar(s) === norm)) return campo
  }
  return 'ignorar'
}

/**
 * Intenta mapear cada columna por su nombre de encabezado. Devuelve `null` cuando la fila no trae
 * ni una columna de ticker ni una numérica reconocible — en ese caso no hay encabezado del que
 * partir, y el mapeo lo tiene que decidir el asesor.
 */
export function intentarMapeoAutomatico(encabezados: string[]): MapeoColumnas | null {
  const mapeo = encabezados.map(reconocerCampo)
  const tieneTicker = mapeo.includes('ticker')
  const tieneNumerico = mapeo.includes('nominal') || mapeo.includes('monto')
  if (!tieneTicker || !tieneNumerico) return null
  return mapeo
}

/** Mapeo de partida cuando no hay ninguna pista: todo sin asignar, a elegir a mano. */
export function mapeoVacio(cantidadColumnas: number): MapeoColumnas {
  return Array.from({ length: cantidadColumnas }, () => 'ignorar')
}

/**
 * Un mapeo alcanza para construir posiciones cuando señala una única columna de ticker y al menos
 * una columna numérica (nominal o monto, los dos también vale). Dos columnas para el mismo campo
 * son un mapeo ambiguo, no una posición con doble dato: se rechaza en vez de quedarse con la
 * primera y descartar la segunda en silencio.
 */
export function mapeoCompleto(mapeo: MapeoColumnas): boolean {
  const cuenta = (campo: CampoPosicion) => mapeo.filter((c) => c === campo).length
  return cuenta('ticker') === 1 && cuenta('nominal') <= 1 && cuenta('monto') <= 1 && cuenta('nominal') + cuenta('monto') >= 1
}
