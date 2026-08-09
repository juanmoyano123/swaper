/**
 * El MEP implícito de F-012, para normalizar a dólares lo que cotiza en pesos — F-018.
 *
 * Movido acá en la Tanda 11 desde `features/armador/hooks/useTipoDeCambio.ts`, para que el
 * diagnóstico de cartera (F-030) normalice con el mismo TC y el mismo caché que el armador.
 * La clave cuelga del prefijo `mercado` para que el refresh de precios la invalide igual que a
 * cualquier otro dato de mercado.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'

import { esquemaTipoDeCambio } from '../esquemaEspecie'

export function useTipoDeCambio() {
  return useQuery({
    queryKey: ['mercado', 'tipo-de-cambio'] as const,
    queryFn: () => apiFetch('/api/v1/universo/tipo-de-cambio', esquemaTipoDeCambio),
    ...TIEMPOS.mercado,
    retry: false,
  })
}
