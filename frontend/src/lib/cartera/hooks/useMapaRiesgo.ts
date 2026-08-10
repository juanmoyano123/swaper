/**
 * El universo indexado por ticker en la forma que `vectorDeRiesgo()` (F-031) necesita.
 *
 * Existía copiado literal en tres lugares —`SeccionRiesgo` (F-031), `useBajarRiesgo` (F-033) y el
 * `useSubirTir` de F-034— y ese es exactamente el tipo de duplicación que hace divergir un vector
 * de riesgo del otro: si mañana `EspecieRiesgo` gana un campo, con tres copias alcanza con olvidar
 * una para que la misma cartera se mida distinto según la pantalla. El criterio de aceptación R12
 * (`plan.md:2774`) pide justo lo contrario.
 *
 * `useEspeciesUniverso()` deduplica por TanStack, así que llamar a este hook desde varias secciones
 * de la misma pantalla no agrega ni una consulta.
 */

import { useMemo } from 'react'

import { useEspeciesUniverso } from './useEspeciesUniverso'
import type { EspecieRiesgo } from '../riesgo'

export function useMapaRiesgo() {
  const especiesUniverso = useEspeciesUniverso()

  const porTicker = useMemo(() => {
    const mapa = new Map<string, EspecieRiesgo>()
    for (const especie of especiesUniverso.data ?? []) {
      mapa.set(especie.ticker, {
        ticker: especie.ticker,
        segmento: especie.segmento,
        naturaleza: especie.naturaleza,
        naturaleza_nombre: especie.naturaleza_nombre,
        clase_activo: especie.clase_activo,
        duracion: especie.duracion,
        ley: especie.ley,
        volumen_usd: especie.volumen_usd,
        calificacion: especie.calificacion,
        dato_sano: especie.dato_sano,
      })
    }
    return mapa
  }, [especiesUniverso.data])

  return { porTicker, isPending: especiesUniverso.isPending, error: especiesUniverso.error }
}
