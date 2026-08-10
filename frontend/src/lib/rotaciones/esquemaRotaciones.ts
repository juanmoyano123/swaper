/**
 * El contrato de `POST /api/v1/rotaciones` — F-032, consumido acá por F-033.
 *
 * La forma exacta sale de `backend/app/rotaciones/motor.py` (`Candidata.como_dict()`,
 * `_especie_como_dict()`) y `backend/app/rotaciones/servicio.py` (`ResultadoRotaciones.como_dict()`),
 * leídos directamente en vez de asumidos. Mismo criterio que `esquemaConcentracion.ts`: se valida
 * entero lo que se usa, todo lo demás lo tolera el modo strip por defecto de Zod.
 *
 * **Modo strip a propósito.** F-035 (tanda 13, en paralelo) le agrega a esta misma respuesta un
 * bloque `"costo"` en cada candidata — no se declara acá, así que el parseo no falla exista o no
 * ese commit todavía. Tampoco se declara `cupon` (puede traer o no un campo `fecha` por el mismo
 * motivo, y F-033 no lo necesita): cualquier clave no declarada, en cualquier nivel, se descarta
 * en silencio en vez de romper el contrato.
 */

import { z } from 'zod'

// Mismo shape que `esquemaAlertaConcentracion` de `esquemaConcentracion.ts`: `Alerta.como_dict()`
// del backend (`app/ingesta/alertas.py`) no tiene `origen`, y se redefine acá por la misma razón
// que allá (evitar un import cruzado entre dos contratos que documentan servicios distintos).
export const esquemaAlertaRotacion = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.enum(['error', 'advertencia', 'info']),
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

/** `_especie_como_dict()`: sólo `ticker` y `emisor` nunca son `null`. */
export const esquemaEspecieRotacion = z.object({
  ticker: z.string(),
  emisor: z.string(),
  rendimiento: z.number().nullable(),
  duracion: z.number().nullable(),
  moneda_cupon: z.string().nullable(),
  ley: z.string().nullable(),
  calificacion: z.string().nullable(),
  lamina: z.number().nullable(),
  frecuencia_cupon: z.string().nullable(),
  volumen_usd: z.number().nullable(),
})

export const esquemaCandidata = z.object({
  tipo: z.enum(['mejora_rendimiento', 'mejora_perfil']),
  segmento: z.string(),
  origen: esquemaEspecieRotacion,
  destino: esquemaEspecieRotacion,
  delta: z.object({
    rendimiento_pp: z.number(),
    duracion: z.number().nullable(),
  }),
  flags: z.object({
    mismo_emisor: z.boolean(),
    pasa_a_cable: z.boolean(),
    mejora_ley: z.boolean(),
    empeora_ley: z.boolean(),
    mejora_volumen: z.boolean(),
    posible_distress: z.boolean(),
  }),
  premio_ley: z
    .object({
      bps: z.number().nullable(),
      vs_mediana_bps: z.number().nullable(),
    })
    .nullable(),
  riesgo_nota: z.string(),
})

export const esquemaRotaciones = z.object({
  perfil: z.string(),
  candidatas: z.array(esquemaCandidata),
  origenes_evaluados: z.array(z.string()),
  fuera_del_universo: z.array(z.string()),
  sin_rendimiento: z.array(z.string()),
  alertas: z.array(esquemaAlertaRotacion),
})

export type AlertaRotacion = z.infer<typeof esquemaAlertaRotacion>
export type EspecieRotacion = z.infer<typeof esquemaEspecieRotacion>
export type Candidata = z.infer<typeof esquemaCandidata>
export type ResultadoRotaciones = z.infer<typeof esquemaRotaciones>
