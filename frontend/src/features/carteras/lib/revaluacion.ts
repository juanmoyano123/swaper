/**
 * "Revaluar a hoy" (GWT-2 de F-041) — comparar lo congelado en el snapshot contra la misma cartera
 * valuada con los servicios de hoy, sin promediar monedas (regla 3) ni estimar lo que falta
 * (regla 1). Todo el módulo son funciones puras: qué hook trae los precios de hoy lo decide el
 * componente, acá sólo se compara.
 *
 * Las dos puntas (guardada y hoy) se normalizan a `PosicionComparable` antes de compararlas, así
 * `compararValuaciones` no necesita saber si viene de la cartera cargada o del armador.
 */

import type { PosicionArmador } from '@/features/armador/store/carteraStore'

import type { ResueltaGuardada, SnapshotArmador, SnapshotCargada } from './esquemaSnapshot'

export interface PosicionComparable {
  ticker: string
  moneda: 'usd' | 'ars' | null
  /** En su moneda de cotización. `null` = no se pudo valuar en esta punta (ver `motivo`). */
  invertido: number | null
  invertidoUsd: number | null
  /** Por qué no se pudo valuar en esta punta. `null` cuando sí se valuó. */
  motivo: string | null
}

export interface DeltaPosicion {
  ticker: string
  monedaGuardada: 'usd' | 'ars' | null
  monedaHoy: 'usd' | 'ars' | null
  invertidoGuardado: number | null
  invertidoHoy: number | null
  /** Sólo si las dos monedas coinciden y ninguna de las dos puntas falta. */
  delta: number | null
  /** Por qué no hay `delta`: `'moneda_distinta'` o el motivo declarado de la punta que falta. */
  motivo: string | null
}

export interface ComparacionValuaciones {
  posiciones: DeltaPosicion[]
  totalUsdGuardado: number
  totalUsdHoy: number
  deltaTotalUsd: number
  /** Tickers que no entraron a alguno de los dos totales, con el motivo — el total es parcial
   *  cuando esta lista no está vacía. */
  excluidosDelTotal: { ticker: string; motivo: string }[]
}

export function compararValuaciones(
  congeladas: readonly PosicionComparable[],
  hoy: readonly PosicionComparable[],
): ComparacionValuaciones {
  const porTickerCongelada = new Map(congeladas.map((p) => [p.ticker, p]))
  const porTickerHoy = new Map(hoy.map((p) => [p.ticker, p]))
  const tickers = Array.from(new Set([...porTickerCongelada.keys(), ...porTickerHoy.keys()])).sort()

  const posiciones: DeltaPosicion[] = []
  const excluidosDelTotal: { ticker: string; motivo: string }[] = []
  let totalUsdGuardado = 0
  let totalUsdHoy = 0

  for (const ticker of tickers) {
    const c = porTickerCongelada.get(ticker) ?? null
    const h = porTickerHoy.get(ticker) ?? null

    if (c?.invertidoUsd != null) {
      totalUsdGuardado += c.invertidoUsd
    } else {
      excluidosDelTotal.push({ ticker, motivo: c?.motivo ?? 'sin_valuar_al_guardar' })
    }

    if (h?.invertidoUsd != null) {
      totalUsdHoy += h.invertidoUsd
    } else {
      excluidosDelTotal.push({ ticker, motivo: h?.motivo ?? 'sin_precio_hoy' })
    }

    const monedasDeclaradas = c?.moneda != null && h?.moneda != null
    const monedaCoincide = monedasDeclaradas && c.moneda === h.moneda
    const delta =
      monedaCoincide && c.invertido != null && h.invertido != null ? h.invertido - c.invertido : null

    let motivo: string | null = null
    if (delta === null) {
      if (monedasDeclaradas && !monedaCoincide) motivo = 'moneda_distinta'
      else if (c?.invertido == null) motivo = c?.motivo ?? 'sin_valuar_al_guardar'
      else if (h?.invertido == null) motivo = h?.motivo ?? 'sin_precio_hoy'
    }

    posiciones.push({
      ticker,
      monedaGuardada: c?.moneda ?? null,
      monedaHoy: h?.moneda ?? null,
      invertidoGuardado: c?.invertido ?? null,
      invertidoHoy: h?.invertido ?? null,
      delta,
      motivo,
    })
  }

  return {
    posiciones,
    totalUsdGuardado,
    totalUsdHoy,
    deltaTotalUsd: totalUsdHoy - totalUsdGuardado,
    excluidosDelTotal,
  }
}

