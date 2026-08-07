/**
 * La especie pedida más sus hermanas de liquidación — F-039.
 *
 * `retry: false`, igual que las otras dos queries de esta ficha: el test de rutas monta el drawer
 * sobre `/armador` con un `fetch` que sólo responde el health, así que esta consulta tiene que fallar
 * una vez y quedarse en error, no reintentar y disparar un warning de act() en el medio.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaFicha } from '../lib/schema'

export function useFichaInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: claves.mercado.instrumento(ticker ?? ''),
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}`, esquemaFicha),
    enabled: ticker !== undefined,
    retry: false,
  })
}
