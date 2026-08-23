/**
 * Cuánto de la cartera quedó afuera del calendario de cupones porque no le corresponde tener
 * cronograma — F-046. Hoy el único caso es el FCI: la regla 5 del proyecto hace del calendario un
 * criterio de armado, y un FCI no tiene flujo contractual que proyectar (no es un bono, es una
 * cuotaparte). `useCarteraResuelta` ya excluye el FCI del POST a `/calendario/cartera` por clase —
 * ver ese hook—, así que este helper es la otra mitad: sumar aparte lo que se excluyó, en vez de
 * dejar que desaparezca en silencio.
 *
 * Es a propósito **otro concepto** que `instrumento_sin_cronograma` (`app/calendario/alertas.py`):
 * esa alerta dice "el dato falta" sobre un instrumento de renta fija que debería tener cronograma y
 * no lo tiene en la fuente. Este helper dice "no le corresponde tener cronograma" sobre un FCI, que
 * nunca lo va a tener. Confundir los dos textos haría pensar que un hueco de dato y un hueco
 * estructural son arreglables de la misma forma.
 *
 * Función pura, sin red: recibe lo que `useCarteraResuelta` ya calculó.
 */

/** Lo mínimo que hace falta de una posición resuelta para medir su porción sin cronograma. */
export interface PosicionParaPorcion {
  esFci: boolean
  /** `invertidoUsd` del resolver — `null` cuando la posición no se pudo valuar. */
  invertidoUsd: number | null
}

export interface PorcionSinCronograma {
  /** Σ `invertidoUsd` de las posiciones FCI resueltas. 0 cuando no hay ninguna — es una suma de
   *  cero términos, no un dato faltante. */
  montoFciUsd: number
  /** `montoFciUsd / totalInvertidoUsd * 100`. `null` cuando no hay total sobre el cual medir un
   *  porcentaje (cartera sin ninguna posición resuelta) — no calcularlo no es que dé cero. */
  pctFci: number | null
  /** Cuántas posiciones FCI entran en `montoFciUsd`. Las que no se pudieron valuar no suman monto,
   *  pero siguen siendo FCI: `cantidadFci` cuenta todas, `montoFciUsd` sólo lo que se pudo medir. */
  cantidadFci: number
}

export function porcionSinCronograma(
  resueltas: readonly PosicionParaPorcion[],
  totalInvertidoUsd: number,
): PorcionSinCronograma {
  const fci = resueltas.filter((r) => r.esFci)
  const montoFciUsd = fci.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)
  const pctFci = totalInvertidoUsd > 0 ? (montoFciUsd / totalInvertidoUsd) * 100 : null

  return { montoFciUsd, pctFci, cantidadFci: fci.length }
}