// --- Origen A: cartera cargada -------------------------------------------------------------------

/** El snapshot ya guarda `moneda` por posición valuada: no hace falta el universo de hoy para
 *  leer la punta congelada. */
export function comparablesDesdeSnapshotCargada(snapshot: SnapshotCargada): PosicionComparable[] {
  const porId = new Map(snapshot.posiciones.map((p) => [p.id, p]))
  const deValuadas: PosicionComparable[] = snapshot.valuadas.map((v) => ({
    ticker: v.ticker,
    moneda: v.moneda,
    invertido: v.invertido,
    invertidoUsd: v.invertidoUsd,
    motivo: null,
  }))
  const deExcluidas: PosicionComparable[] = snapshot.excluidas.map((e) => ({
    ticker: porId.get(e.id)?.tickerDeclarado ?? e.id,
    moneda: null,
    invertido: null,
    invertidoUsd: null,
    motivo: e.motivo,
  }))
  return [...deValuadas, ...deExcluidas]
}

interface EspecieConMoneda {
  moneda_cotizacion: string | null
}

function monedaNormalizada(cruda: string | null | undefined): 'usd' | 'ars' | null {
  const m = cruda?.toLowerCase() ?? null
  return m === 'usd' || m === 'ars' ? m : null
}

/** La misma cartera cargada, valuada con los servicios de hoy (`useCarteraCargadaValuada` sobre
 *  `snapshot.posiciones`). La moneda no viaja en `PosicionValuada`: se la agrega acá desde el
 *  universo de hoy, mismo criterio que `armarSnapshotCargada`. */
export function comparablesDesdeValuacionHoy(
  posicionesCrudas: readonly { id: string; tickerDeclarado: string }[],
  valuacion: {
    valuadas: readonly { ticker: string; invertido: number; invertidoUsd: number }[]
    excluidas: readonly { id: string; motivo: string; montoDeclarado: number | null }[]
  },
  porTicker: ReadonlyMap<string, EspecieConMoneda>,
): PosicionComparable[] {
  const porId = new Map(posicionesCrudas.map((p) => [p.id, p]))
  const deValuadas: PosicionComparable[] = valuacion.valuadas.map((v) => ({
    ticker: v.ticker,
    moneda: monedaNormalizada(porTicker.get(v.ticker)?.moneda_cotizacion),
    invertido: v.invertido,
    invertidoUsd: v.invertidoUsd,
    motivo: null,
  }))
  const deExcluidas: PosicionComparable[] = valuacion.excluidas.map((e) => ({
    ticker: porId.get(e.id)?.tickerDeclarado ?? e.id,
    moneda: null,
    invertido: null,
    invertidoUsd: null,
    motivo: e.motivo,
  }))
  return [...deValuadas, ...deExcluidas]
}

// --- Origen B: armador ----------------------------------------------------------------------------

/** El snapshot del armador ya guarda precio, moneda e invertido por posición del mandato — algunas
 *  pueden tener `invertidoUsd: null` si no se pudieron resolver al momento de guardar (declarado,
 *  no se inventa un valor). */
export function comparablesDesdeSnapshotArmador(snapshot: SnapshotArmador): PosicionComparable[] {
  return snapshot.resueltas.map((r) => ({
    ticker: r.ticker,
    moneda: r.moneda,
    invertido: r.invertido,
    invertidoUsd: r.invertidoUsd,
    motivo: r.invertidoUsd == null ? 'sin_valuar_al_guardar' : null,
  }))
}

interface EspecieConMonedaYPrecio extends EspecieConMoneda {
  precio: number | null
}

/** Lo que hace falta de un fondo de hoy para revaluar un FCI congelado — F-046. */
interface FondoConVcpYMoneda {
  vcp: number | null
  moneda: string
}

/**
 * Revalúa el mandato guardado del armador contra el universo de hoy. No se corre `resolver()` de
 * nuevo: eso recalcularía otros nominales a partir del monto total, es decir, otra cartera. Lo que
 * se revalúa es lo que se propuso comprar —el `vn`/`cantidad`/`cuotapartes` congelados— a precios de
 * hoy, misma fórmula que `resolver.ts` (RF, precio cada 100 VN; FCI, VCP de hoy) y
 * `resolverRentaVariable.ts` (RV, unidades enteras).
 */
