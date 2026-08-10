/**
 * F-034 — orquesta candidatas de rotación (F-032) + vector de riesgo actual (F-031) + concentración
 * simulada de cada sobreviviente de la etapa local, y llama a la lib pura de `subirTir.ts`.
 *
 * Espejo de `useBajarRiesgo`, sin eje primario: este modo no le pide al asesor que elija nada,
 * porque no filtra por eje — muestra todas las mejoras de rendimiento con lo que cada una cuesta.
 *
 * Comparte caché con el otro modo en los tres pedidos: `useEspeciesUniverso` (dentro de
 * `useMapaRiesgo`), `useConcentracion` de la cartera real, y `useRotaciones` con la misma firma de
 * pesos y perfil. Las concentraciones simuladas se piden con `useQueries` bajo la misma clave que
 * usa F-033, así que una cartera simulada que el otro modo ya pidió no vuelve a viajar.
 */

import { useMemo } from 'react'

import { useQueries } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import { esquemaConcentracion, type Concentracion, type NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { firmaDePesos, useConcentracion, type PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'
import { useMapaRiesgo } from '@/lib/cartera/hooks/useMapaRiesgo'
import { vectorDeRiesgo } from '@/lib/cartera/riesgo'

import { carteraSimuladaDeCandidata, claveCandidata } from '../ejes'
import { evaluarEtapaLocalSubirTir, evaluarSubirTir, type ResultadoSubirTir } from '../subirTir'
import { useRotaciones } from './useRotaciones'

export function useSubirTir(posicionesActuales: PosicionConPeso[], perfil: NombreDePerfil) {
  const universo = useMapaRiesgo()
  const concentracionActual = useConcentracion(posicionesActuales, perfil)
  const rotaciones = useRotaciones(posicionesActuales, perfil)

  const porTicker = universo.porTicker

  const vectorActual = useMemo(
    () => vectorDeRiesgo(posicionesActuales, porTicker, concentracionActual.data ?? null),
    [posicionesActuales, porTicker, concentracionActual.data],
  )

  const sobrevivientesLocal = useMemo(() => {
    if (!rotaciones.data) return []
    return evaluarEtapaLocalSubirTir(rotaciones.data.candidatas, vectorActual, posicionesActuales, porTicker)
      .sobrevivientes
  }, [rotaciones.data, vectorActual, posicionesActuales, porTicker])

  const consultasConcentracion = useQueries({
    queries: sobrevivientesLocal.map((candidata) => {
      const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
      return {
        queryKey: claves.mercado.concentracion(firmaDePesos(posicionesSimuladas), perfil),
        queryFn: () =>
          apiFetch(`/api/v1/concentracion?perfil=${encodeURIComponent(perfil)}`, esquemaConcentracion, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              posiciones: posicionesSimuladas.map((p) => ({ ticker: p.ticker, peso: p.peso })),
            }),
          }),
        ...TIEMPOS.mercado,
        retry: false,
      }
    }),
  })

  const cargandoConcentracion = consultasConcentracion.some((c) => c.isPending)
  const errorConcentracion = consultasConcentracion.find((c) => c.isError)?.error ?? null

  // Sin `useMemo` por el mismo motivo que en `useBajarRiesgo`: `useQueries` ya devuelve un array
  // nuevo en cada render, así que memoizar acá no evitaría ningún recálculo real.
  const concentracionesSimuladas = new Map<string, Concentracion | null>()
  sobrevivientesLocal.forEach((candidata, indice) => {
    concentracionesSimuladas.set(claveCandidata(candidata), consultasConcentracion[indice]?.data ?? null)
  })

  let resultado: ResultadoSubirTir | null = null
  if (rotaciones.data && !cargandoConcentracion) {
    resultado = evaluarSubirTir(
      rotaciones.data.candidatas,
      vectorActual,
      posicionesActuales,
      porTicker,
      concentracionesSimuladas,
    )
  }

  return {
    cargando: universo.isPending || concentracionActual.isPending || rotaciones.isPending || cargandoConcentracion,
    error: universo.error ?? concentracionActual.error ?? rotaciones.error ?? errorConcentracion,
    resultado,
  }
}
