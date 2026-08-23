/**
 * Contrato, fetch y hooks de los fondos comunes de inversión — F-057.
 *
 * En `lib/`, no en `features/monitor/`: F-046 (FCI valuables en cartera) importa de acá desde el
 * armador, que tiene prohibido importar de `features/monitor/**` (precedente F-018, seguido por
 * `lib/rentaVariable.ts`).
 */

import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'

import { TIEMPOS } from '@/app/queryClient'

import { apiFetch } from './api/client'
import { claves } from './api/queryKeys'
import { esquemaPagina } from './api/schemas'

export const esquemaFondoFci = z.object({
  codigo_cafci: z.string(),
  fondo: z.string(),
  codigo_cnv: z.string().nullable(),
  seccion: z.string(),
  tipo_renta: z.string(),
  /** Naturaleza fija: `variacion_cuotaparte`. Un FCI nunca comparte eje con una TIR (regla 2). */
  naturaleza: z.string(),
  naturaleza_nombre: z.string(),
  moneda: z.string(),
  region: z.string().nullable(),
  horizonte: z.string().nullable(),

  /** `null` cuando la fuente no publicó fecha para esta fila (medido: 7 de 4.251). */
  fecha_vcp: z.string().nullable(),
  /** Por cada MIL cuotapartes, tal como CAFCI lo publica. No dividir por mil acá. */
  vcp: z.number().nullable(),
  vcp_anterior: z.number().nullable(),

  var_diaria_pct: z.number().nullable(),
  var_mes_pct: z.number().nullable(),
  var_anio_pct: z.number().nullable(),
  var_12m_pct: z.number().nullable(),

  cuotapartes: z.number().nullable(),
  cuotapartes_anterior: z.number().nullable(),
  patrimonio: z.number().nullable(),
  patrimonio_anterior: z.number().nullable(),
  market_share: z.number().nullable(),

  gerente: z.string().nullable(),
  depositaria: z.string().nullable(),
  /** `null` = no informada (47 % de cobertura medida), nunca "sin calificación". */
  calificacion: z.string().nullable(),
  calificado: z.string().nullable(),
  tipo_dinero: z.string().nullable(),

  comision_ingreso: z.number().nullable(),
  honorarios_adm_sg: z.number().nullable(),
  honorarios_adm_sd: z.number().nullable(),
  gastos_ord_gestion: z.number().nullable(),
  comision_rescate: z.number().nullable(),
  comision_transferencia: z.number().nullable(),
  honorarios_exito: z.number().nullable(),

  moneda_fondo: z.string().nullable(),
  discrepancia_moneda: z.boolean(),
  /** Crudo, con centinelas (999/9999/99999/-1). Usar `dias_para_rescatar` para mostrar. */
  plazo_liq: z.number().nullable(),
  dias_para_rescatar: z.number().nullable(),
  minimo_inversion: z.number().nullable(),

  advertencia_distribucion: z.string(),
})

export type FondoFci = z.infer<typeof esquemaFondoFci>

export const esquemaPlanillaFci = z.object({
  fecha_planilla: z.string().nullable(),
  fecha_cierre_anterior: z.string().nullable(),
  fecha_base_mes: z.string().nullable(),
  fecha_base_anio: z.string().nullable(),
  fecha_base_12m: z.string().nullable(),
  total_filas: z.number(),
  capturado_en: z.string().nullable(),
  advertencia_distribucion: z.string(),
})

export type PlanillaFci = z.infer<typeof esquemaPlanillaFci>

export const esquemaSegmentosFci = z.object({
  segmentos: z.array(
    z.object({ tipo_renta: z.string(), cantidad: z.number(), monedas: z.array(z.string()) }),
  ),
  planilla: esquemaPlanillaFci.nullable(),
})

const esquemaPaginaFci = esquemaPagina(esquemaFondoFci)

const LIMITE_POR_PAGINA = 200
/** Igual tope que `useUniversoSegmento` y `useRentaVariable`: un resultado cortado en silencio no
 *  es una opción. */
const TOPE_PAGINAS = 30

/** El prefijo que distingue una pestaña de tipo de renta de FCI de un segmento de renta fija en
 *  `SelectorSegmento` — nunca colisiona con `usd_hard`, `cer`, etc. */
const PREFIJO_CLAVE_TIPO_RENTA = 'fci_'

export function claveTipoRenta(tipoRenta: string): string {
  return `${PREFIJO_CLAVE_TIPO_RENTA}${tipoRenta}`
}

export function tipoRentaDeClave(clave: string): string {
  return clave.startsWith(PREFIJO_CLAVE_TIPO_RENTA)
    ? clave.slice(PREFIJO_CLAVE_TIPO_RENTA.length)
    : clave
}

export function useSegmentosFci() {
  return useQuery({
    queryKey: claves.mercado.fci.segmentos,
    queryFn: () => apiFetch('/api/v1/fci/segmentos', esquemaSegmentosFci),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}

async function traerFondosEnteros(tipoRenta: string | null): Promise<FondoFci[]> {
  const fondos: FondoFci[] = []
  let cursor: string | null = null

  for (let pagina = 0; pagina < TOPE_PAGINAS; pagina++) {
    const busqueda = new URLSearchParams({ limit: String(LIMITE_POR_PAGINA) })
    if (tipoRenta) busqueda.set('tipo_renta', tipoRenta)
    if (cursor) busqueda.set('cursor', cursor)

    const respuesta = await apiFetch(`/api/v1/fci/fondos?${busqueda.toString()}`, esquemaPaginaFci)
    fondos.push(...respuesta.items)
    cursor = respuesta.next_cursor
    if (cursor === null) return fondos
  }

  throw new Error(
    `Los FCI de "${tipoRenta ?? 'todos'}" no terminaron de traerse en ${TOPE_PAGINAS} páginas ` +
      `(${fondos.length} fondos leídos hasta acá): se corta la carga acá para no mostrar un ` +
      'listado truncado sin decirlo.',
  )
}

/** `tipoRenta === null` trae todos los fondos — lo que necesitan el picker de F-046 y el
 *  comparador de F-067, que buscan por nombre sin filtrar por segmento. */
export function useFondosFci(tipoRenta: string | null) {
  return useQuery({
    queryKey: claves.mercado.fci.fondos(tipoRenta, null),
    queryFn: () => traerFondosEnteros(tipoRenta),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}

export function useFichaFci(codigoCafci: string | null) {
  return useQuery({
    queryKey: claves.mercado.fci.ficha(codigoCafci ?? ''),
    queryFn: () => apiFetch(`/api/v1/fci/${codigoCafci}/ficha`, esquemaFondoFci),
    enabled: codigoCafci !== null,
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
