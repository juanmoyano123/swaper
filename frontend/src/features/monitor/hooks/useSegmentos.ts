/**
 * De dónde saca el monitor sus pestañas de segmento — F-038.
 *
 * Cuelga del prefijo `mercado` con una clave propia (`'segmentos'` al final): así el refresh de
 * precios la invalida junto con el universo del que sale, sin tocar `queryKeys.ts`, que es de otra
 * feature. No es `claves.mercado.universo('segmentos')` — esa clave dice "el universo del segmento
 * llamado segmentos", que no es lo que este endpoint contesta.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaSegmentos } from '../lib/schema'

export function useSegmentos() {
  return useQuery({
    queryKey: [...claves.mercado.todas, 'segmentos'],
    queryFn: () => apiFetch('/api/v1/universo/segmentos', esquemaSegmentos),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
