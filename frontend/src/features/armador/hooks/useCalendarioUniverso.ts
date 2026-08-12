/**
 * La grilla de doce meses del universo, sobre el endpoint de F-015 — F-016.
 *
 * `staleTime` sale de `TIEMPOS.mercado` y no de uno propio: el calendario se calcula sobre
 * paridades y cronogramas del snapshot del día, así que un refresh de precios lo invalida igual
 * que a un precio (ver el comentario de `calendarioUniverso` en `lib/api/queryKeys.ts`).
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaCalendarioUniverso } from '../lib/schema'

export function useCalendarioUniverso() {
  return useQuery({
    queryKey: claves.mercado.calendarioUniverso,
    queryFn: () =>
      apiFetch('/api/v1/calendario/universo?detalle=true', esquemaCalendarioUniverso),
    ...TIEMPOS.mercado,
    // Mismo criterio que `useEstadoDelDato`: un 4xx/5xx acá es un estado normal y esperable del
    // backend, no una excepción a reintentar en el momento — se muestra tal cual.
    retry: false,
  })
}
