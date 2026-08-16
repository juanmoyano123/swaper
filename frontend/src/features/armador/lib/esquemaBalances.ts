/**
 * El contrato de `POST /renta-variable/balances` — F-027.
 *
 * Espejo de `CalendarioBalances` (`backend/app/externos/sec_calendario.py`). Como todo dato de
 * `app/externos/`, se muestra con su fuente y su hora de captura, y se declara ausente en vez de
 * inventar un patrón cuando la SEC no tiene qué mostrar.
 */

import { z } from 'zod'

export const esquemaMesDeBalance = z.object({
  /** 1 = enero .. 12 = diciembre. Sólo vienen los meses con al menos una presentación. */
  mes: z.number().int().min(1).max(12),
  presentaciones: z.number().int().nonnegative(),
  formularios: z.array(z.string()),
})

export const esquemaVentanaCalendario = z.object({
  desde: z.string(),
  hasta: z.string(),
})

export const esquemaCalendarioBalances = z.object({
  papel: z.string(),
  fuente: z.string(),
  disponible: z.boolean(),
  motivo_ausente: z.string().nullable(),
  /** `true`: sólo se detecta patrón anual (emisor privado extranjero). Ver `nota_solo_anual`. */
  solo_anual: z.boolean(),
  nota_solo_anual: z.string().nullable(),
  cik: z.string().nullable(),
  /** El rango de fechas realmente cubierto por la ventana medida — nunca se muestra un patrón por
   *  fuera de lo que la fuente entregó. */
  ventana: esquemaVentanaCalendario.nullable(),
  meses: z.array(esquemaMesDeBalance),
  capturado_en: z.string(),
})

export const esquemaRespuestaBalances = z.object({
  calendarios: z.array(esquemaCalendarioBalances),
})

export type MesDeBalance = z.infer<typeof esquemaMesDeBalance>
export type CalendarioBalances = z.infer<typeof esquemaCalendarioBalances>
