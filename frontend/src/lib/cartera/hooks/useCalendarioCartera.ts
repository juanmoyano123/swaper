/**
 * El calendario de doce meses de una cartera de posiciones explícitas — F-018/F-021, sobre F-015.
 *
 * Movido acá en la Tanda 11 desde `features/armador/hooks/useCalendarioCartera.ts`, para que el
 * diagnóstico de cartera (F-030) pida la renta con el mismo endpoint y el mismo criterio de caché
 * que el armador (riesgo R12 de `plan.md:2774`). El endpoint es POST-que-es-lectura: las
 * posiciones viajan explícitas en el cuerpo, nunca por id de cartera — sirve igual para una
 * cartera guardada, una propuesta que todavía no existe, o una cartera cargada por F-029.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { firmaDeCartera } from '../firmaDeCartera'
import { esquemaCalendarioUniverso } from '../esquemaCalendario'

export function useCalendarioCartera(posiciones: { ticker: string; monto: number }[]) {
  const firma = firmaDeCartera(posiciones)
  return useQuery({
    queryKey: claves.mercado.calendarioCartera(firma),
    queryFn: () =>
      apiFetch('/api/v1/calendario/cartera?detalle=true', esquemaCalendarioUniverso, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          posiciones: posiciones.map((p) => ({ ticker: p.ticker, monto: p.monto })),
        }),
      }),
    // El endpoint exige al menos una posición (`min_length=1`): con la lista vacía daría 422, así
    // que nunca se llama vacía.
    enabled: posiciones.length > 0,
    ...TIEMPOS.mercado,
    retry: false,
  })
}
