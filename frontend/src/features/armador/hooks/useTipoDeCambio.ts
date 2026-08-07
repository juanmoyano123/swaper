/**
 * El MEP implícito de F-012, para normalizar a dólares lo que cotiza en pesos — F-018.
 *
 * Misma nota que `useEspeciesUniverso`: la clave se define acá y no en `lib/api/queryKeys.ts`
 * (de sólo lectura para esta feature), colgando del mismo prefijo `mercado` para que el refresh
 * de precios la invalide igual que a cualquier otro dato de mercado.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'

import { esquemaTipoDeCambio } from '../lib/schema'

export function useTipoDeCambio() {
  return useQuery({
    queryKey: ['mercado', 'tipo-de-cambio'] as const,
    queryFn: () => apiFetch('/api/v1/universo/tipo-de-cambio', esquemaTipoDeCambio),
    ...TIEMPOS.mercado,
    retry: false,
  })
}
