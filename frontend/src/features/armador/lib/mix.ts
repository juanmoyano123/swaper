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
