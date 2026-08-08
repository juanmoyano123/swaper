/**
 * El contrato de `POST /api/v1/concentracion` — F-020.
 *
 * Vive en su propio archivo y no en `lib/schema.ts` por una razón de coordinación, no de diseño:
 * `schema.ts` lo comparten las features de la Tanda 9 y las tres se construyen en paralelo. Un
 * archivo por contrato evita que dos agentes editen el mismo a la vez, que es el único error de
 * coordinación que tuvo la tanda anterior.
 *
 * La forma exacta sale de `backend/app/concentracion/servicio.py` (`Concentracion.como_dict`,
 * `EstadoDeTope.como_dict`, `Tramo.como_dict`). Se valida entero, como todo lo que entra por
 * `apiFetch`: si el backend deja de mandar un campo, esto falla fuerte en vez de dibujar un panel
 * de riesgo a medias, que es la peor forma de mostrar un riesgo.
 *
 * Las alertas usan el mismo shape que las del calendario —`Alerta.como_dict()` sin `origen`— y se
 * redefinen acá en vez de importarse de `lib/schema.ts` por lo mismo de arriba.
 */

import { z } from 'zod'

export const esquemaAlertaConcentracion = z.object({
  codigo: z.string(),
  mensaje: z.string(),
  severidad: z.enum(['error', 'advertencia', 'info']),
  /** Siempre `null` en esta feature: la ficha manda que informe y no bloquee. */
  accion_requerida: z.string().nullable(),
  detalle: z.record(z.string(), z.unknown()),
})

/** Contra qué se mide un acumulado. Los tres topes del motor, sin componer ninguno (regla 7). */
export const esquemaTipoDeTope = z.enum(['soberano', 'emisor', 'sector'])

export const esquemaEstadoDeTope = z.object({
  tipo: esquemaTipoDeTope,
  /** `SOBERANO_AR`, el prefijo de tres letras del emisor, o el nombre del sector. */
  clave: z.string(),
  nombre: z.string(),
  /** Peso acumulado en puntos porcentuales, **sin normalizar a 100**. */
  peso: z.number(),
  tope: z.number(),
  excedido: z.boolean(),
  /** Cuánto sobra, en puntos porcentuales. Cero cuando no está excedido. */
  exceso: z.number(),
})

export const esquemaTramo = z.object({
  nombre: z.string(),
  peso: z.number(),
  /** `true` en el tramo que agrupa lo que no tiene el dato. Se muestra, nunca se reparte. */
  sin_dato: z.boolean(),
})

export const esquemaLimites = z.object({
  tope_rend_usd: z.number(),
  percentil_liquidez: z.number(),
  max_emisor: z.number(),
  max_soberano: z.number(),
  max_sector: z.number(),
  min_sectores: z.number(),
})

export const esquemaConcentracion = z.object({
  perfil: z.string(),
  limites: esquemaLimites,
  topes: z.array(esquemaEstadoDeTope),
  excedidos: z.number(),
  distribucion: z.object({
    sector: z.array(esquemaTramo),
    ley: z.array(esquemaTramo),
    naturaleza: z.array(esquemaTramo),
  }),
  sectores: z.object({
    /** Sectores informados, exentos incluidos: la exención es del tope, no de la existencia. */
    presentes: z.array(z.string()),
    cantidad: z.number(),
    minimo: z.number(),
    suficiente: z.boolean(),
    peso_sin_sector: z.number(),
  }),
  peso: z.object({
    /** Lo que suman todas las posiciones enviadas. */
    declarado: z.number(),
    /** Lo que suman las que están en el universo: sobre esto se miden los topes. */
    medido: z.number(),
  }),
  fuera_del_universo: z.array(z.string()),
  alertas: z.array(esquemaAlertaConcentracion),
})

export type AlertaConcentracion = z.infer<typeof esquemaAlertaConcentracion>
export type TipoDeTope = z.infer<typeof esquemaTipoDeTope>
export type EstadoDeTope = z.infer<typeof esquemaEstadoDeTope>
export type TramoConcentracion = z.infer<typeof esquemaTramo>
export type Concentracion = z.infer<typeof esquemaConcentracion>

/** Los tres perfiles del backend (`app/concentracion/perfiles.py`). */
export const PERFILES = ['conservador', 'moderado', 'agresivo'] as const
export type NombreDePerfil = (typeof PERFILES)[number]
