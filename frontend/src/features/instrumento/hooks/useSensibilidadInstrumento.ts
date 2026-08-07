/**
 * La sensibilidad del precio por repricing completo — F-040.
 *
 * Query independiente con `retry: false`, mismo régimen que las otras tres de la ficha: una falla
 * acá no puede tumbar la ficha de precios.
 *
 * Cuelga del prefijo `mercado`, no de `referencia`: la sensibilidad depende de la TIR vigente, que
 * cambia con cada refresh de precios, y `referencia` tiene `staleTime: Infinity` — dejaría en
 * pantalla una tabla calculada sobre una TIR vieja sin que nadie lo note. Es el criterio inverso al
 * del cronograma (cambia por ingesta, no por precio) y por el mismo motivo.
 *
 * `queryKeys.ts` está prohibido editar para esta feature: la clave se deriva del prefijo con el
 * mismo gesto que `useCronogramaInstrumento.ts` y `useSegmentos.ts`.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaSensibilidad } from '../lib/schema'

export function useSensibilidadInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: [...claves.mercado.todas, 'sensibilidad', ticker ?? ''] as const,
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}/sensibilidad`, esquemaSensibilidad),
    enabled: ticker !== undefined,
    staleTime: TIEMPOS.mercado.staleTime,
    retry: false,
  })
}
