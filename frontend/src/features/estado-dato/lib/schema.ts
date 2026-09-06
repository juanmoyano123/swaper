/**
 * El contrato de GET /api/v1/estado-del-dato — F-013.
 *
 * Se valida entero, como todo lo que entra por `apiFetch`: si el backend deja de mandar un campo,
 * esto falla fuerte en vez de dibujar media barra. Una barra a medias es peor que ninguna — su
 * trabajo es declarar qué falta, y no puede hacerlo si ella misma está incompleta sin decirlo.
 */

import { z } from 'zod'

/** Cuánto duele. El orden de urgencia lo fija `severidad.ts`, no el orden alfabético de estos valores. */
export const esquemaSeveridad = z.enum(['error', 'advertencia', 'info'])

/**
 * Una alerta del backend, con el mismo contrato de `backend/app/ingesta/alertas.py`.
 *
 * `mensaje` y `accion_requerida` son para la persona; `codigo` es para el código que agrupa y
 * cuenta. El mensaje **no se reescribe en la interfaz**: ya está redactado para que se sepa qué
 * hacer, y una segunda redacción haría que el mismo hecho se cuente de dos formas distintas según
 * por dónde se lo mire.
 */
export const esquemaAlerta = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: esquemaSeveridad,
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
  /** `ingesta` si falló al traer el dato; `estado` si falta en el dato ya traído. */
  origen: z.enum(['ingesta', 'estado']),
})

/** Un instrumento que no se propone, con el número exacto que lo disparó (GWT-3). */
export const esquemaDescarte = z.object({
  ticker: z.string(),
  motivo: z.string(),
  rendimiento: z.number().nullable(),
  segmento: z.string(),
  naturaleza_nombre: z.string(),
  umbral: z.number(),
  ticker_referencia: z.string().nullable(),
  rendimiento_referencia: z.number().nullable(),
})

/** Cuánto del universo trae un campo crítico, y qué se rompe cuando no lo trae. */
export const esquemaCobertura = z.object({
  campo: z.string(),
  rotulo: z.string(),
  por_que: z.string(),
  presentes: z.number(),
  total: z.number(),
  faltantes: z.number(),
  porcentaje: z.number(),
})

export const esquemaEstadoDelDato = z.object({
  consultado_en: z.string(),

  dato: z.object({
    /** Cuándo se capturó el precio más nuevo. **No** es cuándo se armó esta respuesta. */
    capturado_en: z.string().nullable(),
    /** `capturado_en` menos la demora: hasta qué momento del mercado refleja lo que se ve. */
    dato_valido_hasta: z.string().nullable(),
    antiguedad_minutos: z.number().nullable(),
    demora: z.object({
      minutos: z.number(),
      fuente: z.string(),
      por_que: z.string(),
    }),
  }),

  corrida: z
    .object({
      id: z.number(),
      tipo: z.string(),
      estado: z.string(),
      iniciado_en: z.string(),
      finalizado_en: z.string(),
      duracion_ms: z.number(),
      filas_por_fuente: z.record(z.string(), z.number()),
    })
    .nullable(),

  fuentes: z.object({
    credenciales_vencidas: z.array(esquemaAlerta.partial({ origen: true })),
    caidas: z.array(esquemaAlerta.partial({ origen: true })),
    hay_credencial_vencida: z.boolean(),
    hay_fuente_caida: z.boolean(),
    requiere_intervencion: z.boolean(),
  }),

  universo: z.object({
    leidos: z.number(),
    renta_variable: z.number(),
    /** Renta fija cuyo tipo de tasa no se reconoce: la sanidad ni la mira. */
    sin_segmento: z.number(),
    evaluados: z.number(),
    con_rendimiento: z.number(),
    descartados: z.number(),
    operables: z.number(),
    emisiones: z.number(),
  }),

  descartes: z.object({
    total: z.number(),
    items: z.array(esquemaDescarte),
    truncado: z.boolean(),
  }),

  cobertura: z.array(esquemaCobertura),

  tipo_de_cambio: z.object({
    valor: z.number().nullable(),
    disponible: z.boolean(),
    pares: z.number(),
  }),

  calendario: z.object({
    emisiones: z.number(),
    con_calendario: z.number(),
    sin_paridad: z.number(),
    sin_cronograma: z.number(),
    vencidos: z.number(),
  }),

  alertas: z.array(esquemaAlerta),

  resumen: z.object({
    alertas: z.number(),
    por_severidad: z.record(esquemaSeveridad, z.number()),
    peor_severidad: esquemaSeveridad.nullable(),
    requiere_intervencion: z.boolean(),
  }),

  costo: z.object({
    desde_cache: z.boolean(),
    analisis_calculado_en: z.string(),
    analisis_duracion_ms: z.number(),
  }),
})

/**
 * El contrato de `POST /api/v1/jobs/corridas/matinal` — el botón de refresh manual.
 *
 * `alertas` usa `esquemaAlerta` sin `origen`: ese campo lo agrega `GET /estado-del-dato` al fusionar
 * fuentes, no viene en el dict crudo de `Alerta` que devuelve `registrar_corrida` en el backend.
 */
export const esquemaCorridaDisparada = z.object({
  id: z.number(),
  tipo: z.string(),
  estado: z.string(),
  iniciado_en: z.string(),
  finalizado_en: z.string(),
  duracion_ms: z.number(),
  filas_por_fuente: z.record(z.string(), z.number()),
  alertas: z.array(esquemaAlerta.partial({ origen: true })),
})

/**
 * La corrida no se disparó porque ya había una en curso (el cron, u otro click de este mismo
 * botón). 200 y no un error — `backend/app/api/v1/jobs.py` explica por qué en `_omitida()`.
 */
export const esquemaCorridaOmitida = z.object({
  omitida: z.literal(true),
  motivo: z.string(),
})

export const esquemaResultadoCorrida = z.union([esquemaCorridaDisparada, esquemaCorridaOmitida])

export type Severidad = z.infer<typeof esquemaSeveridad>
export type Alerta = z.infer<typeof esquemaAlerta>
export type Descarte = z.infer<typeof esquemaDescarte>
export type CoberturaCampo = z.infer<typeof esquemaCobertura>
export type EstadoDelDato = z.infer<typeof esquemaEstadoDelDato>
export type CorridaDisparada = z.infer<typeof esquemaCorridaDisparada>
export type CorridaOmitida = z.infer<typeof esquemaCorridaOmitida>
export type ResultadoCorrida = z.infer<typeof esquemaResultadoCorrida>

/** Type guard para distinguir las dos formas de `ResultadoCorrida` en la vista. */
export function esCorridaOmitida(resultado: ResultadoCorrida): resultado is CorridaOmitida {
  return 'omitida' in resultado
}
