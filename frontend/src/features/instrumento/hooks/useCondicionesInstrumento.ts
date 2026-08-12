/**
 * Las condiciones de emisión curadas de un ticker — F-039.
 *
 * Consulta independiente de la ficha de precios: cuelga de `referencia` porque el dato curado
 * cambia por ingesta y no por reloj, igual criterio que `condiciones` en `queryKeys.ts`.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaCondiciones } from '../lib/schema'

export function useCondicionesInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: claves.referencia.condiciones(ticker ?? ''),
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}/condiciones`, esquemaCondiciones),
    enabled: ticker !== undefined,
    retry: false,
  })
}
