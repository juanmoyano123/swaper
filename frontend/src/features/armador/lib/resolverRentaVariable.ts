/**
 * El motor de F-026: de peso pedido a cantidad de unidades e invertido, para acciones y CEDEARs.
 *
 * Hermano de `resolver.ts` pero no el mismo módulo, porque la matemática es distinta a propósito.
 * `resolver.ts` calcula bonos: precio cada 100 VN, redondeo a lámina. Una acción o un CEDEAR se
 * compra por **unidad entera** — no hay lámina, no hay VN, el precio ya es el precio de la unidad.
 * Mezclar las dos cosas en una función habría significado ramas `if (esRentaVariable)` por todos
 * lados de `resolver.ts`, en un módulo que F-018/F-020/F-021 ya tienen congelado.
 *
 * **Nunca redondea hacia arriba.** `Math.floor(objetivo / precio)` es el mismo criterio que la
 * lámina en `resolver.ts`: comprar de más que lo pedido no es una aproximación razonable.
 *
 * **La moneda de cotización viaja cruda de BYMA** (`ARS` / `USD` / `EXT`, ver
 * `lib/rentaVariable.ts` y `components/SelectorMoneda.tsx`), a diferencia de `resolver.ts` que
 * recibe la de `Especie` ya bajada a minúscula por `useCarteraResuelta`. Acá no hay ese paso
 * intermedio, así que se compara contra los literales en mayúscula tal como llegan. `EXT` no se
 * interpreta (regla 11 del dominio): la posición queda sin resolver, igual que si no cotizara.
 */

export interface EntradaRentaVariable {
  ticker: string
  /** Pedido, en puntos porcentuales sobre el total de la cartera (no sólo del bloque de RV):
   *  mismo eje que `PosicionArmador.peso` en el store. */
  peso: number
  /** En la moneda de cotización de la especie. `null` = sin precio publicado hoy. */
  precio: number | null
  /** Código crudo de BYMA: `'ARS'`, `'USD'`, `'EXT'`, u otro no documentado. `null` = sin declarar. */
  monedaCotizacion: string | null
}

export interface PosicionRvResuelta {
  ticker: string
  peso: number
  /** Unidades enteras a comprar. `null` si no se pudo calcular. */
  cantidad: number | null
  /** `cantidad * precio`, en la moneda de cotización de la especie. */
  invertido: number | null
  /** Normalizado a USD con el tipo de cambio implícito del propio universo (regla 3), cuando la
   *  especie cotiza en ARS. */
  invertidoUsd: number | null
  /** `invertidoUsd / Σ invertidoUsd(bloque de renta variable) * 100`. Es el peso real **dentro del
   *  bloque**, no de la cartera entera — a diferencia de `resolver.ts`, que reparte sobre el total. */
  pesoReal: number | null
}

function sinResolver(entrada: EntradaRentaVariable): PosicionRvResuelta {
  return {
    ticker: entrada.ticker,
    peso: entrada.peso,
    cantidad: null,
    invertido: null,
    invertidoUsd: null,
    pesoReal: null,
  }
}

export function resolverRentaVariable(
  entradas: EntradaRentaVariable[],
  montoTotalUsd: number,
  tipoDeCambio: number | null,
): PosicionRvResuelta[] {
  const resueltas = entradas.map((entrada): PosicionRvResuelta => {
    if (entrada.precio === null || montoTotalUsd === 0) return sinResolver(entrada)

    const precio = entrada.precio
    const objetivoUsd = (montoTotalUsd * entrada.peso) / 100

    let objetivo: number
    if (entrada.monedaCotizacion === 'USD') {
      objetivo = objetivoUsd
    } else if (entrada.monedaCotizacion === 'ARS') {
      // Nunca se inventa un tipo de cambio externo (regla 3): sin el implícito del propio
      // universo, esta posición no se puede resolver y se declara, no se estima.
      if (tipoDeCambio === null) return sinResolver(entrada)
      objetivo = objetivoUsd * tipoDeCambio
    } else {
      // `EXT`, otro código sin documentar, o sin declarar: no se interpreta (regla 11).
      return sinResolver(entrada)
    }

    const cantidad = Math.floor(objetivo / precio)
    const invertido = cantidad * precio
    const invertidoUsd = entrada.monedaCotizacion === 'ARS' && tipoDeCambio !== null ? invertido / tipoDeCambio : invertido

    return {
      ticker: entrada.ticker,
      peso: entrada.peso,
      cantidad,
      invertido,
      invertidoUsd,
      pesoReal: null,
    }
  })

  const sumaInvertidoUsd = resueltas.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)

  return resueltas.map((r) => ({
    ...r,
    pesoReal:
      r.invertidoUsd !== null && sumaInvertidoUsd > 0 ? (r.invertidoUsd / sumaInvertidoUsd) * 100 : null,
  }))
}

/** Σ `invertidoUsd` del bloque, ignorando las que no se pudieron resolver. `null` si ninguna se
 *  resolvió: un subtotal que no existe no es 0 (mismo criterio que `resumenAjuste` en `resolver.ts`). */
export function subtotalRentaVariableUsd(resueltas: PosicionRvResuelta[]): number | null {
  const resueltasConMonto = resueltas.filter((r) => r.invertidoUsd !== null)
  if (resueltasConMonto.length === 0) return null
  return resueltasConMonto.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)
}
