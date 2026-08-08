/**
 * La ficha de una acción o un CEDEAR — F-053.
 *
 * Cuelga del prefijo `mercado` porque el bloque propio es precio de BYMA: un refresh de precios
 * tiene que invalidarla. La clave se deriva del prefijo en vez de agregarse a `queryKeys.ts`, mismo
 * criterio que `useSensibilidadInstrumento` (F-040) — así el refresh la alcanza igual sin tocar un
 * archivo compartido.
 *
 * `retry: false` por dos motivos que se suman. El primero es el de siempre en esta ficha: una falla
 * no puede quedar reintentando en pantalla. El segundo es propio de F-053: **el 404 de este endpoint
 * es información**, no un fallo — es cómo se sabe que el ticker no es renta variable y que la ficha
 * que corresponde es la de renta fija. Reintentarlo sería demorar tres veces una respuesta correcta.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaFichaRentaVariable } from '../lib/schemaRentaVariable'

export function useFichaRentaVariable(ticker: string | undefined) {
  return useQuery({
    queryKey: [...claves.mercado.todas, 'renta-variable', 'ficha', ticker ?? ''] as const,
    queryFn: () =>
      apiFetch(`/api/v1/renta-variable/${ticker}/ficha`, esquemaFichaRentaVariable),
    enabled: ticker !== undefined,
    retry: false,
  })
}
