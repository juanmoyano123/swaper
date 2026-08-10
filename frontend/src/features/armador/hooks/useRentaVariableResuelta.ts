/**
 * La porción de renta variable de la cartera, resuelta a unidades y montos — Tanda 13.
 *
 * El gemelo de `useCarteraResuelta` para el otro lado de la cartera. Sale de `BloqueRentaVariable`,
 * que era su único consumidor hasta que la tabla de `CarteraEditable` pasó a mostrar la cartera
 * completa por bloques y necesitó los mismos números: el nombre de la empresa, el porcentaje real y
 * lo invertido en cada acción.
 *
 * La matemática es la de `resolverRentaVariable` —unidades enteras, nunca fracciones de acción— y
 * queda toda de ese lado; acá sólo se junta el universo de acciones con el de CEDEARs y se cruza
 * contra las posiciones del store. Las dos consultas están cacheadas por TanStack Query, así que
 * tener dos consumidores no duplica ningún pedido.
 */

import { useMemo } from 'react'

import { type EspecieRentaVariable, useRentaVariable } from '@/lib/rentaVariable'

import { useTipoDeCambio } from './useTipoDeCambio'
import {
  resolverRentaVariable,
  subtotalRentaVariableUsd,
  type PosicionRvResuelta,
} from '../lib/resolverRentaVariable'
import { posicionesRentaVariable, useArmador, type PosicionArmador } from '../store/carteraStore'

export interface RentaVariableResuelta {
  /** Las posiciones de clase `renta_variable` del store, en orden de incorporación. */
  posiciones: PosicionArmador[]
  /** Cada una resuelta a unidades enteras e invertido, o con todo en `null` si falta precio. */
  resueltas: PosicionRvResuelta[]
  /** Acciones y CEDEARs del universo indexados por ticker: de acá sale el nombre de la empresa. */
  porTicker: Map<string, EspecieRentaVariable>
  /** Suma invertida en dólares, o `null` si no se pudo resolver ninguna. */
  subtotalUsd: number | null
  hayAlgunaResuelta: boolean
}

export function useRentaVariableResuelta(): RentaVariableResuelta {
  const { pos, montoTotal } = useArmador()

  const acciones = useRentaVariable('accion')
  const cedears = useRentaVariable('cedear')
  const tipoDeCambio = useTipoDeCambio()

  const porTicker = useMemo(() => {
    const mapa = new Map<string, EspecieRentaVariable>()
    for (const especie of acciones.data ?? []) mapa.set(especie.ticker, especie)
    for (const especie of cedears.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [acciones.data, cedears.data])

  const posiciones = useMemo(() => posicionesRentaVariable(pos), [pos])
  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const resueltas = useMemo(() => {
    const entradas = posiciones.map((p) => {
      const especie = porTicker.get(p.ticker)
      return {
        ticker: p.ticker,
        peso: p.peso,
        precio: especie?.precio ?? null,
        monedaCotizacion: especie?.moneda_cotizacion ?? null,
      }
    })
    return resolverRentaVariable(entradas, montoTotal, tcValor)
  }, [posiciones, porTicker, montoTotal, tcValor])

  return {
    posiciones,
    resueltas,
    porTicker,
    subtotalUsd: subtotalRentaVariableUsd(resueltas),
    hayAlgunaResuelta: resueltas.some((r) => r.invertidoUsd !== null),
  }
}
