/**
 * Los esquemas del contrato que expone FastAPI en /api/v1.
 *
 * Ojo: esto tipa lo que devuelve el backend —modelos Pydantic, páginas, vistas calculadas—, que no
 * es lo mismo que las tablas de la base. Los tipos de tablas viven en `types/database.types.ts` y
 * se usan solo con el cliente de Supabase (desde F-014). Acoplar los dos contratos obligaría a que
 * cada endpoint devolviera filas crudas.
 */

import { z } from 'zod'

/** Contrato de error uniforme de `backend/app/core/errors.py`. */
export const esquemaError = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().nullable().optional(),
    request_id: z.string().nullable().optional(),
  }),
})

/** Respuesta de GET /api/v1/health. */
export const esquemaSalud = z.object({
  status: z.string(),
  database: z.string(),
  last_market_snapshot_at: z.string().nullable(),
  warnings: z.array(z.string()),
})

export type Salud = z.infer<typeof esquemaSalud>

/**
 * Espejo de `Page[T]` de `backend/app/core/pagination.py`.
 *
 * `next_cursor` es opaco: llega como string y se devuelve tal cual. El cliente no lo decodifica
 * nunca — que su contenido sea base64 de un JSON es asunto del backend y puede cambiar.
 */
export function esquemaPagina<T extends z.ZodTypeAny>(item: T) {
  return z.object({
    items: z.array(item),
    next_cursor: z.string().nullable(),
  })
}

export type Pagina<T> = { items: T[]; next_cursor: string | null }
