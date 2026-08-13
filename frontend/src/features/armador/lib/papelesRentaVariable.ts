/**
 * Las especies de renta variable, agrupadas en papeles para el buscador.
 *
 * El backend ya dice qué especies son el mismo papel (`emision`, `sufijo_liquidacion`) y lo
 * contrasta contra el tipo de cambio del universo antes de afirmarlo — ver
 * `app/renta_variable/agrupamiento.py`. Acá sólo se arma la vista: **una fila por papel, con sus
 * monedas al lado**, en vez de tres filas sueltas que el asesor tiene que reconocer como el mismo
 * CEDEAR.
 *
 * Es el mismo criterio que la grilla de renta fija ya usa con AL30 / AL30C / AL30D, ahora que la
 * renta variable tiene el dato para hacerlo.
 */

import type { EspecieRentaVariable } from '@/lib/rentaVariable'

/** Cómo se rotula cada moneda de liquidación en pantalla. */
export const ROTULO_MONEDA: Record<string, string> = {
  ARS: 'ARS',
  C: 'Cable',
  D: 'MEP',
}

/** El grupo de las especies que la fuente no explica. Espejo de `NO_IDENTIFICADO` del backend. */
export const NO_IDENTIFICADO = 'n/n'

export interface EspecieDelPapel {
  especie: EspecieRentaVariable
  /** `'ARS'`, `'Cable'` o `'MEP'`. */
  rotulo: string
  /** `true` si esta especie operó hoy. La pestaña de una que no operó no se ofrece para comprar:
   *  sin precio no hay con qué resolver nominales (`lib/resolverRentaVariable.ts`). */
  opera: boolean
}

export interface PapelRentaVariable {
  /** El ticker del papel — el de la especie en pesos cuando existe. */
  emision: string
  /** Todas sus especies, ordenadas ARS → MEP → Cable. */
  especies: EspecieDelPapel[]
  /** La especie que representa al papel en la lista: la que opera con más volumen, o la primera. */
  representante: EspecieRentaVariable
  /** `true` cuando ninguna de sus especies se puede identificar. */
  noIdentificado: boolean
}

/** ARS primero, después MEP, después Cable: el orden en que el asesor los piensa. */
const ORDEN_MONEDA: Record<string, number> = { ARS: 0, D: 1, C: 2 }

function rotuloDe(especie: EspecieRentaVariable): string {
  if (especie.sufijo_liquidacion === null) return ROTULO_MONEDA.ARS
  return ROTULO_MONEDA[especie.sufijo_liquidacion] ?? especie.sufijo_liquidacion
}

/**
 * Agrupa las especies en papeles.
 *
 * El representante es el que más volumen mueve — **en dólares**, nunca el crudo: el crudo está en
 * la moneda de cada especie y la que cotiza en pesos siempre ganaría por el tipo de cambio y no
 * por liquidez. Es el mismo desempate que `universo/emisiones.py` usa para elegir qué especie
 * representa a un bono.
 *
 * Las no identificadas van cada una a su propio papel y **no se mezclan entre sí**: compartir el
 * cajón de lo desconocido no las hace el mismo CEDEAR.
 */
export function agruparEnPapeles(especies: EspecieRentaVariable[]): PapelRentaVariable[] {
  const porEmision = new Map<string, EspecieRentaVariable[]>()
  for (const especie of especies) {
    // Sin `emision` (respuesta de un backend anterior a esta feature) cada especie es su papel:
    // se degrada a la vista de antes en vez de romper.
    const clave = especie.no_identificado
      ? `${NO_IDENTIFICADO}:${especie.ticker}`
      : (especie.emision ?? especie.ticker)
    const grupo = porEmision.get(clave)
    if (grupo) grupo.push(especie)
    else porEmision.set(clave, [especie])
  }

  const papeles: PapelRentaVariable[] = []
  for (const [clave, grupo] of porEmision) {
    const ordenadas = [...grupo].sort(
      (a, b) =>
        (ORDEN_MONEDA[a.sufijo_liquidacion ?? 'ARS'] ?? 9) -
        (ORDEN_MONEDA[b.sufijo_liquidacion ?? 'ARS'] ?? 9),
    )
    papeles.push({
      emision: clave.startsWith(`${NO_IDENTIFICADO}:`) ? grupo[0].ticker : clave,
      especies: ordenadas.map((especie) => ({
        especie,
        rotulo: rotuloDe(especie),
        opera: especie.precio !== null && especie.precio > 0,
      })),
      representante: elegirRepresentante(ordenadas),
      noIdentificado: grupo.every((e) => e.no_identificado),
    })
  }
  return papeles
}

function elegirRepresentante(especies: EspecieRentaVariable[]): EspecieRentaVariable {
  let mejor = especies[0]
  for (const especie of especies) {
    const volumen = especie.volumen_usd ?? -1
    const volumenMejor = mejor.volumen_usd ?? -1
    if (volumen > volumenMejor) mejor = especie
  }
  return mejor
}

/** Si alguna especie del papel coincide con la búsqueda, el papel entero coincide: buscar `AAPLD`
 *  tiene que encontrar a Apple aunque su representante sea `AAPL`. */
export function papelCoincide(papel: PapelRentaVariable, busqueda: string): boolean {
  const texto = busqueda.trim().toLowerCase()
  if (texto === '') return true
  return papel.especies.some(({ especie }) => {
    return (
      especie.ticker.toLowerCase().includes(texto) ||
      (especie.nombre_corto?.toLowerCase().includes(texto) ?? false) ||
      (especie.nombre_largo?.toLowerCase().includes(texto) ?? false)
    )
  })
}
