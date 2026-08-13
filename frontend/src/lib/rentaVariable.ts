/**
 * Contrato, fetch y hook de la renta variable del monitor — F-052.
 *
 * Zona compartida a propósito: **F-026 (renta variable en el armador, tanda 9) importa de acá**.
 * El armador tiene prohibido importar de `features/monitor/**` (precedente F-018), así que nada de
 * este archivo puede mudarse adentro del monitor.
 */

import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { TIEMPOS } from '@/app/queryClient'

import { apiFetch } from './api/client'
import { claves } from './api/queryKeys'
import { esquemaPagina } from './api/schemas'

export const esquemaEspecieRentaVariable = z.object({
  ticker: z.string(),
  clase_activo: z.string(),
  precio: z.number().nullable(),
  moneda_cotizacion: z.string().nullable(),
  cierre_anterior: z.number().nullable(),
  /** Fracción, no puntos: 0.031 es +3,1%. Multiplicar por 100 recién al formatear, nunca antes. */
  variacion: z.number().nullable(),
  volumen: z.number().nullable(),
  volumen_usd: z.number().nullable(),
  px_bid: z.number().nullable(),
  px_ask: z.number().nullable(),
  operaciones: z.number().nullable(),
  // Sin `rendimiento`: si el backend algún día lo mandara, no viaja a la tabla. Una acción no
  // tiene TIR (regla 2) y este contrato no le hace lugar.
  /** Experimento data912: de dónde salió `precio`. Ver `features/monitor/lib/schema.ts`. */
  fuente: z.string().nullable(),

  // Qué papel es esta especie (13/08/2026). `AAPL`, `AAPLC` y `AAPLD` son el mismo CEDEAR de Apple
  // en pesos, cable y MEP: comparten `emision`. El backend lo agrupa y lo contrasta contra el tipo
  // de cambio del universo antes de afirmarlo — ver `app/renta_variable/agrupamiento.py`.
  /** El ticker del papel. Para una especie sin variantes es su propio ticker. */
  emision: z.string().nullable(),
  /** `'C'` cable, `'D'` MEP, `null` la especie en pesos o sin variantes. */
  sufijo_liquidacion: z.string().nullable(),
  /** Las otras especies del mismo papel. */
  hermanas: z.array(z.string()).default([]),
  /** La fuente no explica qué es esta especie — hoy, las que terminan en `B`. Se muestra aparte,
   *  declarada, en vez de esconderla o de inventarle una categoría. */
  no_identificado: z.boolean().default(false),

  // Perfil de empresa (Etapa 4 del rediseño del armador): `null` hasta que el job de
  // enriquecimiento pase por este ticker (`app/renta_variable/enriquecimiento.py`, backend). De
  // Yahoo Finance, tal como la fuente los declara — nunca se traducen (regla 11).
  nombre_corto: z.string().nullable(),
  nombre_largo: z.string().nullable(),
  sector: z.string().nullable(),
  industria: z.string().nullable(),
  pais: z.string().nullable(),
  perfil_fuente: z.string().nullable(),
  perfil_capturado_en: z.string().nullable(),
})

export type EspecieRentaVariable = z.infer<typeof esquemaEspecieRentaVariable>

const esquemaPaginaRentaVariable = esquemaPagina(esquemaEspecieRentaVariable)

const LIMITE_POR_PAGINA = 200

/** Igual tope que `useUniversoSegmento`: un resultado cortado en silencio no es una opción. */
const TOPE_PAGINAS = 30

async function traerClaseEntera(clase: string): Promise<EspecieRentaVariable[]> {
  const especies: EspecieRentaVariable[] = []
  let cursor: string | null = null

  for (let pagina = 0; pagina < TOPE_PAGINAS; pagina++) {
    const busqueda = new URLSearchParams({ limit: String(LIMITE_POR_PAGINA), clase })
    if (cursor) busqueda.set('cursor', cursor)

    const respuesta = await apiFetch(
      `/api/v1/renta-variable/especies?${busqueda.toString()}`,
      esquemaPaginaRentaVariable,
    )
    especies.push(...respuesta.items)
    cursor = respuesta.next_cursor
    if (cursor === null) return especies
  }

  throw new Error(
    `La clase "${clase}" no terminó de traerse en ${TOPE_PAGINAS} páginas ` +
      `(${especies.length} especies leídas hasta acá): se corta la carga acá para no mostrar un ` +
      'listado truncado sin decirlo.',
  )
}

export function useRentaVariable(clase: string) {
  return useQuery({
    queryKey: [...claves.mercado.todas, 'renta-variable', clase],
    queryFn: () => traerClaseEntera(clase),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
