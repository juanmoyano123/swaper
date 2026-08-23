/**
 * Abre la ficha de un fondo común sin perder la pantalla de atrás — F-057.
 *
 * Mismo patrón que `useAbrirInstrumento`: la ubicación actual va en el estado de navegación para
 * que la ficha se abra como panel superpuesto, no como reemplazo de pantalla.
 */

import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export function useAbrirFondoFci() {
  const navigate = useNavigate()
  const location = useLocation()

  return useCallback(
    (codigoCafci: string) => {
      navigate(`/fci/${codigoCafci}`, { state: { fondo: location } })
    },
    [navigate, location],
  )
}
