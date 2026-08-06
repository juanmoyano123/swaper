/**
 * El punto donde F-014 enchufa la verificación de sesión.
 *
 * Hoy deja pasar todo: no hay autenticación todavía y fingirla sería peor que no tenerla. Lo que
 * aporta es el lugar — cuando exista la sesión, este componente redirige a /login y ninguna
 * pantalla necesita enterarse.
 */

import type { ReactNode } from 'react'

export function RequiereSesion({ children }: { children: ReactNode }) {
  // F-014: leer la sesión de Supabase Auth y, si no hay, <Navigate to="/login" replace state={{ desde: location }} />
  return <>{children}</>
}
