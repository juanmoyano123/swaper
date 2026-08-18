/**
 * Los documentos de la serie que declara un documento del prospecto — F-072.
 *
 * A diferencia de los otros hooks de la ficha, éste no se dispara al cargar: espera a que el asesor
 * toque "Ver serie" en un documento. El gate es el `uuid` en `null` (`enabled`), el mismo mecanismo
 * que ya usa el resto del proyecto para diferir una query. La razón no es sólo ahorrar red: son dos
 * llamadas a la CNV por documento, y la ficha abre con varios grupos a la vista.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaSerieCnv } from '../lib/schema'

export function useSerieProspecto(ticker: string, uuid: string | null) {
  return useQuery({
    queryKey: claves.referencia.serieProspecto(uuid ?? ''),
    queryFn: () =>
      apiFetch(`/api/v1/instrumentos/${ticker}/prospecto/${uuid}/serie`, esquemaSerieCnv),
    enabled: uuid !== null,
    retry: false,
  })
}
