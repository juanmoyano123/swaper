/**
 * El detalle de una cartera guardada (F-041) — la fila entera, snapshot incluido.
 *
 * `snapshot` se valida con `safeParse` y no con `parse`: una fila con una versión de snapshot que
 * este frontend todavía no sabe leer, o un dato corrupto, se declara "no se pudo leer el snapshot"
 * en el detalle en vez de tirar la pantalla entera (regla 1: se declara el faltante, no se rompe
 * en silencio ni se inventa un contenido).
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { claves } from '@/lib/api/queryKeys'
import { supabase } from '@/lib/supabase'

import { esquemaFilaDetalle, esquemaSnapshotCartera, type SnapshotCartera } from '../lib/esquemaSnapshot'

export interface CarteraGuardadaDetalle {
  id: string
  nombre: string
  descripcion: string | null
  origen: string
  monedaReferencia: string
  monto: number
  resumen: string
  snapshotEn: string
  /** `null` cuando el snapshot no se pudo validar contra ningún schema conocido. */
  snapshot: SnapshotCartera | null
}

export function useCarteraGuardada(id: string) {
  return useQuery({
    queryKey: claves.carteras.detalle(id),
    queryFn: async (): Promise<CarteraGuardadaDetalle> => {
      const { data, error } = await supabase.from('carteras').select('*').eq('id', id).single()

      if (error) throw new Error(`No se pudo leer la cartera guardada: ${error.message}`)

      const fila = esquemaFilaDetalle.parse(data)
      const snapshot = esquemaSnapshotCartera.safeParse(fila.snapshot)

      return {
        id: fila.id,
        nombre: fila.nombre,
        descripcion: fila.descripcion,
        origen: fila.origen,
        monedaReferencia: fila.moneda_referencia,
        monto: fila.monto,
        resumen: fila.resumen,
        snapshotEn: fila.snapshot_en,
        snapshot: snapshot.success ? snapshot.data : null,
      }
    },
    enabled: id.length > 0,
    ...TIEMPOS.carteras,
  })
}
