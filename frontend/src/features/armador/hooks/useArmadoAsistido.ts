/**
 * El armado asistido: precarga una cartera de arranque a partir del mandato del cliente — F-019.
 *
 * `POST /api/v1/armado`. Es un `useMutation` y no un `useQuery` porque el pedido lo dispara el
 * asesor con un botón ("Armar cartera asistida") y no la sola presencia de los cinco parámetros
 * en pantalla -- mismo criterio que `useCargarLamina` (F-025), la otra mutación de este paquete.
 *
 * En éxito, reemplaza la cartera del store entero vía `cargarCartera` (armado asistido es un
 * **punto de partida**, no un agregado: la ficha lo dice así, y `carteraStore.tsx` documenta la
 * misma decisión en su acción). No invalida ninguna clave de `claves.mercado`: esto no cambia el
 * universo, sólo precarga posiciones sobre el universo que ya está en caché.
 */

import { useMutation } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'

import { useArmadorAcciones } from '../store/carteraStore'
import {
  esquemaResultadoArmado,
  type ParametrosArmadoAsistido,
  type ResultadoArmado,
} from '../lib/schemaArmado'

export function useArmadoAsistido() {
  const { cargarCartera } = useArmadorAcciones()

  return useMutation<ResultadoArmado, Error, ParametrosArmadoAsistido>({
    mutationFn: (parametros) =>
      apiFetch('/api/v1/armado', esquemaResultadoArmado, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(parametros),
      }),
    onSuccess: (resultado) => {
      // La clase la decide el backend (Tanda 13): antes se forzaba `renta_fija` en todas porque el
      // armado sólo elegía bonos, y ahora también elige acciones. Forzarla acá haría que una acción
      // entrara al resolver de bonos y saliera con nominales sin sentido.
      cargarCartera(
        resultado.posiciones.map((posicion) => ({
          ticker: posicion.ticker,
          peso: posicion.pct_cartera,
          clase: posicion.clase,
        })),
      )
    },
  })
}
