/**
 * F-022 se movió a `@/lib/cartera/metricas` en la Tanda 11 (deuda de `plan.md:2581`, saldada para
 * que el diagnóstico de cartera de F-030 calcule con las mismas funciones). Re-exportado acá para
 * no editar los importadores existentes del armador.
 */

export {
  rendimientosPorNaturaleza,
  plazoPromedio,
  sensibilidadPorSegmento,
} from '@/lib/cartera/metricas'
export type {
  RendimientoPorNaturaleza,
  SensibilidadPorSegmento,
} from '@/lib/cartera/metricas'
