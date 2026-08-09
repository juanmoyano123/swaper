/**
 * F-030 — compone la resolución de la cartera cargada (F-029) con el universo y el tipo de cambio
 * compartidos (`@/lib/cartera/hooks`), y valúa el resultado con `valuarCartera`.
 *
 * Mismo patrón que `features/armador/hooks/useCarteraResuelta.ts` (`useMemo` sobre queries de
 * TanStack Query), pero sin store propio: esta pantalla no arma nada, sólo valúa la cartera que ya
 * se cargó — no hay `useCarteraResuelta.ts` ni `ArmadorProvider` de por medio.
 */

import { useMemo } from 'react'

import type { PosicionCruda } from '@/features/cartera-ingreso/types'
import { useResolucionCartera } from '@/features/cartera-resolucion/hooks/useResolucionCartera'
import type { Especie } from '@/lib/cartera/esquemaEspecie'
import { useEspeciesUniverso } from '@/lib/cartera/hooks/useEspeciesUniverso'
import { useTipoDeCambio } from '@/lib/cartera/hooks/useTipoDeCambio'

import { valuarCartera, type CarteraValuada } from '../lib/valuacion'

export function useCarteraCargadaValuada(posiciones: PosicionCruda[]) {
  const resolucion = useResolucionCartera(posiciones)
  const especies = useEspeciesUniverso()
  const tipoDeCambio = useTipoDeCambio()

  const porTicker = useMemo(() => {
    const mapa = new Map<string, Especie>()
    for (const especie of especies.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [especies.data])

  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const valuacion: CarteraValuada | null = useMemo(
    () => (resolucion.data ? valuarCartera(resolucion.data.posiciones, porTicker, tcValor) : null),
    [resolucion.data, porTicker, tcValor],
  )

  return {
    resolucion,
    valuacion,
    tipoDeCambio: tcValor,
    porTicker,
    cargando: resolucion.isPending || especies.isPending || tipoDeCambio.isPending,
    error: resolucion.error ?? especies.error ?? tipoDeCambio.error ?? null,
  }
}