export function revaluarResueltasHoy(
  resueltas: readonly ResueltaGuardada[],
  porTickerHoy: ReadonlyMap<string, EspecieConMonedaYPrecio>,
  tipoDeCambioHoy: number | null,
  /** Fondos de hoy por `codigo_cafci` (F-046). `undefined` = no se pasó ninguno (mismo default
   *  vacío que un snapshot sin FCI necesitaría): todo FCI cae en `fci_sin_identificar` o
   *  `fci_sin_vcp_hoy` según tenga o no código, nunca en un precio inventado. */
  porCodigoCafciHoy: ReadonlyMap<string, FondoConVcpYMoneda> = new Map(),
): PosicionComparable[] {
  return resueltas.map((r) => {
    if (r.clase === 'fci') {
      // Ausente en snapshots guardados antes de F-046: un FCI legado sigue sin identificar, nunca
      // matcheado por nombre (regla 11).
      if (!r.codigoCafci) {
        return { ticker: r.ticker, moneda: null, invertido: null, invertidoUsd: null, motivo: 'fci_sin_identificar' }
      }
      const fondo = porCodigoCafciHoy.get(r.codigoCafci)
      if (!fondo || fondo.vcp === null) {
        // El fondo desapareció de la planilla de hoy, o esta corrida no lo trajo: distinto de un
        // FCI sin identificar, que nunca tuvo con qué buscarlo.
        return { ticker: r.ticker, moneda: null, invertido: null, invertidoUsd: null, motivo: 'fci_sin_vcp_hoy' }
      }
      const monedaHoy = monedaNormalizada(fondo.moneda)
      if (monedaHoy === null) {
        // `USB` de CAFCI, u otra moneda que no sea `usd`/`ars`: nunca se convierte (regla 3).
        return { ticker: r.ticker, moneda: null, invertido: null, invertidoUsd: null, motivo: 'fci_moneda_no_convertible' }
      }
      if (monedaHoy === 'ars' && tipoDeCambioHoy === null) {
        return { ticker: r.ticker, moneda: 'ars', invertido: null, invertidoUsd: null, motivo: 'sin_tipo_de_cambio' }
      }
      if (r.cuotapartes == null) {
        // Se identificó pero no se pudo congelar la cantidad al guardar (no resolvía en ese
        // momento): no hay con qué multiplicar el VCP de hoy sin inventar una cantidad.
        return { ticker: r.ticker, moneda: monedaHoy, invertido: null, invertidoUsd: null, motivo: 'sin_precio_hoy' }
      }

      const invertido = r.cuotapartes * (fondo.vcp / 1000)
      const invertidoUsd = monedaHoy === 'ars' ? invertido / tipoDeCambioHoy! : invertido
      return { ticker: r.ticker, moneda: monedaHoy, invertido, invertidoUsd, motivo: null }
    }

    const especie = porTickerHoy.get(r.ticker)
    const monedaHoy = monedaNormalizada(especie?.moneda_cotizacion)
    const precioHoy = especie?.precio ?? null

    if (!especie || precioHoy === null || monedaHoy === null) {
      return { ticker: r.ticker, moneda: null, invertido: null, invertidoUsd: null, motivo: 'sin_precio_hoy' }
    }
    if (monedaHoy === 'ars' && tipoDeCambioHoy === null) {
      return { ticker: r.ticker, moneda: 'ars', invertido: null, invertidoUsd: null, motivo: 'sin_tipo_de_cambio' }
    }

    const invertido =
      r.clase === 'renta_variable'
        ? r.cantidad != null
          ? r.cantidad * precioHoy
          : null
        : r.vn != null
          ? (r.vn * precioHoy) / 100
          : null

    if (invertido === null) {
      return { ticker: r.ticker, moneda: monedaHoy, invertido: null, invertidoUsd: null, motivo: 'sin_precio_hoy' }
    }

    const invertidoUsd = monedaHoy === 'ars' ? invertido / tipoDeCambioHoy! : invertido
    return { ticker: r.ticker, moneda: monedaHoy, invertido, invertidoUsd, motivo: null }
  })
}

/** Reconstruye el mandato (`PosicionArmador[]`) desde el snapshot, para `cargarCartera` — "Abrir
 *  en el armador" (decisión 7 del plan). No incluye la parte valuada: eso lo vuelve a calcular el
 *  armador con los precios de hoy, que es justamente lo que "reabrir para seguir trabajando" pide. */
export function mandatoDesdeSnapshotArmador(snapshot: SnapshotArmador): PosicionArmador[] {
  return snapshot.posiciones.map((p) => ({
    ticker: p.ticker,
    peso: p.peso,
    clase: p.clase,
    codigoCafci: p.codigoCafci,
  }))
}
