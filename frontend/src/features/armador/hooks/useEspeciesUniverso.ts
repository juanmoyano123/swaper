/**
 * El universo entero, para resolver precio/moneda/emisor por ticker en `CarteraEditable` — F-018.
 *
 * La clave no sale de `claves.mercado.universo(segmento)`: esa clave es del monitor y significa
 * "un segmento filtrado"; acá se pide el universo sin filtrar, y es una clave distinta aunque
 * cuelgue del mismo prefijo `mercado` (`lib/api/queryKeys.ts` es de sólo lectura para esta
 * feature, así que se define acá en vez de agregarla ahí).
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'

import { traerUniversoEntero } from '../lib/especies'

export function useEspeciesUniverso() {
  return useQuery({
    queryKey: ['mercado', 'universo', 'todas'] as const,
    queryFn: traerUniversoEntero,
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
