/**
 * El mix pedido entre renta fija y renta variable — Etapa 3 del rediseño del armador, base para
 * declarar en la cabecera de `CarteraEditable` y de `BloqueRentaVariable` un solo número
 * consistente en las dos pantallas.
 *
 * Funciones puras sobre `PosicionArmador.peso` (puntos porcentuales sobre la cartera **entera**,
 * ver `store/carteraStore.tsx`): no leen precio ni tipo de cambio, así que no dependen de que el
 * universo haya resuelto nada. El mix *real* (sobre lo efectivamente invertido en dólares) es otra
 * cuenta — cada consumidor la arma con sus propios subtotales resueltos, porque ahí sí hace falta
 * declarar `s/d` cuando falta precio o tipo de cambio (regla 1 del dominio).
 */

import { posicionesRentaFija, posicionesRentaVariable, type PosicionArmador } from '../store/carteraStore'

export function sumaPesos(pos: readonly { peso: number }[]): number {
  return pos.reduce((acumulado, p) => acumulado + p.peso, 0)
}

export interface MixPedido {
  rf: number
  rv: number
}

/** `rf` incluye FCI, igual que `posicionesRentaFija` — es "todo lo que no es renta variable". */
export function mixPedido(pos: readonly PosicionArmador[]): MixPedido {
  return {
    rf: sumaPesos(posicionesRentaFija(pos)),
    rv: sumaPesos(posicionesRentaVariable(pos)),
  }
}

/** El objetivo declarado, ya abierto en sus dos lados. `null` sin objetivo (ver `objetivoRv`). */
export function objetivoMix(objetivoRv: number | null): MixPedido | null {
  return objetivoRv === null ? null : { rf: 100 - objetivoRv, rv: objetivoRv }
}

/** Cuánto pesa el objetivo declarado antes de que valga la pena señalar el desvío, en puntos
 *  porcentuales. Medio punto es el ruido normal de redondear pesos a un decimal y repartir el
 *  residuo (`normalizarA100`); marcarlo sería gritar por la aritmética de la propia pantalla. */
export const TOLERANCIA_OBJETIVO = 0.5

export interface DesvioObjetivo {
  objetivo: MixPedido
  logrado: MixPedido
  /** `logrado.rv - objetivo.rv`, en puntos porcentuales. Positivo = hay más renta variable de la
   *  pedida. El de renta fija es el mismo número con el signo cambiado, así que no se guarda. */
  desvioRv: number
  /** `true` cuando el desvío supera la tolerancia y merece mostrarse. */
  fueraDeTolerancia: boolean
}

/** Compara lo que se declaró contra lo que la cartera tiene hoy. `null` sin objetivo declarado:
 *  sin mandato no hay desvío que reportar, y no se inventa uno con el default de un perfil. */
export function desvioContraObjetivo(
  objetivoRv: number | null,
  logrado: MixPedido,
): DesvioObjetivo | null {
  const objetivo = objetivoMix(objetivoRv)
  if (objetivo === null) return null
  const desvioRv = logrado.rv - objetivo.rv
  return {
    objetivo,
    logrado,
    desvioRv,
    fueraDeTolerancia: Math.abs(desvioRv) > TOLERANCIA_OBJETIVO,
  }
}
