/**
 * El motor de F-018: de peso pedido a nominales, invertido y peso real. Función pura, sin red —
 * lo único que sabe es lo que se le pasa, así que se testea aislada de la pantalla y del store.
 *
 * Porta el pseudocódigo del design system (sección "State Management", bloque `resolver`)
 * adaptado a lo que hoy se puede calcular: sin moneda de operación todavía (F-019), un solo tipo
 * de cambio implícito para todo lo que cotiza en pesos.
 *
 * **Nunca redondea hacia arriba.** `Math.floor` en la lámina es a propósito: comprar de más que lo
 * pedido no es una aproximación razonable, es plata puesta sin que el asesor la haya pedido.
 *
 * F-024 cablea acá la lámina real, de `condiciones_emision` (vía `/especies`), y agrega
 * `resumenAjuste`: el total ajustado y la cobertura de la cartera viven en este módulo puro para
 * poder testearse sin la pantalla.
 */

export interface EntradaResolver {
  ticker: string
  /** Pedido, en puntos porcentuales (16.5 = 16,5%). */
  peso: number
  /** En la moneda de cotización de la especie. `null` = FCI o sin precio conocido. */
  precio: number | null
  monedaCotizacion: 'usd' | 'ars' | string
  /** `null` = sin dato: no se redondea a ningún múltiplo (regla 1 del proyecto). */
  lamina: number | null
  esFci: boolean
}

export interface PosicionResuelta {
  ticker: string
  peso: number
  /** Valor nominal asignado. `null` si no se pudo calcular. */
  vn: number | null
  /** En la moneda de cotización de la especie. */
  invertido: number | null
  /** Normalizado con el TC implícito cuando la especie cotiza en ARS. */
  invertidoUsd: number | null
  /** `invertidoUsd / Σ invertidoUsd * 100`, sobre las posiciones que sí lo tienen. */
  pesoReal: number | null
  laminaConocida: boolean
  /** Una lámina faltante en un FCI no es un dato faltante: a un FCI no le corresponde lámina.
   *  El resumen de ajuste lo necesita para no contarlo como "lámina no informada". */
  esFci: boolean
}

function sinResolver(entrada: EntradaResolver): PosicionResuelta {
  return {
    ticker: entrada.ticker,
    peso: entrada.peso,
    vn: null,
    invertido: null,
    invertidoUsd: null,
    pesoReal: null,
    laminaConocida: entrada.lamina !== null,
    esFci: entrada.esFci,
  }
}

export function resolver(
  posiciones: EntradaResolver[],
  montoTotalUsd: number,
  tipoDeCambio: number | null,
): PosicionResuelta[] {
  const resueltas = posiciones.map((entrada): PosicionResuelta => {
    if (entrada.esFci || entrada.precio === null || montoTotalUsd === 0) return sinResolver(entrada)

    const precio = entrada.precio
    const objetivoUsd = (montoTotalUsd * entrada.peso) / 100

    let objetivo: number
    if (entrada.monedaCotizacion === 'usd') {
      objetivo = objetivoUsd
    } else if (entrada.monedaCotizacion === 'ars') {
      // Nunca se inventa un tipo de cambio externo (regla 3 del proyecto): sin el implícito del
      // propio universo, esta posición no se puede resolver y se declara, no se estima.
      if (tipoDeCambio === null) return sinResolver(entrada)
      objetivo = objetivoUsd * tipoDeCambio
    } else {
      return sinResolver(entrada)
    }

    let vn: number
    if (entrada.lamina !== null) {
      vn = Math.floor(objetivo / (precio / 100) / entrada.lamina) * entrada.lamina
    } else {
      vn = objetivo / (precio / 100)
    }

    const invertido = (vn * precio) / 100
    const invertidoUsd =
      entrada.monedaCotizacion === 'ars' && tipoDeCambio !== null ? invertido / tipoDeCambio : invertido

    return {
      ticker: entrada.ticker,
      peso: entrada.peso,
      vn,
      invertido,
      invertidoUsd,
      pesoReal: null,
      laminaConocida: entrada.lamina !== null,
      esFci: entrada.esFci,
    }
  })

  const sumaInvertidoUsd = resueltas.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)

  return resueltas.map((r) => ({
    ...r,
    pesoReal:
      r.invertidoUsd !== null && sumaInvertidoUsd > 0 ? (r.invertidoUsd / sumaInvertidoUsd) * 100 : null,
  }))
}

/** Lo que la cabecera del armador declara sobre el redondeo por lámina — F-024. */
export interface ResumenAjuste {
  /** Posiciones a las que una lámina les corresponde (excluye FCI). */
  ajustables: number
  /** De esas, cuántas quedaron sin lámina informada. */
  sinLamina: number
  /** Σ invertidoUsd de las posiciones con lámina informada y resueltas.
   *  `null` cuando ninguna posición ajustable tiene lámina: un total que no existe no es 0. */
  totalAjustadoUsd: number | null
  /** Σ pesoReal de las posiciones sin lámina: el % de la cartera fuera del total ajustado.
   *  `null` cuando ninguna posición está resuelta (no hay cartera medible sobre la que declarar
   *  un porcentaje). Una posición sin lámina y además sin resolver (sin precio o sin TC) cuenta en
   *  `sinLamina` pero no puede aportar al porcentaje: su pesoReal es null y no se le inventa uno. */
  pctSinAjustar: number | null
}

export function resumenAjuste(resueltas: PosicionResuelta[]): ResumenAjuste {
  const ajustables = resueltas.filter((r) => !r.esFci)
  const sinLamina = ajustables.filter((r) => !r.laminaConocida)

  const conLamina = ajustables.filter((r) => r.laminaConocida && r.invertidoUsd !== null)
  const totalAjustadoUsd =
    conLamina.length > 0 ? conLamina.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0) : null

  const resueltasDeLaCartera = resueltas.filter((r) => r.pesoReal !== null)
  const pctSinAjustar =
    resueltasDeLaCartera.length > 0
      ? sinLamina.reduce((acumulado, r) => acumulado + (r.pesoReal ?? 0), 0)
      : null

  return {
    ajustables: ajustables.length,
    sinLamina: sinLamina.length,
    totalAjustadoUsd,
    pctSinAjustar,
  }
}
