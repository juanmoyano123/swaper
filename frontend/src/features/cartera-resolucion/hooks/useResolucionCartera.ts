/**
 * La resolución de la cartera cargada contra el universo del día — F-029.
 *
 * Es una consulta y no una mutación aunque el verbo sea POST: no escribe nada, es determinística
 * sobre el universo del día y dos pantallas que muestren la misma cartera tienen que ver lo mismo.
 * El POST es por el cuerpo —las tenencias de un cliente no van en una query string, que se
 * persiste en los logs de acceso y en el historial del navegador—, no por el efecto.
 *
 * Cuelga de `claves.mercado` a propósito: lo que resuelve un ticker es el universo de la corrida
 * de ingesta, así que el refresh de precios de F-013 la invalida por prefijo sin tener que
 * acordarse de esta feature.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { claves } from '@/lib/api/queryKeys'

import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import { firmaDeCartera, resolverCartera } from '../lib/resolverCartera'

export function useResolucionCartera(posiciones: PosicionCruda[]) {
  return useQuery({
    queryKey: claves.mercado.resolucion(firmaDeCartera(posiciones)),
    queryFn: () => resolverCartera(posiciones),
    ...TIEMPOS.mercado,
    // Una cartera vacía no se manda: no hay nada que resolver y el backend contestaría un
    // diagnóstico de cero posiciones que la pantalla no tiene por qué pedir.
    enabled: posiciones.length > 0,
  })
}
