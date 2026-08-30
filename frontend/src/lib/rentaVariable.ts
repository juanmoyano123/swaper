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

  // Clasificación de la SEC y de la tabla de CEDEARs de BYMA (13/08/2026). Todas pueden faltar: la
  // SEC cubre el 74 % de los CEDEARs y el 9 % de las acciones argentinas, y lo que no está se
  // declara en pantalla — nunca se completa por analogía con otra empresa.
  /** Código de actividad de la SEC, sin normalizar: es la llave de auditoría. */
  sic_codigo: z.string().nullable().default(null),
  /** A qué se dedica, en las palabras de la fuente: `Electronic Computers`. */
  sic_titulo: z.string().nullable().default(null),
  /** El rubro, según cómo agrupa la propia SEC: `Office of Energy & Transportation`. */
  sic_oficina: z.string().nullable().default(null),
  /** En qué eslabón de la cadena productiva está: `Extracción`, `Manufactura`, `Servicios`…
   *  Sale de la división del SIC Manual, no de una interpretación nuestra. */
  division_cadena: z.string().nullable().default(null),

  // Sector y rubro específico — F-079 (29/08/2026). Traducción curada del SIC en dos niveles: ver
  // `app/renta_variable/especies.py` para el docstring completo.
  /** El major group SIC de dos dígitos (`"73"`), aritmética pura sobre `sic_codigo`. Siempre
   *  presente si hay `sic_codigo`, sin depender de ningún curado. */
  sector_codigo: z.string().nullable().default(null),
  /** La etiqueta ES de `sector_codigo` (`data/sic_sectores.csv`). `null` sin curado cargado o sin
   *  fila para ese major group — el fallback declarado es mostrar `sector_codigo`. */
  sector: z.string().nullable().default(null),
  /** La etiqueta ES de `sic_codigo` (`data/sic_rubros.csv`). `null` sin curado cargado o sin fila
   *  para ese código — el fallback declarado es `sic_titulo`, tal como lo publica la SEC. */
  rubro_especifico: z.string().nullable().default(null),
  /** Qué idea arma el portafolio si es un fondo. `null` = no es un fondo. */
  estrategia_etf: z.string().nullable().default(null),
  /** Cuántos CEDEARs equivalen a una acción del subyacente, como razón (`20:1`). */
  ratio_conversion: z.string().nullable().default(null),
  /** En qué mercado cotiza el subyacente: `NASDAQ`, `NYSE`, `B3`. */
  mercado_origen: z.string().nullable().default(null),
  /** La geografía que declara el nombre oficial del fondo, tal como aparece en el nombre: `China`,
   *  `EAFE`, `Latin America`. `null` = no es un fondo, o su nombre no nombra ninguna geografía.
   *  **No se traduce ni se unifica con `region`**: aquélla sale del país curado por la subregión
   *  M49 de la ONU y ésta del nombre del fondo. Son dos vocabularios y se muestran como valores
   *  distintos — mapear `Brazil` a "América Latina y el Caribe" sería traducir (regla 11). */
  region_etf: z.string().nullable(),

  // Geografía curada de ETFs — F-079, D3 (29/08/2026). Viene de `public.etf_geografia`, por papel,
  // igual que el país curado de más abajo. `null` en las seis columnas es lo normal para todo lo
  // que no es un ETF geográfico curado — a diferencia de sector/rubro, acá no hay fallback textual.
  /** Qué índice sigue el fondo, en español y corto. */
  etf_indice: z.string().nullable().default(null),
  /** Qué alcance declara el emisor de ese índice — su propia definición, no nuestra lectura de qué
   *  países lo componen hoy (esa composición no se cura: envejece con cada rebalanceo). */
  etf_alcance: z.string().nullable().default(null),
  /** ISO 3166-1 alfa-2, sólo para el puñado de fondos mono-país. `null` es el caso normal para un
   *  fondo multi-país. */
  etf_pais: z.string().nullable().default(null),
  /** La subregión M49 de la ONU de `etf_pais`, derivada al leer. `null` sin `etf_pais`. */
  etf_region: z.string().nullable().default(null),
  /** Qué declara la geografía del ETF y dónde se investigó. Nunca se muestra sin esto (regla 11). */
  etf_geo_fuente: z.string().nullable().default(null),
  /** Cuándo se verificó contra esa fuente, en ISO. Es la fecha del dato, no la de la carga. */
  etf_geo_verificado: z.string().nullable().default(null),

  // País de la empresa detrás del CEDEAR — F-078. Curado a mano papel por papel, con la fuente que
  // lo declara y la fecha en que se verificó, y validado antes de cargarse: no hay fuente
  // automática que diga a qué economía queda expuesta la plata (el domicilio legal de la SEC no lo
  // dice). `null` mientras el curado no llegue a ese papel, y se muestra como faltante declarado.
  /** ISO 3166-1 alfa-2, tal como el curado lo declara. */
  pais: z.string().nullable().default(null),
  /** La subregión geográfica de la ONU (estándar M49) que corresponde a `pais`, en español y tal
   *  como la ONU la publica: `América Latina y el Caribe`, `Asia occidental`. La deriva el backend
   *  al leer; no es una columna. */
  region: z.string().nullable().default(null),
  /** Qué declara el país y dónde se leyó. El país nunca se muestra sin esto (regla 11). */
  pais_fuente: z.string().nullable().default(null),
  /** Cuándo se verificó contra esa fuente, en ISO. Es la fecha del dato, no la de la carga. */
  pais_verificado: z.string().nullable().default(null),

  // Perfil de empresa: `null` hasta que el job de clasificación pase por este ticker
  // (`app/renta_variable/clasificacion.py`, backend). Tal como la fuente lo declara — nunca se
  // traduce (regla 11).
  nombre_largo: z.string().nullable(),
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
