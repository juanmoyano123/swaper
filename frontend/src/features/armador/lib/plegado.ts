/**
 * Qué secciones del armador están plegadas — preferencia de UI, no estado de cartera.
 *
 * Va a `localStorage` y no al store del armador (`carteraStore.tsx`) a propósito: F-041 (tanda 17)
 * va a persistir la forma exacta del store para guardar/reabrir carteras, y si el plegado viviera
 * ahí, cada cartera guardada arrastraría una preferencia visual de sesión que no le pertenece.
 * Mismo patrón que `lib/theme.ts` — `try/catch` porque `localStorage` puede estar bloqueado
 * (modo privado, permisos) y eso no tiene que romper la pantalla, sólo dejar todo abierto.
 */

export type SeccionId = 'cordillera' | 'asistido' | 'cartera' | 'calendario' | 'analisis' | 'rv'

const STORAGE_KEY = 'swaper-armador-plegadas-v1'

export function leerPlegadas(): Set<SeccionId> {
  try {
    const crudo = localStorage.getItem(STORAGE_KEY)
    if (!crudo) return new Set()
    const lista = JSON.parse(crudo) as unknown
    if (!Array.isArray(lista)) return new Set()
    return new Set(lista.filter((v): v is SeccionId => typeof v === 'string'))
  } catch {
    return new Set()
  }
}

export function guardarPlegadas(plegadas: ReadonlySet<SeccionId>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...plegadas]))
  } catch {
    // Sin persistencia el plegado vale para esta sesión; no es motivo para romper la interfaz.
  }
}
