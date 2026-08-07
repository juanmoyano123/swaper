/**
 * El calendario de doce meses de la cartera en construcción — F-018, sobre F-015/F-029.
 *
 * Mismo endpoint que alimenta el panel de renta de F-021; acá sólo se usa para el mini-calendario
 * de cada fila y para las alertas (`fuera_del_universo` incluida). `esquemaCalendarioUniverso` se
 * importa de F-016: es el mismo contrato de respuesta que ya usa `/calendario/universo`.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { firmaDeCartera } from '../lib/firmaDeCartera'
import { esquemaCalendarioUniverso } from '../lib/schema'

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
