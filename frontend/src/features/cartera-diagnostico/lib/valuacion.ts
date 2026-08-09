/**
 * F-030 — el adaptador que cruza las posiciones resueltas de F-029 contra el universo para
 * obtener precio y moneda, y valuar la cartera cargada: invertido, invertido en dólares y peso
 * real. Hace el mismo trabajo que `features/armador/lib/resolver.ts::resolver()` para el mandato
 * del armador, pero partiendo de nominales ya declarados (F-029) en vez de un peso pedido.
 *
 * El contrato de entrada (`PosicionResuelta` de F-029) no trae rendimiento, duración, precio ni
 * peso — sólo lo que el asesor declaró y lo que el backend pudo vincular contra el universo. Acá
 * se agrega la mitad que falta.
 *
 * **Función pura, sin red**: se testea aislada del hook y de la pantalla, mismo criterio que
 * `resolver.ts`.
 */

import type { PosicionResuelta } from '@/features/cartera-resolucion/lib/schema'
import type { Especie } from '@/lib/cartera/esquemaEspecie'

export type MotivoExclusionValuacion =
  | 'no_resuelta'
  | 'sin_nominal'
  | 'sin_precio'
  | 'sin_tipo_de_cambio'

export interface PosicionValuada {
  ticker: string
  /** En la moneda de cotización de la especie. */
  invertido: number
  invertidoUsd: number
  /** `invertidoUsd / Σ invertidoUsd * 100`, sobre las valuadas únicamente. */
  pesoReal: number
  /** Igual a `pesoReal`. Así `PosicionValuada` encaja sin adaptar como `PosicionPonderada` de
   *  `@/lib/cartera/metricas` (`{ ticker, peso, pesoReal }`), que es la forma que piden
   *  `rendimientosPorNaturaleza` y `plazoPromedio`. */
  peso: number
}

export interface PosicionExcluidaValuacion {
  id: string
  motivo: MotivoExclusionValuacion
  /** El monto tal como vino del resumen cargado, sin convertir — su moneda no está declarada
   *  (regla 1: no se infiere). `null` cuando la posición tampoco declaró monto. */
  montoDeclarado: number | null
}

export interface CarteraValuada {
  valuadas: PosicionValuada[]
  excluidas: PosicionExcluidaValuacion[]
  /** Σ `invertidoUsd` de las valuadas. */
  totalInvertidoUsd: number
}

interface Intermedia {
  id: string
  ticker: string
  /** En la moneda de cotización de la especie. */
  invertido: number
  monedaCotizacion: 'usd' | 'ars'
}

export function valuarCartera(
  posiciones: PosicionResuelta[],
  porTicker: ReadonlyMap<string, Especie>,
  tipoDeCambio: number | null,
): CarteraValuada {
  const intermedias: Intermedia[] = []
  const excluidas: PosicionExcluidaValuacion[] = []

  for (const pos of posiciones) {
    if (!pos.resuelta || pos.ticker === null) {
      excluidas.push({ id: pos.id, motivo: 'no_resuelta', montoDeclarado: pos.monto })
      continue
    }

    // No se deriva un nominal de `monto`: la moneda en la que vino ese monto no está declarada en
    // el resumen cargado (a diferencia del armador, que siempre trabaja en USD por construcción),
    // así que convertirlo sería inventar una moneda (regla 1 del proyecto).
    if (pos.nominal === null) {
      excluidas.push({ id: pos.id, motivo: 'sin_nominal', montoDeclarado: pos.monto })
      continue
    }

    const especie = porTicker.get(pos.ticker)
    // Normalizado a minúscula acá, mismo criterio que `useCarteraResuelta.ts:76-77`: `BYMA` manda
    // "ARS"/"USD" en mayúsculas. Una moneda de cotización ausente o distinta de las dos conocidas
    // no tiene con qué valuarse sin inventar una unidad — se agrupa con "sin precio", igual que
    // `resolver.ts` la trata como sin base para operar (`sinBase` en `useCarteraResuelta.ts`).
    const monedaCotizacion = especie?.moneda_cotizacion?.toLowerCase() ?? null
    if (!especie || especie.precio === null || (monedaCotizacion !== 'usd' && monedaCotizacion !== 'ars')) {
      excluidas.push({ id: pos.id, motivo: 'sin_precio', montoDeclarado: pos.monto })
      continue
    }

    // Nunca se inventa un tipo de cambio externo (regla 3 del proyecto): sin el implícito del
    // propio universo, una posición en pesos no se puede llevar a dólares y se declara, no se
    // estima.
    if (monedaCotizacion === 'ars' && tipoDeCambio === null) {
      excluidas.push({ id: pos.id, motivo: 'sin_tipo_de_cambio', montoDeclarado: pos.monto })
      continue
    }

    // Misma fórmula que `resolver.ts:89`: precio cada 100 de valor nominal.
    const invertido = (pos.nominal * especie.precio) / 100
    intermedias.push({ id: pos.id, ticker: pos.ticker, invertido, monedaCotizacion })
  }

  const conInvertidoUsd = intermedias.map((i) => ({
    ...i,
    // Inverso de la conversión que hace `resolver.ts:77` para llegar de un objetivo en USD a uno
    // en ARS: acá se parte del invertido en ARS ya calculado y se lo vuelve a USD dividiendo por
    // el mismo TC (idéntico a `resolver.ts:91`). Ejemplo concreto, TC = 1050: invertido ARS
    // 105.000 → invertidoUsd 105.000 / 1050 = 100. Verificado también en `valuacion.test.ts`.
    invertidoUsd: i.monedaCotizacion === 'ars' ? i.invertido / (tipoDeCambio as number) : i.invertido,
  }))

  const totalInvertidoUsd = conInvertidoUsd.reduce((acumulado, i) => acumulado + i.invertidoUsd, 0)

  const valuadas: PosicionValuada[] = conInvertidoUsd.map((i) => {
    const pesoReal = totalInvertidoUsd > 0 ? (i.invertidoUsd / totalInvertidoUsd) * 100 : 0
    return {
      ticker: i.ticker,
      invertido: i.invertido,
      invertidoUsd: i.invertidoUsd,
      pesoReal,
      peso: pesoReal,
    }
  })

  return { valuadas, excluidas, totalInvertidoUsd }
}
