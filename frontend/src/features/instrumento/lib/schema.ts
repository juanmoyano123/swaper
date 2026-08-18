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
  /** Cuánto capital queda vivo después de este pago, cada 100 nominales, tal como lo declara la
   *  fuente. `null` cuando `resumen.coherente` es `false`: el residual declarado contradice la
   *  suma de amortizaciones ya pagadas, y se prefiere vacío antes que un dato contradictorio. */
  residual: z.number().nullable(),
})

export type PagoCronograma = z.infer<typeof esquemaPagoCronograma>

/**
 * Residual vigente, valor técnico, cupón corrido y paridad — calculados en vivo sobre el
 * cronograma de este ticker (17/08/2026). Nunca una etiqueta interpretativa ("caro"/"barato"):
 * la regla 11 pide mostrar el dato, no la lectura — el color por umbral que ya usa el monitor
 * (`lib/paridad.ts`) es hasta donde llega esto.
 */
export const esquemaResumenCronograma = z.object({
  residual_vigente: z.number().nullable(),
  valor_tecnico: z.number().nullable(),
  cupon_corrido: z.number().nullable(),
  /** Sólo cuando la moneda del flujo y la de cotización coinciden (mismo gate que F-051): sin
   *  eso, comparar el precio contra el valor técnico mezclaría monedas. */
  paridad: z.number().nullable(),
  /** `false` cuando el residual que declara la fuente contradice la suma de amortizaciones ya
   *  pagadas: los otros tres campos van `null` y `motivo_ausente` lo explica. */
  coherente: z.boolean(),
  motivo_ausente: z.string().nullable(),
})

export type ResumenCronograma = z.infer<typeof esquemaResumenCronograma>

export const esquemaCronograma = z.object({
  ticker: z.string(),
  pagos: z.array(esquemaPagoCronograma),
  resumen: esquemaResumenCronograma,
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

/**
 * Un documento filed ante la CNV — F-072. `url_publicview` abre la página oficial de la
 * presentación; el archivo real (PDF) se pide aparte, a demanda, por
 * `GET /instrumentos/{ticker}/prospecto/{uuid}/archivo` (no viaja acá: puede pesar varios MB).
 */
export const esquemaDocumentoCnv = z.object({
  fecha: z.string().nullable(),
  hora: z.string(),
  descripcion: z.string(),
  documento_id: z.string(),
  uuid: z.string(),
  url_publicview: z.string(),
})

export type DocumentoCnv = z.infer<typeof esquemaDocumentoCnv>

/** Un grupo del acordeón de la CNV, tal como la fuente lo declara (Prospectos, Suplementos...). */
export const esquemaGrupoDocumentos = z.object({
  grupo: z.string(),
  documentos: z.array(esquemaDocumentoCnv),
})

export type GrupoDocumentos = z.infer<typeof esquemaGrupoDocumentos>

/**
 * Los documentos de la ON ante la CNV. `aplica: false` cuando el ticker no es una ON o no está en
 * el universo de hoy — no se esconde el bloque, se declara por qué no corresponde. `cuit`/`emisor`
 * viajan cuando se pudieron resolver aunque `grupos` venga vacío (fuente pausada o sin confirmar):
 * `url_emisor_cnv` es la salida de emergencia que no depende del parser.
 */
export const esquemaProspecto = z.object({
  ticker: z.string(),
  aplica: z.boolean(),
  emisor: z.string().nullable(),
  cuit: z.string().nullable(),
  url_emisor_cnv: z.string().nullable(),
  grupos: z.array(esquemaGrupoDocumentos),
  motivo_ausente: z.string().nullable(),
  fuente: z.string(),
})

export type Prospecto = z.infer<typeof esquemaProspecto>
