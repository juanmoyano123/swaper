/**
 * El orden de las secciones del armador, y cómo moverlas. Ver `lib/ordenSecciones.ts` para el
 * porqué de guardarlo en `localStorage` y no en el store de la cartera.
 *
 * Mismo patrón que `useSeccionPlegada`: sin caché a nivel de módulo — cada lectura vuelve a
 * `localStorage`, así que un `localStorage.clear()` externo (el que hace `src/test/setup.ts` entre
 * tests) no deja un valor viejo pisando al de verdad.
 */

import { useCallback, useSyncExternalStore } from 'react'

import type { SeccionId } from '../lib/plegado'
import {
  guardarOrden,
  leerOrden,
  moverSeccion,
  olvidarOrden,
  ORDEN_DE_FABRICA,
} from '../lib/ordenSecciones'

const suscriptores = new Set<() => void>()

function suscribir(alCambiar: () => void): () => void {
  suscriptores.add(alCambiar)
  return () => suscriptores.delete(alCambiar)
}

function avisar(): void {
  suscriptores.forEach((f) => f())
}

/** Serializado para que `useSyncExternalStore` pueda comparar por identidad: `leerOrden` devuelve
 *  un array nuevo en cada llamada, y devolverlo directo haría que React lo vea siempre distinto y
 *  entre en un bucle de renders. Se compara el string y se parsea una sola vez al final. */
function instantanea(): string {
  return leerOrden().join(',')
}

export function useOrdenSecciones(): {
  orden: SeccionId[]
  mover: (id: SeccionId, direccion: 'arriba' | 'abajo') => void
  restaurar: () => void
  esDeFabrica: boolean
} {
  const serializado = useSyncExternalStore(suscribir, instantanea, () =>
    ORDEN_DE_FABRICA.join(','),
  )
  const orden = serializado.split(',') as SeccionId[]

  const mover = useCallback((id: SeccionId, direccion: 'arriba' | 'abajo') => {
    guardarOrden(moverSeccion(leerOrden(), id, direccion))
    avisar()
  }, [])

  const restaurar = useCallback(() => {
    olvidarOrden()
    avisar()
  }, [])

  return { orden, mover, restaurar, esDeFabrica: serializado === ORDEN_DE_FABRICA.join(',') }
}
