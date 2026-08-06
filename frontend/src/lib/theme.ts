/**
 * Tema oscuro por defecto, con opción de claro que sobrevive a la recarga.
 *
 * El valor se aplica en `data-theme` de <html>, que es donde `index.css` cuelga los tokens. Quien
 * lo fija por primera vez es el script inline de `index.html`, antes de la primera pintura; este
 * módulo mantiene la lógica de acá en adelante y tiene que coincidir con aquél.
 */

import { useCallback, useSyncExternalStore } from 'react'

export const TEMA_STORAGE_KEY = 'swaper-tema'

export type Tema = 'dark' | 'light'

/** Oscuro salvo que haya una preferencia guardada explícita. No se consulta el sistema operativo. */
export function leerTema(): Tema {
  try {
    return localStorage.getItem(TEMA_STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    // Storage bloqueado (modo privado, permisos): el default alcanza para que la app funcione.
    return 'dark'
  }
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.dataset.theme = tema
  try {
    localStorage.setItem(TEMA_STORAGE_KEY, tema)
  } catch {
    // Sin persistencia el tema vale para esta sesión; no es motivo para romper la interfaz.
  }
}

// Los suscriptores permiten que varios componentes lean el tema sin que ninguno sea el dueño.
const suscriptores = new Set<() => void>()

function suscribir(alCambiar: () => void): () => void {
  suscriptores.add(alCambiar)
  return () => suscriptores.delete(alCambiar)
}

function temaActual(): Tema {
  return document.documentElement.dataset.theme === 'light' ? 'light' : 'dark'
}

export function useTema(): { tema: Tema; alternar: () => void } {
  // El servidor nunca renderiza esto (SPA pura), pero useSyncExternalStore exige el tercer
  // argumento y devolver el default es lo correcto para el snapshot inicial.
  const tema = useSyncExternalStore(suscribir, temaActual, () => 'dark' as Tema)

  const alternar = useCallback(() => {
    aplicarTema(temaActual() === 'dark' ? 'light' : 'dark')
    suscriptores.forEach((notificar) => notificar())
  }, [])

  return { tema, alternar }
}
