/**
 * Umbrales de color de la paridad, compartidos por el monitor y la ficha del instrumento — F-038
 * y el bloque de residual/valor técnico (17/08/2026).
 *
 * En fracción del valor técnico. **No son un juicio sobre el papel**: la paridad es un dato duro
 * —precio sucio sobre valor técnico— y esto sólo la hace legible de un vistazo. Los cortes están
 * en los dos lugares obvios, la par (1,00) y el descuento fuerte, y no en percentiles del
 * universo: un corte relativo movería el color de un bono sin que el bono se moviera.
 *
 * Extraído de `TablaUniverso.tsx` para que la ficha del instrumento use exactamente el mismo
 * criterio: dos umbrales duplicados divergirían la primera vez que alguien ajuste uno de los dos
 * sin acordarse del otro.
 */

export const PARIDAD_SOBRE_LA_PAR = 1
export const PARIDAD_DESCUENTO_FUERTE = 0.8

export function colorDeParidad(paridad: number | null): string {
  if (paridad === null) return 'var(--tx)'
  if (paridad >= PARIDAD_SOBRE_LA_PAR) return 'var(--pos)'
  if (paridad < PARIDAD_DESCUENTO_FUERTE) return 'var(--neg)'
  return 'var(--tx)'
}
