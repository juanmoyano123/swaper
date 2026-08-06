/** Estado del backend, sondeado cada minuto para que la barra superior no mienta. */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import { esquemaSalud } from '@/lib/api/schemas'

export function useSalud() {
  return useQuery({
    queryKey: claves.salud,
    queryFn: () => apiFetch('/api/v1/health', esquemaSalud),
    ...TIEMPOS.salud,
    // Que el backend esté caído es un estado normal y esperable, no una excepción a reintentar
    // varias veces: se muestra tal cual y el próximo sondeo lo corrige solo.
    retry: false,
  })
}
