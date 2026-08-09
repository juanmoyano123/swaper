/**
 * El universo entero, para resolver precio/moneda/emisor por ticker — F-018.
 *
 * Movido acá en la Tanda 11 desde `features/armador/hooks/useEspeciesUniverso.ts`, para que el
 * diagnóstico de cartera (F-030) comparta el mismo fetch (y el mismo caché de TanStack Query) que
 * el armador en vez de pedir el universo por su cuenta.
 *
 * La clave no sale de `claves.mercado.universo(segmento)`: esa clave es del monitor y significa
 * "un segmento filtrado"; acá se pide el universo sin filtrar, y es una clave distinta aunque
 * cuelgue del mismo prefijo `mercado`.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'

import { traerUniversoEntero } from '../traerUniversoEntero'

export function useEspeciesUniverso() {
  return useQuery({
    queryKey: ['mercado', 'universo', 'todas'] as const,
    queryFn: traerUniversoEntero,
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
