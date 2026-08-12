/**
 * GWT-1 de F-036: el efecto de una candidata sobre el calendario de doce meses, calculado en el
 * momento en que se le muestra la fila al asesor.
 *
 * Mismo patrón que la concentración-por-candidata de `useBajarRiesgo`/`useSubirTir`: dos consultas
 * a `POST /calendario/cartera?detalle=true` (la cartera actual y la simulada de esta candidata),
 * cacheadas por `firmaDeCartera` bajo la misma clave que usa `useCalendarioCartera` — la consulta
 * "actual" se dedupea entre todas las filas que la piden, y al aceptar una rotación el calendario de
 * la cartera acumulada ya suele estar en caché (misma firma que la candidata que se aceptó).
 *
 * `detalle=true` es obligatorio: la clave de caché no codifica el parámetro, así que una respuesta
 * sin `instrumentos` rompería el parseo de `useCalendarioCartera` si ese hook la encontrara en
 * caché con `detalle` distinto.
 */

import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import { esquemaCalendarioUniverso } from '@/lib/cartera/esquemaCalendario'
import { firmaDeCartera } from '@/lib/cartera/firmaDeCartera'

import { diffCalendario, efectoNoCalculable, type EfectoCalendario } from '../efectoCalendario'
import type { Candidata } from '../esquemaRotaciones'
import { montosAcumulados, type PosicionConMonto } from '../plan'

function useCalendario(posiciones: PosicionConMonto[]) {
  const firma = firmaDeCartera(posiciones)
  return useQuery({
    queryKey: claves.mercado.calendarioCartera(firma),
    queryFn: () =>
      apiFetch('/api/v1/calendario/cartera?detalle=true', esquemaCalendarioUniverso, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ posiciones: posiciones.map((p) => ({ ticker: p.ticker, monto: p.monto })) }),
      }),
    enabled: posiciones.length > 0,
    ...TIEMPOS.mercado,
    retry: false,
  })
}

export function useEfectoCalendario(
  montosActuales: PosicionConMonto[],
  candidata: Candidata,
  monedaDe: (ticker: string) => 'usd' | 'ars' | null,
  tipoDeCambio: number | null,
): { cargando: boolean; error: Error | null; efecto: EfectoCalendario | null } {
  const { montos: montosSimulados, noConvertibles } = useMemo(
    () => montosAcumulados(montosActuales, [candidata], monedaDe, tipoDeCambio),
    [montosActuales, candidata, monedaDe, tipoDeCambio],
  )

  const actual = useCalendario(montosActuales)
  const simulado = useCalendario(montosSimulados)

  const efecto = useMemo<EfectoCalendario | null>(() => {
    if (noConvertibles.length > 0) {
      return efectoNoCalculable(
        `El efecto sobre el calendario no se puede afirmar: no hay tipo de cambio para convertir ` +
          `${noConvertibles.join(', ')} a la moneda de la punta que se compra.`,
      )
    }
    if (!actual.data || !simulado.data) return null
    return diffCalendario(actual.data, simulado.data, candidata)
  }, [noConvertibles, actual.data, simulado.data, candidata])

  return {
    cargando: actual.isPending || simulado.isPending,
    error: actual.error ?? simulado.error,
    efecto,
  }
}
