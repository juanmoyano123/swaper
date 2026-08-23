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

/** Por qué una posición quedó sin resolver — sólo se puebla en las ramas donde hace falta
 *  distinguir el motivo (F-046, FCI); el resto de los casos sigue sin motivo explícito, igual que
 *  antes de F-046 (la pantalla ya lo explica genéricamente por "sin precio o sin tipo de cambio"). */
export type MotivoSinResolver =
  | 'fci_sin_vcp'
  /** Sin `codigoCafci` (FCI legado) o con código pero sin fila en la planilla de hoy: los dos casos
   *  colapsan en lo mismo desde acá — `vcpPorMil` vino `null` — y la distinción de cuál de los dos
   *  es la queda del lado de quien arma `EntradaResolver` (F-046, punto 2). */
  | 'fci_moneda_no_convertible'
  /** La moneda del fondo no es `usd` ni `ars` (p. ej. `USB` de CAFCI): nunca se convierte
   *  (regla 3 del proyecto). */
  | 'sin_tipo_de_cambio'

export interface EntradaResolver {
  ticker: string
  /** Pedido, en puntos porcentuales (16.5 = 16,5%). */
  peso: number
  /** En la moneda de cotización de la especie. `null` = FCI o sin precio conocido. */
  precio: number | null
  /** Moneda de cotización de la especie, o moneda propia del fondo cuando `esFci` (F-046):
   *  `'usb'` u otra distinta de `'usd'`/`'ars'` nunca se convierte (regla 3 del proyecto). */
  monedaCotizacion: 'usd' | 'ars' | string
  /** `null` = sin dato: no se redondea a ningún múltiplo (regla 1 del proyecto). Sin sentido en un
   *  FCI — un fondo suscribe fracciones de cuotaparte, no nominales — así que siempre viaja `null`
   *  ahí y `resolver()` nunca lo usa en esa rama. */
  lamina: number | null
  esFci: boolean
  /** Valor de cuotaparte de hoy, por cada MIL cuotapartes tal como CAFCI lo publica (F-046, F-057).
   *  `null` = sin código CAFCI identificado o sin fila en la planilla de hoy: la posición queda sin
   *  resolver, nunca se redondea a lámina ni se convierte. Irrelevante cuando `!esFci`. */
  vcpPorMil: number | null
  /** Fecha del valor de cuotaparte usado, tal como la publica CAFCI. Sólo declarativa: `resolver`
   *  no la usa para calcular nada. Irrelevante cuando `!esFci`. */
  fechaVcp: string | null
}

export interface PosicionResuelta {
  ticker: string
  peso: number
  /** Valor nominal asignado. `null` si no se pudo calcular, o siempre en un FCI: no hay lámina que
   *  redondear — un fondo suscribe fracciones de cuotaparte, no nominales (F-046). */
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
  /** Cuotapartes suscriptas, derivado de `invertido / (vcpPorMil / 1000)` — sólo para mostrar, en
   *  un FCI resuelto. `null` en renta fija y en cualquier FCI sin resolver (F-046). */
  cuotapartes: number | null
  /** Por qué no se pudo resolver. `null` cuando resolvió, y también en la mayoría de los casos sin
   *  resolver de renta fija (la pantalla ya declara "sin precio o sin tipo de cambio" ahí sin
   *  necesitar un código). Poblado en las ramas de FCI donde el motivo importa distinguir. */
  motivo: MotivoSinResolver | null
}

function sinResolver(entrada: EntradaResolver, motivo: MotivoSinResolver | null = null): PosicionResuelta {
  return {
    ticker: entrada.ticker,
    peso: entrada.peso,
    vn: null,
    invertido: null,
    invertidoUsd: null,
    pesoReal: null,
    laminaConocida: entrada.lamina !== null,
    esFci: entrada.esFci,
    cuotapartes: null,
    motivo,
  }
}

/**
 * Un FCI se valúa aparte de un bono: no hay precio cada 100 VN ni lámina — se convierte el monto
 * objetivo a la moneda del fondo y se derivan las cuotapartes, sin redondear a ningún múltiplo
 * (regla 1 del proyecto: suscribir fracciones de cuotaparte no es una aproximación, es lo que un
 * FCI permite de verdad).
 */
function resolverFci(
  entrada: EntradaResolver,
  montoTotalUsd: number,
  tipoDeCambio: number | null,
): PosicionResuelta {
  if (montoTotalUsd === 0) return sinResolver(entrada)
  if (entrada.vcpPorMil === null) return sinResolver(entrada, 'fci_sin_vcp')

  const objetivoUsd = (montoTotalUsd * entrada.peso) / 100

  let invertido: number
  if (entrada.monedaCotizacion === 'usd') {
    invertido = objetivoUsd
  } else if (entrada.monedaCotizacion === 'ars') {
    // Nunca se inventa un tipo de cambio externo (regla 3 del proyecto): sin el implícito del
    // propio universo, esta posición no se puede resolver y se declara, no se estima.
    if (tipoDeCambio === null) return sinResolver(entrada, 'sin_tipo_de_cambio')
    invertido = objetivoUsd * tipoDeCambio
  } else {
    // `USB` de CAFCI, u otra moneda que no sea `usd`/`ars`: nunca se convierte (regla 3).
    return sinResolver(entrada, 'fci_moneda_no_convertible')
  }

  const invertidoUsd =
    entrada.monedaCotizacion === 'ars' && tipoDeCambio !== null ? invertido / tipoDeCambio : invertido
  const cuotapartes = invertido / (entrada.vcpPorMil / 1000)

  return {
    ticker: entrada.ticker,
    peso: entrada.peso,
    vn: null,
    invertido,
    invertidoUsd,
    pesoReal: null,
    laminaConocida: entrada.lamina !== null,
    esFci: true,
    cuotapartes,
    motivo: null,
  }
}

export function resolver(
  posiciones: EntradaResolver[],
  montoTotalUsd: number,
  tipoDeCambio: number | null,
): PosicionResuelta[] {
  const resueltas = posiciones.map((entrada): PosicionResuelta => {
    if (entrada.esFci) return resolverFci(entrada, montoTotalUsd, tipoDeCambio)
    if (entrada.precio === null || montoTotalUsd === 0) return sinResolver(entrada)

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
      cuotapartes: null,
      motivo: null,
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
