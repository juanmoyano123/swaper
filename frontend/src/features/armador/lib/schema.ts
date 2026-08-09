/**
 * El contrato del calendario (F-015/F-016) y de una especie del universo (F-015/F-018) se
 * movieron a `@/lib/cartera/esquemaCalendario` y `@/lib/cartera/esquemaEspecie` en la Tanda 11 —
 * deuda de `plan.md:2581`, saldada para que el diagnóstico de cartera de F-030 lea exactamente el
 * mismo contrato en vez de duplicarlo (riesgo R12 de `plan.md:2774`). Re-exportados acá para no
 * editar los ~20 importadores existentes del armador.
 *
 * Lo que sigue abajo (F-025, carga de lámina) no es una métrica compartida — es un contrato de
 * escritura propio del armador, y se queda acá.
 */

export {
  esquemaSeveridadCalendario,
  esquemaAlertaCalendario,
  esquemaInstrumentoDelMes,
  esquemaMesDelCalendario,
  esquemaCalendarioUniverso,
} from '@/lib/cartera/esquemaCalendario'
export type {
  SeveridadCalendario,
  AlertaCalendario,
  InstrumentoDelMes,
  MesDelCalendario,
  CalendarioUniverso,
} from '@/lib/cartera/esquemaCalendario'

export { esquemaEspecie, esquemaTipoDeCambio } from '@/lib/cartera/esquemaEspecie'
export type { Especie, RespuestaTipoDeCambio } from '@/lib/cartera/esquemaEspecie'

import { z } from 'zod'

/**
 * `POST /api/v1/condiciones/{ticker}/lamina` — F-025. Sólo el camino 200: el 409 de conflicto no
 * pasa por acá, `apiFetch` lanza antes de validar el cuerpo contra ningún esquema en ese caso (ver
 * `useCargarLamina.ts`, que lee el conflicto de `ApiError.details`).
 */
export const esquemaResultadoCargaLamina = z.object({
  guardado: z.literal(true),
  ticker: z.string(),
  lamina: z.number(),
  lamina_origen: z.string(),
  lamina_fecha: z.string(),
})

export type ResultadoCargaLamina = z.infer<typeof esquemaResultadoCargaLamina>

/** El shape de `Conflicto.como_dict()` (`app/condiciones/resolucion.py`), tal cual viaja en el
 *  cuerpo del 409: los dos valores en pugna, por ticker, sin que el sistema elija ninguno. */
export const esquemaConflictoLamina = z.object({
  campo: z.string(),
  emision: z.string(),
  valores: z.record(z.string(), z.number()),
})

export type ConflictoLamina = z.infer<typeof esquemaConflictoLamina>
