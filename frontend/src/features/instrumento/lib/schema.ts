/**
 * Los contratos que consume la ficha de instrumento — F-039.
 *
 * Tres esquemas para tres endpoints independientes, que es a propósito lo mismo que hacen los tres
 * hooks: una falla en el cronograma no puede tumbar la ficha de precios.
 *
 * `esquemaEspecieFicha` redefine localmente el shape de `EspecieUniverso` — los mismos 18 campos
 * que `features/monitor/lib/schema.ts::esquemaEspecie` — porque esa carpeta está prohibida para
 * esta feature (ni siquiera se puede importar). Es la misma forma que trae `GET /instrumentos/{t}`
 * para la especie pedida y para cada hermana, sin el campo `hermanas` que sólo agrega la vista viva
 * del monitor.
 */

import { z } from 'zod'

export const esquemaEspecieFicha = z.object({
  ticker: z.string(),
  emision: z.string(),
  sufijo_liquidacion: z.string().nullable(),
  clase_activo: z.string(),
  segmento: z.string(),
  naturaleza: z.string(),
  naturaleza_nombre: z.string(),
  /** Fracción, no puntos: 0.13 es 13%. Multiplicar por 100 recién al formatear, nunca antes. */
  rendimiento: z.number().nullable(),
  duracion: z.number().nullable(),
  vencimiento: z.string().nullable(),
  ley: z.string().nullable(),
  moneda_cupon: z.string().nullable(),
  emisor: z.string().nullable(),
  precio: z.number().nullable(),
  moneda_cotizacion: z.string().nullable(),
  volumen: z.number().nullable(),
  volumen_usd: z.number().nullable(),
  /** Adimensional y ronda 1.0: 0.875 es un bono bajo la par. */
  paridad: z.number().nullable(),
  /** `false` cuando la sanidad de F-010 la descartó. Sigue en la ficha: no se propone, no se
   * esconde. */
  dato_sano: z.boolean(),
  /** Experimento data912: de dónde salió `precio`. Ver `features/monitor/lib/schema.ts`. */
  fuente: z.string().nullable(),
})

export type EspecieFicha = z.infer<typeof esquemaEspecieFicha>

export const esquemaFicha = z.object({
  ticker: z.string(),
  especie: esquemaEspecieFicha,
  /** Las otras especies de liquidación de la misma emisión (F-011). 0, 1 o 2 elementos. */
  hermanas: z.array(esquemaEspecieFicha),
})

export type Ficha = z.infer<typeof esquemaFicha>

/**
 * El triplete `campo/campo_origen/campo_fecha` de cada uno de los seis campos curados, tal como lo
 * devuelve `GET /condiciones` y ahora también `GET /instrumentos/{ticker}/condiciones`. `lamina` es
 * el único numérico de los seis (`CAMPOS_NUMERICOS` del backend); el resto son texto.
 */
export const esquemaCondicionesDetalle = z.object({
  ticker: z.string(),
  ley: z.string().nullable(),
  ley_origen: z.string().nullable(),
  ley_fecha: z.string().nullable(),
  moneda_pago: z.string().nullable(),
  moneda_pago_origen: z.string().nullable(),
  moneda_pago_fecha: z.string().nullable(),
  lamina: z.number().nullable(),
  lamina_origen: z.string().nullable(),
  lamina_fecha: z.string().nullable(),
  calificacion: z.string().nullable(),
  calificacion_origen: z.string().nullable(),
  calificacion_fecha: z.string().nullable(),
  sector: z.string().nullable(),
  sector_origen: z.string().nullable(),
  sector_fecha: z.string().nullable(),
  underlying: z.string().nullable(),
  underlying_origen: z.string().nullable(),
  underlying_fecha: z.string().nullable(),
})

export type CondicionesDetalle = z.infer<typeof esquemaCondicionesDetalle>

export const esquemaCondiciones = z.object({
  ticker: z.string(),
  /** `null` cuando el ticker no tiene fila curada (GWT-2): un estado normal, no un error. */
  condiciones: esquemaCondicionesDetalle.nullable(),
})

export type Condiciones = z.infer<typeof esquemaCondiciones>

/**
 * Un pago del cronograma, por 100 de valor nominal y en la moneda de emisión — nunca convertido a
 * fracción del invertido, eso lo hacen los cálculos de cartera (F-016/F-021), no esta ficha.
 */
export const esquemaPagoCronograma = z.object({
  fecha: z.string(),
  interes: z.number(),
  amortizacion: z.number(),
  /** `null` cuando ninguna fuente declara la moneda de emisión: no se infiere del ticker. */
  moneda: z.string().nullable(),
})

export type PagoCronograma = z.infer<typeof esquemaPagoCronograma>

export const esquemaCronograma = z.object({
  ticker: z.string(),
  pagos: z.array(esquemaPagoCronograma),
})

export type Cronograma = z.infer<typeof esquemaCronograma>

/**
 * Un escenario de la tabla de sensibilidad — F-040: repricing completo del cashflow contractual a
 * la TIR de ese escenario, nunca la aproximación lineal por duración.
 */
export const esquemaEscenarioSensibilidad = z.object({
  delta_bps: z.number(),
  /** Fracción en la unidad del instrumento, igual que `rendimiento`: multiplicar por 100 recién al formatear. */
  tir_escenario: z.number(),
  /** Fracción: 0.18 es +18 % de precio. Repricing completo, nunca duración por delta. */
  retorno: z.number(),
})

export type EscenarioSensibilidad = z.infer<typeof esquemaEscenarioSensibilidad>

export const esquemaSensibilidad = z.object({
  ticker: z.string(),
  tir_actual: z.number().nullable(),
  naturaleza: z.string().nullable(),
  naturaleza_nombre: z.string().nullable(),
  calculable: z.boolean(),
  /** El porqué cuando no se puede calcular. Se muestra tal cual: la declaración es el dato. */
  motivo: z.string().nullable(),
  escenarios: z.array(esquemaEscenarioSensibilidad),
  omitidos_bps: z.array(z.number()),
})

export type Sensibilidad = z.infer<typeof esquemaSensibilidad>
