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
  /** F-046: el texto declarado matcheó un `codigo_cafci`, pero el fondo no tiene VCP en la
   *  planilla de hoy (desapareció, o `public.fci` no lo trajo en esta corrida). No es lo mismo que
   *  `sin_precio` genérico: acá el instrumento sí se identificó. */
  | 'fci_sin_vcp'
  /** El fondo cotiza en una moneda que no es `USD` ni `ARS` (p. ej. `USB` de CAFCI): nunca se
   *  convierte (regla 3 del proyecto). */
  | 'fci_moneda_no_convertible'

export interface PosicionValuada {
  ticker: string
  /** En la moneda de cotización de la especie. */
  invertido: number
  invertidoUsd: number
  /** `invertidoUsd / Σ invertidoUsd * 100`, sobre las valuadas únicamente. `null` si el total no
   *  se pudo determinar (mismo criterio que `resolver.ts::pesoReal`): no hay de qué ser un
   *  porcentaje, y no es 0. */
  pesoReal: number | null
  /** Igual a `pesoReal`. Así `PosicionValuada` encaja sin adaptar como `PosicionPonderada` de
   *  `@/lib/cartera/metricas` (`{ ticker, peso, pesoReal }`), que es la forma que piden
   *  `rendimientosPorNaturaleza` y `plazoPromedio`. */
  peso: number | null
  /** F-046: un FCI valuado no tiene cronograma contractual ni especie en el universo de renta fija
   *  — quien arme el calendario o el vector de riesgo con esta posición lo tiene que saber para
   *  excluirla por clase en vez de tratarla como una posición de renta fija más. */
  esFci: boolean
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
  esFci: boolean
}

export function valuarCartera(
  posiciones: PosicionResuelta[],
  porTicker: ReadonlyMap<string, Especie>,
  tipoDeCambio: number | null,
): CarteraValuada {
  const intermedias: Intermedia[] = []
  const excluidas: PosicionExcluidaValuacion[] = []

  for (const pos of posiciones) {
    // F-046: un `codigo_cafci` matcheado por F-029 no es una especie del universo de renta fija
    // (`pos.resuelta` es `false` por construcción), así que se valúa aparte y antes de caer en
    // `no_resuelta` — que sería indistinguible de un ticker mal escrito.
    if (pos.motivo === 'es_fci' && pos.fondo_fci !== null) {
      const resultado = valuarFci(pos, pos.fondo_fci, tipoDeCambio)
      if ('excluida' in resultado) excluidas.push(resultado.excluida)
      else intermedias.push(resultado.intermedia)
      continue
    }

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
    intermedias.push({ id: pos.id, ticker: pos.ticker, invertido, monedaCotizacion, esFci: false })
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
    const pesoReal = totalInvertidoUsd > 0 ? (i.invertidoUsd / totalInvertidoUsd) * 100 : null
    return {
      ticker: i.ticker,
      invertido: i.invertido,
      invertidoUsd: i.invertidoUsd,
      pesoReal,
      peso: pesoReal,
      esFci: i.esFci,
    }
  })

  return { valuadas, excluidas, totalInvertidoUsd }
}

/**
 * Valúa una posición identificada como FCI (F-046) — separado de la matemática de bonos porque no
 * hay precio cada 100 VN: `pos.nominal` se interpreta como cuotapartes suscriptas, que es la única
 * magnitud que un resumen de cuenta declara para un fondo (no hay otro casillero disponible).
 */
function valuarFci(
  pos: PosicionResuelta,
  fondo: NonNullable<PosicionResuelta['fondo_fci']>,
  tipoDeCambio: number | null,
): { intermedia: Intermedia } | { excluida: PosicionExcluidaValuacion } {
  if (pos.nominal === null) {
    return { excluida: { id: pos.id, motivo: 'sin_nominal', montoDeclarado: pos.monto } }
  }
  // Sin fila en la planilla de hoy (el fondo desapareció, o esta corrida no lo trajo): se declara
  // distinto de "sin_precio" genérico porque acá el instrumento sí se identificó.
  if (fondo.vcp === null) {
    return { excluida: { id: pos.id, motivo: 'fci_sin_vcp', montoDeclarado: pos.monto } }
  }

  const monedaCruda = fondo.moneda.toLowerCase()
  let monedaCotizacion: 'usd' | 'ars'
  if (monedaCruda === 'usd') monedaCotizacion = 'usd'
  else if (monedaCruda === 'ars') monedaCotizacion = 'ars'
  else {
    // `USB` de CAFCI, u otra moneda que no sea `usd`/`ars`: nunca se convierte (regla 3).
    return { excluida: { id: pos.id, motivo: 'fci_moneda_no_convertible', montoDeclarado: pos.monto } }
  }
  if (monedaCotizacion === 'ars' && tipoDeCambio === null) {
    return { excluida: { id: pos.id, motivo: 'sin_tipo_de_cambio', montoDeclarado: pos.monto } }
  }

  const invertido = pos.nominal * (fondo.vcp / 1000)
  return { intermedia: { id: pos.id, ticker: fondo.fondo, invertido, monedaCotizacion, esFci: true } }
}
