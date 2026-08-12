/**
 * Cómo se agrupa la cartera para leerla — Tanda 13. Movido acá en la Tanda 18 (F-042) desde
 * `features/armador/lib/bloques.ts`, para que el export (que trabaja sobre un snapshot congelado,
 * no sobre `PosicionArmador` en vivo) use la misma constante de orden y el mismo mapa de clase que
 * el armador — mismo criterio que las demás promociones de la Tanda 11 (`useCalendarioCartera`,
 * `useConcentracion`, `esquemaEspecie`). El armador re-exporta este archivo para no editar sus
 * importadores existentes.
 *
 * El formato de referencia de la mesa (`referencia/carteras-sugeridas-ifa.xlsx`) presenta siempre
 * la misma estructura: bloques por clase de activo, cada uno con su subtotal, y recién al final los
 * indicadores de la cartera entera. Es la forma en que el asesor lee una cartera —"cuánto tengo en
 * soberano, cuánto en corporativo, cuánto en acciones"— y no coincide con el orden de
 * incorporación, que es como estaba listada hasta acá.
 *
 * **Los bloques salen de `clase_activo`, que es dato de la fuente, no de una regla nuestra.** Un
 * ticker que no cruzó contra el universo, o que trae una clase que no está en la tabla, cae en "sin
 * clasificar" y se muestra igual: esconderlo o meterlo en el bloque más parecido sería inventar
 * (reglas 1 y 11). Ese bloque aparece sólo cuando tiene contenido, así que en una cartera sana no
 * se ve.
 */

import type { PosicionArmador } from '@/features/armador/store/carteraStore'

/** Los bloques, en el orden en que se muestran. Es el del Excel de la mesa. */
export const ORDEN_DE_BLOQUES = [
  'soberanos',
  'corporativos',
  'fci',
  'sin_clasificar',
  'renta_variable',
] as const

export type IdBloque = (typeof ORDEN_DE_BLOQUES)[number]

export const ROTULO_DE_BLOQUE: Record<IdBloque, string> = {
  soberanos: 'Soberanos y subsoberanos',
  corporativos: 'Corporativos',
  fci: 'Fondos comunes',
  sin_clasificar: 'Sin clasificar',
  renta_variable: 'Renta variable',
}

/** Qué clases de activo caen en qué bloque de renta fija. Exportado (a diferencia del original en
 *  `armador/lib/bloques.ts`): el export de F-042 clasifica filas de un snapshot congelado, no
 *  `PosicionArmador`, así que necesita el mapa directo en vez de pasar por `agruparEnBloques`. */
export const BLOQUE_POR_CLASE_ACTIVO: Record<string, IdBloque> = {
  bono_soberano: 'soberanos',
  bono_subsoberano: 'soberanos',
  on_corporativo: 'corporativos',
}

export interface BloqueDeCartera {
  id: IdBloque
  rotulo: string
  posiciones: PosicionArmador[]
  /** Suma de los pesos pedidos del bloque, en puntos porcentuales. */
  pesoPedido: number
}

/**
 * Reparte las posiciones en bloques, en el orden de `ORDEN_DE_BLOQUES`.
 *
 * `claseActivoDe` resuelve la clase de cada ticker contra el universo; devolver `null`/`undefined`
 * —porque el ticker no cruzó o porque todavía no cargó el universo— manda la posición a "sin
 * clasificar". Los bloques vacíos no se devuelven: la cartera muestra los que tienen algo.
 */
export function agruparEnBloques(
  posiciones: readonly PosicionArmador[],
  claseActivoDe: (ticker: string) => string | null | undefined,
): BloqueDeCartera[] {
  const porBloque = new Map<IdBloque, PosicionArmador[]>()

  for (const posicion of posiciones) {
    const id = bloqueDe(posicion, claseActivoDe(posicion.ticker))
    const acumuladas = porBloque.get(id)
    if (acumuladas) acumuladas.push(posicion)
    else porBloque.set(id, [posicion])
  }

  return ORDEN_DE_BLOQUES.filter((id) => porBloque.has(id)).map((id) => {
    const posicionesDelBloque = porBloque.get(id) as PosicionArmador[]
    return {
      id,
      rotulo: ROTULO_DE_BLOQUE[id],
      posiciones: posicionesDelBloque,
      pesoPedido: posicionesDelBloque.reduce((acumulado, p) => acumulado + p.peso, 0),
    }
  })
}

/** La clase de la posición manda sobre la del universo: un FCI es un FCI aunque cruce con algo. */
function bloqueDe(posicion: PosicionArmador, claseActivo: string | null | undefined): IdBloque {
  if (posicion.clase === 'fci') return 'fci'
  if (posicion.clase === 'renta_variable') return 'renta_variable'
  if (!claseActivo) return 'sin_clasificar'
  return BLOQUE_POR_CLASE_ACTIVO[claseActivo] ?? 'sin_clasificar'
}
