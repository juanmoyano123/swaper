/**
 * El patrón mensual de balances de un conjunto de CEDEARs — F-027, sobre `POST /renta-variable/
 * balances`.
 *
 * POST-que-es-lectura, mismo criterio que `useCalendarioCartera` (F-015/F-018): los papeles viajan
 * explícitos en el cuerpo. La clave se deriva de `claves.referencia` y no de `claves.mercado`: un
 * refresh de precios no cambia en qué mes una empresa presenta balance ante la SEC — ese dato se
 * actualiza a lo sumo una vez por trimestre, así que cuelga del mismo prefijo que el dato curado
 * (`referencia`, "cambia por ingesta, no por paso del tiempo"), con `staleTime` largo propio.
 */

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaRespuestaBalances, type CalendarioBalances } from '../lib/esquemaBalances'

const UNA_HORA_MS = 60 * 60 * 1000

export function useCalendarioBalances(papeles: string[]) {
  const unicos = useMemo(
    () => [...new Set(papeles.map((p) => p.trim().toUpperCase()).filter((p) => p.length > 0))].sort(),
    [papeles],
  )
  const firma = unicos.join(',')

  const consulta = useQuery({
    queryKey: [...claves.referencia.todas, 'balances', firma] as const,
    queryFn: () =>
      apiFetch('/api/v1/renta-variable/balances', esquemaRespuestaBalances, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ papeles: unicos }),
      }),
    // El endpoint exige al menos un papel (`min_length=1`): con la lista vacía daría 422, así que
    // nunca se llama sin CEDEARs en la cartera.
    enabled: unicos.length > 0,
    staleTime: UNA_HORA_MS,
    retry: false,
  })

  const porPapel = useMemo(() => {
    const mapa = new Map<string, CalendarioBalances>()
    for (const calendario of consulta.data?.calendarios ?? []) mapa.set(calendario.papel, calendario)
    return mapa
  }, [consulta.data])

  return { ...consulta, porPapel }
}
