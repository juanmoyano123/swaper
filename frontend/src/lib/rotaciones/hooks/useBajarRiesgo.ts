/**
 * F-033 — orquesta candidatas de rotación (F-032) + vector de riesgo actual (F-031) + concentración
 * simulada de cada sobreviviente de la etapa local, y llama a la lib pura de `bajarRiesgo.ts` para
 * el veredicto final.
 *
 * El eje elegido es estado local del hook (no de la URL ni de un store global): cambiarlo no pide
 * de nuevo rotaciones ni el vector actual, sólo vuelve a evaluar contra lo que ya está en caché.
 *
 * La concentración simulada de cada candidata sobreviviente de la etapa local se pide con
 * `useQueries` — una consulta por candidata, cacheada por la misma `firmaDePesos` + perfil que
 * `useConcentracion`, así que si dos candidatas distintas terminan en la misma cartera simulada (o
 * coinciden con una concentración que `SeccionRiesgo` ya pidió para la cartera real) comparten
 * caché en vez de repetir el POST.
 */

import { useMemo, useState } from 'react'

import { useQueries } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import { esquemaConcentracion, type Concentracion, type NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { firmaDePesos, useConcentracion, type PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'
import { useMapaRiesgo } from '@/lib/cartera/hooks/useMapaRiesgo'
import { vectorDeRiesgo, type IdDeEje } from '@/lib/cartera/riesgo'

import {
  EJES_NO_MEDIBLES_COMO_PRIMARIO,
  EJE_PRIMARIO_DEFAULT,
  carteraSimuladaDeCandidata,
  claveCandidata,
  evaluarBajarRiesgo,
  evaluarEtapaLocal,
  resultadoNoMedible,
  type ResultadoBajarRiesgo,
} from '../bajarRiesgo'
import { useRotaciones } from './useRotaciones'

export function useBajarRiesgo(posicionesActuales: PosicionConPeso[], perfil: NombreDePerfil) {
  const [ejePrimario, setEjePrimario] = useState<IdDeEje>(EJE_PRIMARIO_DEFAULT)
  const noMedible = EJES_NO_MEDIBLES_COMO_PRIMARIO.has(ejePrimario)

  const especiesUniverso = useMapaRiesgo()
  const concentracionActual = useConcentracion(posicionesActuales, perfil)
  const rotaciones = useRotaciones(posicionesActuales, perfil)

  const porTicker = especiesUniverso.porTicker

  const vectorActual = useMemo(
    () => vectorDeRiesgo(posicionesActuales, porTicker, concentracionActual.data ?? null),
    [posicionesActuales, porTicker, concentracionActual.data],
  )

  const sobrevivientesLocal = useMemo(() => {
    if (noMedible || !rotaciones.data) return []
    return evaluarEtapaLocal(rotaciones.data.candidatas, ejePrimario, vectorActual, posicionesActuales, porTicker)
      .sobrevivientes
  }, [noMedible, rotaciones.data, ejePrimario, vectorActual, posicionesActuales, porTicker])

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

  // Sin `useMemo`: `consultasConcentracion` ya es un array nuevo en cada render de `useQueries`,
  // así que memoizar acá no evita ningún recálculo real — sólo agregaría una dependencia más para
  // mantener sincronizada.
  const concentracionesSimuladas = new Map<string, Concentracion | null>()
  sobrevivientesLocal.forEach((candidata, indice) => {
    concentracionesSimuladas.set(claveCandidata(candidata), consultasConcentracion[indice]?.data ?? null)
  })

  let resultado: ResultadoBajarRiesgo | null = null
  if (noMedible) {
    resultado = resultadoNoMedible(ejePrimario)
  } else if (rotaciones.data && !cargandoConcentracion) {
    resultado = evaluarBajarRiesgo(
      rotaciones.data.candidatas,
      ejePrimario,
      vectorActual,
      posicionesActuales,
      porTicker,
      concentracionesSimuladas,
    )
  }

  return {
    ejePrimario,
    setEjePrimario,
    cargando:
      especiesUniverso.isPending ||
      concentracionActual.isPending ||
      rotaciones.isPending ||
      (!noMedible && cargandoConcentracion),
    error: especiesUniverso.error ?? concentracionActual.error ?? rotaciones.error ?? errorConcentracion,
    resultado,
  }
}
