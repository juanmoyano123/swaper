/**
 * El estado del dato, consultado desde el layout — F-013.
 *
 * Es una sola consulta para las seis pantallas: la clave es fija, así que TanStack Query la comparte
 * entre todas y no la vuelve a pedir al navegar. La barra vive en el layout, que no se desmonta al
 * cambiar de sección, así que el componente ni siquiera se vuelve a montar.
 *
 * **Se refresca por reloj y no por foco de ventana.** El `refetchOnWindowFocus` está apagado
 * globalmente por una razón que acá aplica doble: el dato de mercado llega con 20 minutos de demora
 * declarada, así que volver a pedirlo cada vez que alguien vuelve a la pestaña simularía una
 * frescura que la fuente no tiene. El intervalo elegido es el mismo del refresh intra-rueda del job
 * de F-008 (`ingesta_refresh_minutos`, 15 minutos), dividido por tres: alcanza para que una corrida
 * nueva se vea en pocos minutos y el backend contesta desde su caché mientras no haya ninguna.
 */

import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'

import { esquemaEstadoDelDato } from '../lib/schema'

/** Cinco minutos. Ver el docstring: es un tercio del refresh intra-rueda del job. */
export const INTERVALO_MS = 5 * 60_000

export function useEstadoDelDato() {
  return useQuery({
    queryKey: claves.estadoDelDato,
    queryFn: () => apiFetch('/api/v1/estado-del-dato', esquemaEstadoDelDato),
    staleTime: INTERVALO_MS,
    refetchInterval: INTERVALO_MS,
    // Que el backend esté caído es un estado normal y esperable, no una excepción a reintentar:
    // la barra lo muestra tal cual y el próximo sondeo lo corrige solo. Mismo criterio que
    // `useSalud`, y por lo mismo — una barra que reintenta tres veces tarda en admitir que no sabe.
    retry: false,
  })
}
