/**
 * El listado de "Mis carteras" (F-041) — sólo las columnas denormalizadas, nunca el `snapshot`
 * entero: PostgREST hace la proyección del lado del servidor, así que listar cien carteras no baja
 * cien snapshots.
 *
 * RLS filtra por `user_id` del lado de la base (GWT-3): esta consulta no filtra nada acá, confía
 * en la policy `carteras_select` de `supabase/migrations/20260806151149_usuario.sql`.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { claves } from '@/lib/api/queryKeys'
import { supabase } from '@/lib/supabase'

import { esquemaFilaListado, type FilaListado } from '../lib/esquemaSnapshot'

const COLUMNAS_LISTADO = 'id, nombre, descripcion, origen, moneda_referencia, monto, resumen, snapshot_en'

export function useCarterasGuardadas() {
  return useQuery({
    queryKey: claves.carteras.todas,
    queryFn: async (): Promise<FilaListado[]> => {
      const { data, error } = await supabase
        .from('carteras')
        .select(COLUMNAS_LISTADO)
        .order('snapshot_en', { ascending: false })

      if (error) throw new Error(`No se pudo leer el listado de carteras guardadas: ${error.message}`)

      return data.map((fila) => esquemaFilaListado.parse(fila))
    },
    ...TIEMPOS.carteras,
  })
}
