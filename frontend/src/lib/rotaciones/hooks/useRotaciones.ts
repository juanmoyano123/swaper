/**
 * F-032 desde el lado de F-033: candidatas de rotación de una cartera contra `POST /rotaciones`.
 *
 * Mismo patrón que `useConcentracion` (POST-que-es-lectura, cacheado por firma de pesos + perfil):
 * el motor no usa el peso de cada posición para nada (rota por ticker, no por tamaño), pero se
 * firma igual con `firmaDePesos` para compartir la misma convención de clave que el resto de
 * `mercado.*` en vez de inventar una firma-sólo-de-tickers para este único caso.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { firmaDePesos, type PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'

import { esquemaRotaciones } from '../esquemaRotaciones'

export function useRotaciones(posiciones: PosicionConPeso[], perfil: NombreDePerfil) {
  return useQuery({
    queryKey: claves.mercado.rotaciones(firmaDePesos(posiciones), perfil),
    queryFn: () =>
      apiFetch(`/api/v1/rotaciones?perfil=${encodeURIComponent(perfil)}`, esquemaRotaciones, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posiciones: posiciones.map((p) => ({ ticker: p.ticker })) }),
      }),
    // El endpoint exige al menos una posición (`min_length=1`): con la lista vacía daría 422.
    enabled: posiciones.length > 0,
    ...TIEMPOS.mercado,
    retry: false,
  })
}
