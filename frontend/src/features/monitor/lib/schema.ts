/**
 * Los contratos que consume el monitor — F-038.
 *
 * `esquemaEspecie` es `EspecieUniverso.como_dict()` más los dos campos que sólo agrega la vista
 * viva (`dato_sano`, `hermanas`): la misma forma que ya usan las otras vistas de `/universo`, así
 * que no hay nada acá que el backend no esté mandando desde F-011/F-012. `esquemaSegmentos` es el
 * contrato nuevo de F-038, de dónde el monitor saca sus pestañas.
 */

import { z } from 'zod'

export const esquemaEspecie = z.object({
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
  /** Adimensional y ronda 1.0 (`cupones.py` del backend): 0.875 es un bono bajo la par. */
  paridad: z.number().nullable(),
  /** Cuánto capital queda vivo hoy, cada 100 nominales — cálculo propio desde el 17/08/2026
   *  (`componentes_valor_tecnico`, contractual). `null` sin cronograma, vencido, o cuando el
   *  residual que declara la fuente contradice la suma de amortizaciones ya pagadas. */
  residual: z.number().nullable(),
  /** Residual vigente + cupón corrido, cada 100 nominales — denominador de `paridad`. Mismas
   *  condiciones de `null` que `residual`. */
  valor_tecnico: z.number().nullable(),
  /** Rubro declarado por la fuente curada (`data/condiciones_emision.csv`). `null` = sin dato: no
   *  se infiere de ningún parecido con otra especie (regla 1). Agregado 14/08/2026 para el
   *  facetado de la barra de filtros — el mismo campo que ya usa el armador. */
  sector: z.string().nullable(),
  /** Texto literal de la calificadora (`'AA(arg)'`, `'AAA (FIX)'`), sin escala común entre las
   *  cuatro calificadoras del universo: nunca se ordena por riesgo, sólo se filtra por
   *  coincidencia exacta. `null` = sin dato. Agregado 14/08/2026, mismo criterio que `sector`. */
  calificacion: z.string().nullable(),
  /** `false` cuando la sanidad de F-010 la descartó. Sigue en la lista: no se propone, no se
   * esconde. */
  dato_sano: z.boolean(),
  /** Las otras especies de liquidación de la misma emisión (F-011). */
  hermanas: z.array(z.string()),
  /** Experimento data912 (rama `experimento/data912`): de dónde salió `precio`. `'data912'` |
   * `'data912-arrastre'` (precio de fecha desconocida, regla 11) | `'byma'`, compuesto con
   * `+calculo` según de dónde salga la métrica. `+iamc` ya no aparece en corridas nuevas: el
   * consumo de IAMC está pausado desde el 13/08/2026, pero sigue llegando en filas anteriores.
   * `null` en cualquier corrida anterior a la migración que lo expone. */
  fuente: z.string().nullable(),
})

export type Especie = z.infer<typeof esquemaEspecie>

/** Una pestaña de `/universo/segmentos`, con su conteo real del día. */
export const esquemaSegmentoInfo = z.object({
  clave: z.string(),
  nombre: z.string(),
  naturaleza: z.string(),
  naturaleza_nombre: z.string(),
  especies: z.number(),
})

export type SegmentoInfo = z.infer<typeof esquemaSegmentoInfo>

export const esquemaSegmentos = z.object({
  segmentos: z.array(esquemaSegmentoInfo),
  /** Cuántos instrumentos quedaron fuera por ser renta variable: no tienen TIR ni duración. */
  renta_variable: z.number(),
  /** Renta fija cuyo tipo de tasa no se reconoció: no entra en ninguna pestaña. */
  sin_segmento: z.number(),
})

export type Segmentos = z.infer<typeof esquemaSegmentos>
