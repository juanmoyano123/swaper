/**
 * Los documentos que el emisor de una ON presentó ante la CNV — F-072.
 *
 * Consulta independiente de la ficha de precios, mismo patrón que `useCondicionesInstrumento`: el
 * dato viene de una fuente externa consultada en vivo (`app/externos/cnv.py`), no del universo, así
 * que un refresh de precios no lo invalida.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaProspecto } from '../lib/schema'

export function useProspectoInstrumento(ticker: string | undefined) {
  return useQuery({
    queryKey: claves.referencia.prospecto(ticker ?? ''),
    queryFn: () => apiFetch(`/api/v1/instrumentos/${ticker}/prospecto`, esquemaProspecto),
    enabled: ticker !== undefined,
    retry: false,
  })
}
