/**
 * Una línea por sección, visible aunque esté plegada — para poder enfocarse en una sola sección
 * sin perder de vista qué hay en las demás. Todo lo que muestra sale de datos que la página ya
 * tiene cargados (el store del armador, la grilla de doce meses): ningún resumen dispara su propio
 * pedido, y ninguno inventa un número que no pueda calcular (regla 1 del dominio).
 */

import { fmtPct } from '@/lib/fmt'

import { sumaPesos } from '../lib/mix'
import type { MesDelCalendario } from '../lib/schema'
import { posicionesRentaFija, posicionesRentaVariable, useArmador } from '../store/carteraStore'

/** Cuántos de los doce meses de la grilla tienen al menos un papel elegido pagando ahí. */
export function ResumenCordillera({ meses }: { meses: readonly MesDelCalendario[] }) {
  const { pos } = useArmador()
  const tickers = new Set(posicionesRentaFija(pos).map((p) => p.ticker))
  if (tickers.size === 0) return <>sin papeles elegidos todavía</>
  const mesesConPago = meses.filter((m) => m.instrumentos.some((i) => tickers.has(i.ticker))).length
  return (
    <>
      {mesesConPago} de {meses.length || 12} meses con papeles elegidos
    </>
  )
}

/** Posiciones y ponderación pedida de la cartera entera (RF + FCI + RV, como pesa `peso`). */
export function ResumenCartera() {
  const { pos } = useArmador()
  if (pos.length === 0) return <>sin posiciones todavía</>
  return (
    <>
      {pos.length} posición{pos.length === 1 ? '' : 'es'} · Σ {fmtPct(sumaPesos(pos), 1)}
    </>
  )
}

/** Sólo el bloque de renta variable — cuenta y ponderación pedida propias (F-026: no participa de
 *  la renta ni de los rendimientos, así que su resumen tampoco se mezcla con el de renta fija). */
export function ResumenRentaVariable() {
  const { pos } = useArmador()
  const rv = posicionesRentaVariable(pos)
  if (rv.length === 0) return <>sin acciones ni CEDEARs todavía</>
  return (
    <>
      {rv.length} papel{rv.length === 1 ? '' : 'es'} · Σ {fmtPct(sumaPesos(rv), 1)}
    </>
  )
}
