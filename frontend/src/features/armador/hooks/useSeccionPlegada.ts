/**
 * Si una sección del armador está plegada, y cómo alternarla. Ver `lib/plegado.ts` para el porqué
 * de guardar esto en `localStorage` y no en el store de la cartera.
 *
 * Mismo patrón que `lib/theme.ts`: no hay estado cacheado a nivel de módulo — cada lectura vuelve
 * a `localStorage`, así que un `localStorage.clear()` externo (como el que hace
 * `src/test/setup.ts` entre tests) no deja un valor viejo pisando al de verdad.
 */

import { useCallback, useSyncExternalStore } from 'react'

import { guardarPlegadas, leerPlegadas, type SeccionId } from '../lib/plegado'

const suscriptores = new Set<() => void>()

function suscribir(alCambiar: () => void): () => void {
  suscriptores.add(alCambiar)
  return () => suscriptores.delete(alCambiar)
}

export function useSeccionPlegada(id: SeccionId): [plegada: boolean, alternar: () => void] {
  const plegada = useSyncExternalStore(
    suscribir,
    () => leerPlegadas().has(id),
    () => false,
  )

  const alternar = useCallback(() => {
    const proximo = leerPlegadas()
    if (proximo.has(id)) proximo.delete(id)
    else proximo.add(id)
    guardarPlegadas(proximo)
    suscriptores.forEach((f) => f())
  }, [id])

  return [plegada, alternar]
}
