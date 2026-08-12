/**
 * La llamada a F-029: manda las posiciones crudas de F-028 y devuelve la cartera resuelta.
 *
 * **Se mandan todas las posiciones, también las que F-028 marcó inválidas.** Filtrarlas acá las
 * haría desaparecer del diagnóstico de cobertura, que es justo lo contrario de lo que la feature
 * existe para hacer: una posición que no se pudo leer sigue siendo plata del cliente.
 *
 * `valida` y `motivo` no se mandan: son el veredicto de F-028 sobre el formato de la fila y el
 * backend no los necesita para buscar un ticker.
 */

import { apiFetch } from '@/lib/api/client'

import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import { esquemaResolucion, type Resolucion } from './schema'

export const RUTA_RESOLVER = '/api/v1/posiciones/resolver'

/** La firma de una cartera, para la clave de caché. Dos carteras distintas no la comparten. */
export function firmaDeCartera(posiciones: PosicionCruda[]): string {
  return posiciones.map((p) => `${p.tickerDeclarado}:${p.nominal ?? ''}:${p.monto ?? ''}`).join('|')
}

export async function resolverCartera(posiciones: PosicionCruda[]): Promise<Resolucion> {
  return apiFetch(RUTA_RESOLVER, esquemaResolucion, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      posiciones: posiciones.map((p) => ({
        id: p.id,
        fila: p.fila,
        ticker_declarado: p.tickerDeclarado,
        nominal: p.nominal,
        monto: p.monto,
      })),
    }),
  })
}
