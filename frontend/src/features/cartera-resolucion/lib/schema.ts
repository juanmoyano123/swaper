/**
 * El contrato de `POST /api/v1/posiciones/resolver` — F-029.
 *
 * Espeja `app/posiciones/resolucion.py`. Lo que más importa de esta forma es que **el ticker
 * declarado y el resuelto son dos campos y no uno**: la pantalla tiene que poder mostrar que lo
 * que se encontró es exactamente lo que se pidió, y una respuesta que pisara el declarado con el
 * resuelto haría invisible cualquier diferencia.
 */

import { z } from 'zod'

/** Por qué un ticker no quedó vinculado a una especie. Los cuatro son hechos leídos de la base. */
export const esquemaMotivo = z.enum([
  'no_esta_en_el_universo',
  'renta_variable',
  'sin_tipo_de_tasa',
  'es_fci',
])

/** La ficha mínima de un FCI matcheado por `codigo_cafci` exacto (F-046). Presente sólo cuando
 *  `motivo === 'es_fci'`; nunca se completa por analogía en ningún otro caso (regla 1). */
export const esquemaFondoFciResuelto = z.object({
  codigo_cafci: z.string(),
  fondo: z.string(),
  /** Por cada mil cuotapartes, tal como CAFCI lo publica. */
  vcp: z.number().nullable(),
  fecha_vcp: z.string().nullable(),
  moneda: z.string(),
})

export const esquemaPosicionResuelta = z.object({
  id: z.string(),
  fila: z.number(),
  ticker_declarado: z.string(),
  nominal: z.number().nullable(),
  monto: z.number().nullable(),
  resuelta: z.boolean(),
  ticker: z.string().nullable(),
  emision: z.string().nullable(),
  /** El sufijo O / D / C: la moneda de liquidación, no el plazo. */
  sufijo_liquidacion: z.string().nullable(),
  moneda_cotizacion: z.string().nullable(),
  /** `settlementType` de BYMA, `"1"` o `"2"`, sin traducir. `null` cuando la base no lo tiene. */
  plazo_liquidacion: z.string().nullable(),
  clase_activo: z.string().nullable(),
  segmento: z.string().nullable(),
  naturaleza: z.string().nullable(),
  dato_sano: z.boolean().nullable(),
  motivo: esquemaMotivo.nullable(),
  motivo_descripcion: z.string().nullable(),
  fondo_fci: esquemaFondoFciResuelto.nullable(),
})

export const esquemaCobertura = z.object({
  posiciones: z.number(),
  resueltas: z.number(),
  no_resueltas: z.number(),
  /** Las que entran a la base del porcentaje: las únicas que declaran monto. */
  posiciones_con_monto: z.number(),
  posiciones_sin_monto: z.number(),
  posiciones_sin_monto_no_resueltas: z.number(),
  monto_declarado: z.number(),
  monto_no_resuelto: z.number(),
  /**
   * En puntos porcentuales (18,2 es 18,2 %). `null` cuando no hay base sobre la cual calcularlo —
   * y `null` no es cero: se muestra `s/d`, nunca `0,0%`.
   */
  porcentaje_no_resuelto: z.number().nullable(),
})

export const esquemaAlerta = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.string(),
  accion_requerida: z.string().nullable(),
  detalle: z.unknown().optional(),
})

export const esquemaResolucion = z.object({
  posiciones: z.array(esquemaPosicionResuelta),
  cobertura: esquemaCobertura,
  alertas: z.array(esquemaAlerta),
})

export type FondoFciResuelto = z.infer<typeof esquemaFondoFciResuelto>
export type PosicionResuelta = z.infer<typeof esquemaPosicionResuelta>
export type Cobertura = z.infer<typeof esquemaCobertura>
export type AlertaResolucion = z.infer<typeof esquemaAlerta>
export type Resolucion = z.infer<typeof esquemaResolucion>
