/**
 * En qué orden se apilan las secciones del armador — preferencia de UI, no estado de cartera.
 *
 * Mismo criterio y mismo patrón que `lib/plegado.ts`: va a `localStorage` y no al store del
 * armador, porque el store se serializa para guardar carteras (F-041) y arrastraría una
 * preferencia visual que no le pertenece. `try/catch` porque `localStorage` puede estar bloqueado
 * y eso no tiene que romper la pantalla, sólo dejar el orden de fábrica.
 *
 * **Por qué existe.** El orden estaba clavado en el JSX y dejaba la renta variable última, después
 * de cinco secciones de renta fija. Para quien arma con un 40% en acciones eso es scrollear hasta
 * el fondo en cada iteración. El orden de trabajo lo decide quien arma, no el layout.
 */

import type { SeccionId } from './plegado'

const STORAGE_KEY = 'swaper-armador-orden-v1'

/** El orden de fábrica: el que tenía la página antes de que esto fuera configurable. */
export const ORDEN_DE_FABRICA: readonly SeccionId[] = [
  'cordillera',
  'asistido',
  'cartera',
  'calendario',
  'analisis',
  'rv',
]

/**
 * Reconcilia un orden guardado contra las secciones que existen hoy.
 *
 * Es el corazón del módulo, y hace falta porque el orden guardado es de otra versión de la app:
 * puede nombrar una sección que ya no existe, puede no nombrar una que se agregó después, y puede
 * repetir un id si algo escribió mal. Las tres se resuelven sin perder secciones:
 *
 * - lo guardado manda, en su orden, para las que siguen existiendo;
 * - las que existen y no estaban guardadas van **al final**, en su orden de fábrica — nunca se
 *   pierden, que es lo único inaceptable: una sección que no se renderiza es una función que
 *   desaparece sin aviso;
 * - los ids desconocidos o repetidos se descartan.
 */
export function reconciliarOrden(
  guardado: readonly string[],
  disponibles: readonly SeccionId[] = ORDEN_DE_FABRICA,
): SeccionId[] {
  const validos = new Set<string>(disponibles)
  const vistos = new Set<string>()
  const ordenado: SeccionId[] = []

  for (const id of guardado) {
    if (!validos.has(id) || vistos.has(id)) continue
    vistos.add(id)
    ordenado.push(id as SeccionId)
  }
  for (const id of disponibles) {
    if (!vistos.has(id)) ordenado.push(id)
  }
  return ordenado
}

export function leerOrden(disponibles: readonly SeccionId[] = ORDEN_DE_FABRICA): SeccionId[] {
  try {
    const crudo = localStorage.getItem(STORAGE_KEY)
    if (!crudo) return [...disponibles]
    const lista = JSON.parse(crudo) as unknown
    if (!Array.isArray(lista)) return [...disponibles]
    return reconciliarOrden(
      lista.filter((v): v is string => typeof v === 'string'),
      disponibles,
    )
  } catch {
    return [...disponibles]
  }
}

export function guardarOrden(orden: readonly SeccionId[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...orden]))
  } catch {
    // Sin persistencia el orden vale para esta sesión; no es motivo para romper la interfaz.
  }
}

export function olvidarOrden(): void {
  try {
    localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ídem: volver al orden de fábrica en pantalla ya ocurrió, lo único que falla es recordarlo.
  }
}

/**
 * El mismo orden con `id` movido un lugar arriba o abajo. Devuelve una lista nueva; en los bordes
 * devuelve la original sin tocar (mover el primero hacia arriba no es un error, es un no-op).
 */
export function moverSeccion(
  orden: readonly SeccionId[],
  id: SeccionId,
  direccion: 'arriba' | 'abajo',
): SeccionId[] {
  const desde = orden.indexOf(id)
  if (desde === -1) return [...orden]
  const hasta = direccion === 'arriba' ? desde - 1 : desde + 1
  if (hasta < 0 || hasta >= orden.length) return [...orden]

  const proximo = [...orden]
  ;[proximo[desde], proximo[hasta]] = [proximo[hasta], proximo[desde]]
  return proximo
}
