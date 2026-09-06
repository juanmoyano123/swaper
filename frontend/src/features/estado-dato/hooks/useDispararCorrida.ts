/**
 * El botón de refresh manual: dispara `POST /jobs/corridas/matinal` — BYMA + data912 +
 * consolidación, en ese orden — y no `POST /jobs/corridas/refresh`, que es sólo BYMA y no cumple
 * lo que pide la feature ("hace un pull a la api de byma y data912").
 *
 * El backend toma `lock_de_ingesta` antes de correr (F-008): si el cron ya está corriendo, esto
 * vuelve `{ omitida: true, motivo: ... }` en vez de superponerse — se declara en la vista, no se
 * trata como error.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esCorridaOmitida, esquemaResultadoCorrida } from '../lib/schema'

export function useDispararCorrida() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiFetch('/api/v1/jobs/corridas/matinal', esquemaResultadoCorrida, { method: 'POST' }),
    onSuccess: (resultado) => {
      if (esCorridaOmitida(resultado)) return
      // Mismo contrato que ya describe `queryKeys.ts` para F-008/F-013: una corrida nueva invalida
      // todo lo que cuelga de `mercado` y la barra de estado del dato misma.
      void queryClient.invalidateQueries({ queryKey: claves.mercado.todas })
      void queryClient.invalidateQueries({ queryKey: claves.estadoDelDato })
    },
  })
}
