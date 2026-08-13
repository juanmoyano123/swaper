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
  /** Qué lado de la cartera armó esta posición (Tanda 13). El motor sigue eligiendo sólo bonos;
   *  las acciones las elige el endpoint aparte, por liquidez y diversificación sectorial. */
  clase: z.enum(['renta_fija', 'renta_variable']),
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
  /** Cuánto del 100% terminó en renta variable. Puede ser menor al pedido —hasta 0— si no hubo
   *  candidatos; en ese caso la alerta `rv_sin_candidatos` lo explica y la renta fija queda
   *  ocupando la cartera entera, sin reescalar. */
  pct_rv_aplicado: z.number(),
  alertas: z.array(esquemaAlertaArmado),
})

export type PosicionArmada = z.infer<typeof esquemaPosicionArmada>
export type ResultadoArmado = z.infer<typeof esquemaResultadoArmado>
export type AlertaArmado = z.infer<typeof esquemaAlertaArmado>

/** El mandato del cliente. Espejo de `ParametrosArmado` del backend, recortado a lo que el
 *  formulario expone: sin `mix` manual ni `n_total`, y sin `pago_mensual` —que el backend declara
 *  pero su motor todavía no consume (ver `app/armado/motor.py`: "el desempate por calendario no se
 *  portó"), así que exponerlo prometería un efecto que no ocurre. */
export interface ParametrosArmadoAsistido {
  monto: number
  moneda: 'usd' | 'ars' | 'todas'
  cobertura: 'devaluacion' | 'inflacion' | 'tasa-pesos' | 'mixta'
  perfil: 'conservador' | 'moderado' | 'agresivo'
  horizonte: 'corto' | 'medio' | 'largo'
  /** Qué porcentaje del total va a acciones y CEDEARs. Omitirlo deja que el backend use el
   *  default del perfil (`PCT_RV_PERFIL`). */
  pct_rv?: number
  /** Rubro de la SEC (`sic_oficina`) para acotar la renta variable a una temática. */
  rubro_rv?: string | null
  /** Rendimiento mínimo exigido a la renta fija, en puntos porcentuales (`8` = 8%). Va al
   *  `min_rend` del backend, que el motor sí consume como piso al elegir candidatos. Omitirlo es
   *  no exigir piso.
   *
   *  Es el mismo número que `filtros.tirMin` de la grilla, y se mantienen sincronizados a
   *  propósito: que el armado automático proponga un papel que la grilla de al lado esconde por no
   *  llegar al piso sería la pantalla contradiciéndose sola. */
  min_rend?: number
}

/**
 * El default de renta variable por perfil, espejo de `PCT_RV_PERFIL` del backend.
 *
 * Sale del Excel de carteras sugeridas de la mesa: la conservadora no lleva renta variable, la
 * moderada un cuarto, y la audaz la mayor parte. Está acá duplicado —y no pedido al backend— para
 * poder precargar el input antes de que el asesor apriete el botón; el backend sigue siendo el que
 * decide si el campo llega vacío.
 */
export const PCT_RV_PERFIL: Record<ParametrosArmadoAsistido['perfil'], number> = {
  conservador: 0,
  moderado: 25,
  agresivo: 60,
}
