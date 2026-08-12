/**
 * Guardar una cartera (F-041) — siempre un INSERT nuevo: el snapshot es inmutable por definición
 * del GWT-1 (una propuesta tiene que poder reproducirse tal como se presentó), así que no hay
 * "actualizar" una cartera guardada. `user_id` no se manda: `carteras.user_id` tiene
 * `DEFAULT auth.uid()` desde la migración F-041, y la policy `WITH CHECK` sigue verificando la
 * fila igual.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { claves } from '@/lib/api/queryKeys'
import { supabase } from '@/lib/supabase'

import type { SnapshotCartera } from '../lib/esquemaSnapshot'

export interface NuevaCarteraGuardada {
  nombre: string
  descripcion: string | null
  origen: SnapshotCartera['origen']
  monedaReferencia: string
  monto: number
  resumen: string
  snapshotEn: string
  snapshot: SnapshotCartera
}

export function useGuardarCartera() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (nueva: NuevaCarteraGuardada): Promise<{ id: string }> => {
      const { data, error } = await supabase
        .from('carteras')
        .insert({
          nombre: nueva.nombre,
          descripcion: nueva.descripcion,
          origen: nueva.origen,
          moneda_referencia: nueva.monedaReferencia,
          monto: nueva.monto,
          resumen: nueva.resumen,
          snapshot_en: nueva.snapshotEn,
          snapshot: nueva.snapshot,
        })
        .select('id')
        .single()

      if (error) throw new Error(`No se pudo guardar la cartera: ${error.message}`)

      return { id: data.id as string }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: claves.carteras.todas })
    },
  })
}
