/**
 * Los montos de la cartera propuesta — F-036. Compone el plan de rotaciones (`planRotacionStore`)
 * con el universo (para la moneda de cotización de cada punta) y el tipo de cambio implícito, y
 * llama a `montosAcumulados` de `lib/rotaciones/plan.ts` — la única pieza con la aritmética.
 *
 * Recibe los montos originales ya calculados por el llamador (`valuadas[].invertido` de
 * `useCarteraCargadaValuada`, mismo mapeo que hace `DiagnosticoCartera.tsx`), porque este hook no
 * conoce la valuación de la cartera cargada: sólo sabe convertir monedas al mover un monto de una
 * punta a otra.
 */

import { useMemo } from 'react'

import { useEspeciesUniverso } from '../../../lib/cartera/hooks/useEspeciesUniverso'
import { useTipoDeCambio } from '../../../lib/cartera/hooks/useTipoDeCambio'
import { montosAcumulados, type PosicionConMonto } from '../../../lib/rotaciones/plan'
import { usePlanRotacion } from '../store/planRotacionStore'

export function useCarteraPropuesta(montosOriginales: PosicionConMonto[]) {
  const especiesUniverso = useEspeciesUniverso()
  const tipoDeCambio = useTipoDeCambio()
  const plan = usePlanRotacion()

  const porTicker = useMemo(() => {
    const mapa = new Map<string, string | null>()
    for (const especie of especiesUniverso.data ?? []) {
      // Mismo criterio que `valuarCartera.ts:87`: `BYMA` manda "ARS"/"USD" en mayúsculas, y una
      // moneda de cotización distinta de las dos conocidas (por ejemplo `EXT`, regla 11) no tiene
      // con qué convertirse — se deja fuera en vez de asumirla.
      const moneda = especie.moneda_cotizacion?.toLowerCase() ?? null
      mapa.set(especie.ticker, moneda === 'usd' || moneda === 'ars' ? moneda : null)
    }
    return mapa
  }, [especiesUniverso.data])

  const monedaDe = useMemo(() => (ticker: string) => (porTicker.get(ticker) ?? null) as 'usd' | 'ars' | null, [porTicker])

  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const resultado = useMemo(
    () => montosAcumulados(montosOriginales, plan.aceptadas, monedaDe, tcValor),
    [montosOriginales, plan.aceptadas, monedaDe, tcValor],
  )

  return {
    ...resultado,
    cargando: especiesUniverso.isPending || tipoDeCambio.isPending,
    error: especiesUniverso.error ?? tipoDeCambio.error,
  }
}
