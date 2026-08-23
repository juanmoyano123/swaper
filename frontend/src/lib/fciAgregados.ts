/**
 * Contrato, fetch y hooks de los agregados de FCI (categorías y gestoras) — F-067.
 *
 * En `lib/`, mismo criterio que `fci.ts`: dominio compartido, no atado a `features/fci/`.
 */

import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { TIEMPOS } from '@/app/queryClient'

import { apiFetch } from './api/client'
import { claves } from './api/queryKeys'

const esquemaBloqueMonedaCategoria = z.object({
  moneda: z.string(),
  /** `null` cuando ningún fondo del bloque informó patrimonio — nunca 0. */
  aum: z.number().nullable(),
  cantidad_fondos: z.number(),
  fondos: z.array(
    z.object({
      codigo_cafci: z.string(),
      fondo: z.string(),
      patrimonio: z.number().nullable(),
      /** Contra el AUM de esta misma moneda, nunca contra un total que mezcle monedas (regla 3). */
      participacion_pct: z.number().nullable(),
    }),
  ),
})

export const esquemaCategoriaFci = z.object({
  tipo_renta: z.string(),
  cantidad_fondos: z.number(),
  por_moneda: z.array(esquemaBloqueMonedaCategoria),
})

export type CategoriaFci = z.infer<typeof esquemaCategoriaFci>

const esquemaRespuestaCategorias = z.object({ categorias: z.array(esquemaCategoriaFci) })

const esquemaBloqueMonedaGestora = z.object({
  moneda: z.string(),
  aum: z.number().nullable(),
  cantidad_fondos: z.number(),
})

const esquemaFlujoNeto = z.object({
  disponible: z.literal(false),
  motivo: z.string(),
})

export const esquemaGestoraFci = z.object({
  /** `null` = gerente no informado en la planilla, agrupado aparte — no es una gestora real. */
  gerente: z.string().nullable(),
  cantidad_fondos: z.number(),
  por_moneda: z.array(esquemaBloqueMonedaGestora),
  market_share: z.number().nullable(),
  /** Siempre declarado: el producto no acumula planillas históricas (decisión del 23/08/2026). */
  flujo_neto: esquemaFlujoNeto,
})

export type GestoraFci = z.infer<typeof esquemaGestoraFci>

const esquemaRespuestaGestoras = z.object({ gestoras: z.array(esquemaGestoraFci) })

export function useCategoriasFci() {
  return useQuery({
    queryKey: claves.mercado.fci.agregados.categorias,
    queryFn: () => apiFetch('/api/v1/fci/agregados/categorias', esquemaRespuestaCategorias),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}

export function useGestorasFci() {
  return useQuery({
    queryKey: claves.mercado.fci.agregados.gestoras,
    queryFn: () => apiFetch('/api/v1/fci/agregados/gestoras', esquemaRespuestaGestoras),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
