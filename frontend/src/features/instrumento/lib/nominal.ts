/**
 * Monto a invertir → nominal, redondeado hacia abajo a la lámina mínima cuando se la conoce.
 * Mismo criterio que el armador de cartera (F-018, `features/armador/lib/resolver.ts`): comprar de
 * más que lo pedido no es una aproximación razonable, es plata puesta sin que el asesor la pidiera.
 * Se reescribe acá en vez de importarse porque `features/armador` es de otra feature — mismo
 * criterio de aislamiento que ya documenta `FichaInstrumento.tsx` para `descargarBlob`.
 */
export function nominalDesdeMonto(monto: number, precio: number, lamina: number | null): number {
  const nominalCrudo = monto / (precio / 100)
  if (lamina === null || lamina <= 0) return nominalCrudo
  return Math.floor(nominalCrudo / lamina) * lamina
}
