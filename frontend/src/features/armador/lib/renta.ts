/**
 * F-021 se movió a `@/lib/cartera/renta` en la Tanda 11 (deuda de `plan.md:2581`, saldada para
 * que el diagnóstico de cartera de F-030 calcule con las mismas funciones). Re-exportado acá para
 * no editar los importadores existentes del armador.
 */

export {
  columnasDeCordillera,
  picoDeColumnas,
  invertidoPorMoneda,
  calcularRentaAnualPorMoneda,
} from '@/lib/cartera/renta'
export type {
  SegmentoDeMes,
  ColumnaCordillera,
  MesDeRenta,
  RentaAnualPorMoneda,
} from '@/lib/cartera/renta'
