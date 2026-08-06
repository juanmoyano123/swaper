/**
 * Configuración de TanStack Query.
 *
 * La decisión de fondo: el dato de mercado llega con una demora declarada de 20 minutos, así que
 * refetchear cada vez que la ventana toma foco simularía una frescura que la fuente no tiene. El
 * refresco es explícito y por invalidación, no por reflejo del navegador.
 */

import { QueryClient } from '@tanstack/react-query'

import { vale_reintentar } from '@/lib/api/errors'

const MINUTO = 60_000

/**
 * Tiempos por naturaleza del dato. Cada feature importa el que le corresponde en vez de inventar
 * su propio número, que es como terminan conviviendo cinco políticas de caché distintas.
 */
export const TIEMPOS = {
  /** Precios, puntas, universo: los invalida el refresh de la rueda, no el reloj. */
  mercado: { staleTime: 5 * MINUTO },
  /** Condiciones de emisión y demás dato curado: cambia por ingesta. */
  referencia: { staleTime: Infinity },
  /** Salud del backend: siempre se quiere el estado de ahora. */
  salud: { staleTime: 0, refetchInterval: MINUTO },
} as const

export function crearQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        staleTime: MINUTO,
        // Un 4xx da siempre el mismo resultado: reintentarlo solo demora el error en pantalla.
        retry: (intentos, error) => vale_reintentar(error) && intentos < 2,
      },
      mutations: { retry: false },
    },
  })
}
