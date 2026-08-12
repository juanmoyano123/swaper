/**
 * F-020 se movió a `@/lib/cartera/esquemaConcentracion` en la Tanda 11 (deuda de `plan.md:2581`,
 * saldada para que el diagnóstico de cartera de F-030 mida los mismos topes). Re-exportado acá
 * para no editar los importadores existentes del armador.
 */

export {
  esquemaAlertaConcentracion,
  esquemaTipoDeTope,
  esquemaEstadoDeTope,
  esquemaTramo,
  esquemaLimites,
  esquemaConcentracion,
  PERFILES,
} from '@/lib/cartera/esquemaConcentracion'
export type {
  AlertaConcentracion,
  TipoDeTope,
  EstadoDeTope,
  TramoConcentracion,
  Concentracion,
  NombreDePerfil,
} from '@/lib/cartera/esquemaConcentracion'
