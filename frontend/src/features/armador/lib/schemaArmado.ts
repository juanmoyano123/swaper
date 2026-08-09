/**
 * El contrato de `POST /api/v1/armado` — F-019.
 *
 * Archivo propio y no `lib/schema.ts`, mismo criterio que `schemaConcentracion.ts` (F-020): varias
 * features de esta tanda tocan `lib/schema.ts` en paralelo, y un contrato por archivo evita que dos
 * agentes editen el mismo al mismo tiempo.
 *
 * La forma exacta sale de `backend/app/armado/motor.py::ResultadoArmado.como_dict()`. Las alertas
 * usan el mismo shape que las de calendario/concentración (`Alerta.como_dict()`): se redefinen acá
 * en vez de importarse de otro archivo por la misma razón de coordinación.
 */

import { z } from 'zod'

export const esquemaAlertaArmado = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.enum(['error', 'advertencia', 'info']),
  /** Siempre `null` en esta feature: informa, no bloquea. */
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

export const esquemaPosicionArmada = z.object({
  ticker: z.string(),
  /** En puntos porcentuales, post-reponderación. */
  pct_cartera: z.number(),
  monto: z.number(),
})

export const esquemaResultadoArmado = z.object({
  posiciones: z.array(esquemaPosicionArmada),
  mix_aplicado: z.record(z.string(), z.number()),
  origen_mix: z.string(),
  perfil: z.string(),
  sectores: z.object({
    presentes: z.number(),
    minimo: z.number(),
    suficiente: z.boolean(),
  }),
  alertas: z.array(esquemaAlertaArmado),
})

export type PosicionArmada = z.infer<typeof esquemaPosicionArmada>
export type ResultadoArmado = z.infer<typeof esquemaResultadoArmado>
export type AlertaArmado = z.infer<typeof esquemaAlertaArmado>

/** Los cinco campos del mandato del cliente que pide la ficha de F-019 -- monto, moneda de
 *  referencia, objetivo de cobertura, perfil y horizonte. Espejo de `ParametrosArmado` del
 *  backend, recortado a lo que el formulario expone (sin `mix` manual, `n_total`, `min_rend` ni
 *  `pago_mensual`: la ficha no los menciona como parte del input de esta feature). */
export interface ParametrosArmadoAsistido {
  monto: number
  moneda: 'usd' | 'ars' | 'todas'
  cobertura: 'devaluacion' | 'inflacion' | 'tasa-pesos' | 'mixta'
  perfil: 'conservador' | 'moderado' | 'agresivo'
  horizonte: 'corto' | 'medio' | 'largo'
}
