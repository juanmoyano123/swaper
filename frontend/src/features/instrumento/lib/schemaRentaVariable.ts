/**
 * El contrato de `GET /renta-variable/{ticker}/ficha` — F-053.
 *
 * Archivo aparte de `schema.ts` a propósito: son dos fichas distintas, no dos variantes de la
 * misma. La de renta fija gira alrededor de la TIR, el cronograma y la paridad; una acción no tiene
 * ninguna de las tres, y meter las dos en un esquema con la mitad de los campos opcionales invitaría
 * exactamente a lo que la regla 2 prohíbe — poner algo en el lugar de una magnitud que no existe.
 *
 * **No hay campo de recomendación, ni de precio objetivo, ni de consenso de analistas.** Yahoo los
 * publica y el backend no los trae (regla 6); acá tampoco tienen lugar donde entrar. Si el backend
 * algún día los mandara, no viajarían a la pantalla.
 */

import { z } from 'zod'

/** El bloque nuestro: lo que BYMA publica, idéntico a lo que muestra la tabla del monitor. */
export const esquemaBloquePropio = z.object({
  fuente: z.string(),
  ticker: z.string(),
  clase_activo: z.string(),
  precio: z.number().nullable(),
  moneda_cotizacion: z.string().nullable(),
  cierre_anterior: z.number().nullable(),
  /** Fracción, no puntos: 0.031 es +3,1 %. Multiplicar por 100 recién al formatear. */
  variacion: z.number().nullable(),
  volumen: z.number().nullable(),
  volumen_usd: z.number().nullable(),
  px_bid: z.number().nullable(),
  px_ask: z.number().nullable(),
  operaciones: z.number().nullable(),
})

export type BloquePropio = z.infer<typeof esquemaBloquePropio>

export const esquemaPuntoHistorico = z.object({
  fecha: z.string(),
  cierre: z.number(),
})

export type PuntoHistorico = z.infer<typeof esquemaPuntoHistorico>

/** El nivel 1 de Yahoo: el papel visto por la fuente externa, con la hora en que se lo capturó. */
export const esquemaCotizacionExterna = z.object({
  simbolo: z.string(),
  bolsa: z.string(),
  bolsa_nombre: z.string().nullable(),
  moneda: z.string().nullable(),
  nombre_largo: z.string().nullable(),
  nombre_corto: z.string().nullable(),
  tipo_instrumento: z.string().nullable(),
  precio: z.number().nullable(),
  cierre_previo: z.number().nullable(),
  maximo_dia: z.number().nullable(),
  minimo_dia: z.number().nullable(),
  maximo_52_semanas: z.number().nullable(),
  minimo_52_semanas: z.number().nullable(),
  volumen: z.number().nullable(),
  historico: z.array(esquemaPuntoHistorico),
  capturado_en: z.string(),
})

export type CotizacionExterna = z.infer<typeof esquemaCotizacionExterna>

/** El nivel 2: quién es la empresa, en el vocabulario de Yahoo. Se muestra sin traducir (regla 11). */
export const esquemaPerfilExterno = z.object({
  pais: z.string().nullable(),
  sector: z.string().nullable(),
  industria: z.string().nullable(),
  sitio: z.string().nullable(),
  empleados: z.number().nullable(),
  capturado_en: z.string(),
})

export type PerfilExterno = z.infer<typeof esquemaPerfilExterno>

/**
 * `disponible` es del bloque entero; `perfil_motivo` es el matiz del segundo nivel — hay cotización
 * pero no perfil, que es lo que pasa cuando el mecanismo de autenticación de Yahoo se rompe.
 */
export const esquemaBloqueExterno = z.object({
  fuente: z.string(),
  simbolo_consultado: z.string(),
  disponible: z.boolean(),
  motivo: z.string().nullable(),
  cotizacion: esquemaCotizacionExterna.nullable(),
  perfil: esquemaPerfilExterno.nullable(),
  perfil_motivo: z.string().nullable(),
})

export type BloqueExterno = z.infer<typeof esquemaBloqueExterno>

export const esquemaFichaRentaVariable = z.object({
  ticker: z.string(),
  propio: esquemaBloquePropio,
  externo: esquemaBloqueExterno,
})

export type FichaRentaVariable = z.infer<typeof esquemaFichaRentaVariable>
