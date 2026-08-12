/**
 * Borrar una cartera guardada (F-041). La policy `carteras_delete` de la migración de F-014 ya
 * existe (`auth.uid() = user_id`); sin este hook el listado acumularía pruebas sin salida.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { claves } from '@/lib/api/queryKeys'
import { supabase } from '@/lib/supabase'

export function useBorrarCartera() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (id: string): Promise<void> => {
      const { error } = await supabase.from('carteras').delete().eq('id', id)
      if (error) throw new Error(`No se pudo borrar la cartera: ${error.message}`)
    },
    onSuccess: (_dato, id) => {
      void queryClient.invalidateQueries({ queryKey: claves.carteras.todas })
      queryClient.removeQueries({ queryKey: claves.carteras.detalle(id) })
    },
  })
}
