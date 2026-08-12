/**
 * Los topes de concentración de una cartera de posiciones explícitas — F-020, sobre `POST /
 * concentracion`.
 *
 * Movido acá en la Tanda 11 desde `features/armador/hooks/useConcentracion.ts`, para que el
 * diagnóstico de cartera (F-030) mida los mismos topes con el mismo endpoint que el armador
 * (riesgo R12 de `plan.md:2774`).
 *
 * Calcado de `useCalendarioCartera`: mismo POST-que-es-lectura, misma mecánica de firma de cartera
 * para la clave de caché, mismo `enabled` para no llamar con la lista vacía. La diferencia es qué
 * número identifica la cartera.
 *
 * **Acá se firma con el peso y no con el monto.** El calendario se firma con `invertido` porque lo
 * que viaja en su cuerpo es plata: dos carteras con el mismo peso pedido pero precios distintos
 * cobran distinto y necesitan volver a pedirse. La concentración no mira precios — mira contra qué
 * crédito, sector y ley está el peso — así que lo que la identifica es el peso que se manda.
 * Firmar con el monto haría refetch en cada refresh de mercado por un veredicto que no cambió.
 *
 * El perfil entra en la clave y no en la firma: es el parámetro contra el que se mide, no parte de
 * la cartera, y las tres respuestas de la misma cartera conviven en caché sin pisarse.
 *
 * `firmaDePesos` se exporta desde la Tanda 13: F-033 arma carteras simuladas (una por candidata
 * de rotación sobreviviente) y necesita la misma firma para que sus concentraciones simuladas
 * compartan caché con las de este hook.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaConcentracion, type NombreDePerfil } from '../esquemaConcentracion'

/** Una posición como la mide este panel: qué especie y cuánto pesa, en puntos porcentuales. */
export interface PosicionConPeso {
  ticker: string
  peso: number
}

export function firmaDePesos(posiciones: PosicionConPeso[]): string {
  return posiciones.map((p) => `${p.ticker}:${p.peso}`).join('|')
}

export function useConcentracion(posiciones: PosicionConPeso[], perfil: NombreDePerfil) {
  return useQuery({
    queryKey: claves.mercado.concentracion(firmaDePesos(posiciones), perfil),
    queryFn: () =>
      apiFetch(
        `/api/v1/concentracion?perfil=${encodeURIComponent(perfil)}`,
        esquemaConcentracion,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            posiciones: posiciones.map((p) => ({ ticker: p.ticker, peso: p.peso })),
          }),
        },
      ),
    // El endpoint exige al menos una posición (`min_length=1`): con la lista vacía daría 422.
    enabled: posiciones.length > 0,
    ...TIEMPOS.mercado,
    retry: false,
  })
}
