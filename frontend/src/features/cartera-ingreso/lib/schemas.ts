/**
 * El esquema de Zod que valida la posición cruda en el borde, antes de que entre al estado de la
 * aplicación o llegue a F-029.
 *
 * No valida el texto de origen —eso lo hace `parseNumero.ts`, que decide qué es y qué no es un
 * número— sino la forma del objeto ya construido: que el ticker no sea vacío, que `nominal` y
 * `monto` sean `number` finito o `null` (nunca `NaN`, que rompería cualquier cuenta corriente
 * silenciosamente) y que una fila inválida siempre traiga su motivo. Así un bug de cálculo que
 * produjera un `NaN` se corta acá en vez de propagarse como si fuera un dato real.
 */

import { z } from 'zod'

export const esquemaPosicionCruda = z
  .object({
    id: z.string().min(1),
    fila: z.number().int().positive(),
    // Vacío es un valor legítimo acá: es justamente la fila sin ticker que hay que marcar
    // inválida con su motivo, no un objeto malformado que haya que rechazar en el borde.
    tickerDeclarado: z.string(),
    nominal: z.number().finite().nullable(),
    monto: z.number().finite().nullable(),
    valida: z.boolean(),
    motivo: z.string().nullable(),
  })
  .refine((p) => p.valida || p.motivo !== null, {
    message: 'Una posición inválida tiene que declarar el motivo',
  })

export type PosicionCrudaValidada = z.infer<typeof esquemaPosicionCruda>
