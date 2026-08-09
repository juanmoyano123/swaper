/**
 * Carga asistida de la lámina de una especie, con trazabilidad y propagación — F-025.
 *
 * `POST /api/v1/condiciones/{ticker}/lamina`. En éxito invalida el universo entero: la lámina se
 * propaga por emisión (AL30/AL30D/AL30C son el mismo bono) y puede tocar filas de la cartera
 * distintas de la que el asesor tocó. La clave `['mercado', 'universo', 'todas']` no sale de
 * `claves.mercado` — `useEspeciesUniverso.ts` ya la define inline por la misma razón (ese archivo
 * de claves está congelado esta tanda) y acá hay que invalidar exactamente esa.
 *
 * `apiFetch` lanza `ApiError` para cualquier respuesta no-2xx, 409 incluido, antes de validar el
 * cuerpo contra un esquema — el conflicto nunca pasa por `esquemaResultadoCargaLamina`. Pero
 * `client.ts::comoApiError` guarda el cuerpo crudo en `ApiError.details` cuando no matchea el
 * contrato de error del backend (`esquemaError`), que es justo el caso acá: el cuerpo del 409 es
 * `{ guardado, ticker, conflicto }`, no `{ error: {...} }`. Alcanza con leer `details` en el catch
 * — no hace falta reescribir la llamada a mano.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { ApiError } from '@/lib/api/errors'

import { esquemaConflictoLamina, esquemaResultadoCargaLamina, type ConflictoLamina } from '../lib/schema'

const CLAVE_UNIVERSO = ['mercado', 'universo', 'todas'] as const

export type ResultadoCargarLamina =
  | { guardado: true; lamina: number }
  | { guardado: false; conflicto: ConflictoLamina | null }

export function useCargarLamina() {
  const queryClient = useQueryClient()

  return useMutation<ResultadoCargarLamina, ApiError | Error, { ticker: string; valor: number }>({
    mutationFn: async ({ ticker, valor }) => {
      try {
        const resultado = await apiFetch(
          `/api/v1/condiciones/${encodeURIComponent(ticker)}/lamina`,
          esquemaResultadoCargaLamina,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ valor }),
          },
        )
        return { guardado: true, lamina: resultado.lamina }
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          const cuerpo = error.details as { conflicto?: unknown } | null
          const conflicto = esquemaConflictoLamina.safeParse(cuerpo?.conflicto)
          return { guardado: false, conflicto: conflicto.success ? conflicto.data : null }
        }
        throw error
      }
    },
    onSuccess: (resultado) => {
      if (resultado.guardado) {
        queryClient.invalidateQueries({ queryKey: CLAVE_UNIVERSO })
      }
    },
  })
}
