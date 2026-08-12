/**
 * El cronograma de pagos de un ticker — F-039.
 *
 * Sin clave reservada en `queryKeys.ts` (el plan la deja fuera a propósito): cuelga de `referencia`
 * por el mismo motivo que las condiciones — el cashflow cambia por ingesta, no por el paso del
 * tiempo — y no de `mercado`, que es lo que invalida el refresh de precios.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaCronograma } from '../lib/schema'

export function useCronogramaInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: [...claves.referencia.todas, 'cronograma', ticker ?? ''] as const,
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}/cronograma`, esquemaCronograma),
    enabled: ticker !== undefined,
    retry: false,
  })
}
