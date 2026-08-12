/**
 * Consumo de las colecciones paginadas de la API.
 *
 * El backend nunca devuelve el conjunto completo: entrega una página y un cursor para pedir la
 * siguiente. Este hook encapsula ese ida y vuelta para que ninguna feature tenga que manejar
 * cursores a mano.
 */

import { useInfiniteQuery } from '@tanstack/react-query'
import type { QueryKey } from '@tanstack/react-query'
import type { z } from 'zod'

import { apiFetch } from './client'
import { esquemaPagina } from './schemas'

export function usePaginaQuery<T>(opciones: {
  queryKey: QueryKey
  ruta: string
  esquemaItem: z.ZodType<T>
  /** Filtros y demás; el cursor lo administra el hook. */
  params?: Record<string, string | number | undefined>
  limit?: number
  enabled?: boolean
  staleTime?: number
}) {
  const { queryKey, ruta, esquemaItem, params, limit, enabled, staleTime } = opciones
  const esquema = esquemaPagina(esquemaItem)

  const query = useInfiniteQuery({
    queryKey,
    enabled,
    staleTime,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const busqueda = new URLSearchParams()
      for (const [clave, valor] of Object.entries(params ?? {})) {
        if (valor !== undefined) busqueda.set(clave, String(valor))
      }
      if (limit !== undefined) busqueda.set('limit', String(limit))
      // El cursor viaja tal como llegó. Es opaco por contrato: acá no se decodifica ni se inspecciona.
      if (pageParam) busqueda.set('cursor', pageParam)

      const consulta = busqueda.toString()
      return apiFetch(consulta ? `${ruta}?${consulta}` : ruta, esquema)
    },
    // `next_cursor` es null en la última página, que es como useInfiniteQuery sabe que terminó.
    getNextPageParam: (ultima) => ultima.next_cursor,
  })

  return {
    items: query.data?.pages.flatMap((pagina) => pagina.items) ?? [],
    cargarMas: query.fetchNextPage,
    hayMas: query.hasNextPage,
    cargandoMas: query.isFetchingNextPage,
    cargando: query.isPending,
    error: query.error,
    reintentar: query.refetch,
  }
}
