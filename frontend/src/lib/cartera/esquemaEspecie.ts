/**
 * El contrato de una especie de `/api/v1/universo/emisiones/especies` — F-015/F-018, y el tipo de
 * cambio implícito de `/api/v1/universo/tipo-de-cambio` — F-012.
 *
 * Movido acá en la Tanda 11 desde `features/armador/lib/schema.ts`: es el mismo endpoint que ya
 * usaba el armador y el que necesita el diagnóstico de cartera (F-030) para cruzar sus posiciones
 * resueltas contra rendimiento, duración, precio y moneda. Un solo contrato leído por las dos
 * pantallas, en vez de dos copias que puedan desalinearse (riesgo R12 de `plan.md:2774`).
 *
 * El armador re-exporta este archivo desde `features/armador/lib/schema.ts` para no tener que
 * editar sus ~20 importadores existentes.
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
  paridad: z.number().nullable(),
  /** Lámina mínima de la emisión, de `condiciones_emision` vía la base común de la tanda 8b.
   *  `null` = no informada: no se redondea y se declara (F-024, regla 1 del proyecto). */
  lamina: z.number().nullable(),
  /** Sector del emisor, del dato curado de F-009 vía la base común de la tanda 8b. `null` = no
   *  informado y agrupa aparte: no se le asigna uno por parecido con otro emisor (F-017). */
  sector: z.string().nullable(),
  /** Calificación crediticia, del dato curado de F-009 vía la base común de la tanda 12. Texto
   *  libre tal cual la declara la fuente (`'AA(arg)'`, `'AAA (FIX)'`): no hay escala canónica
   *  entre calificadoras, así que nunca se ordena ni se usa como filtro (F-031, eje de crédito).
   *  359 de 823 tickers curados (39 %); el faltante se declara donde se muestre. */
  calificacion: z.string().nullable(),
  dato_sano: z.boolean(),
  hermanas: z.array(z.string()),
})

export type Especie = z.infer<typeof esquemaEspecie>

/** El tramo que se necesita de `GET /api/v1/universo/tipo-de-cambio` — sólo `valor` y
 *  `disponible`. El backend manda más campos (dispersión, contraste, muestras de descarte); no
 *  hace falta tipar los que nadie usa, mismo criterio que `estado-dato/lib/schema.ts`. */
export const esquemaTipoDeCambio = z.object({
  tipo_de_cambio: z.object({
    valor: z.number().nullable(),
    disponible: z.boolean(),
  }),
})

export type RespuestaTipoDeCambio = z.infer<typeof esquemaTipoDeCambio>
