/**
 * Abre la ficha de un instrumento sin perder la pantalla de atrás.
 *
 * Toda pantalla que muestre un ticker clickeable usa este hook y no `navigate` a secas: guardar la
 * ubicación actual en el estado de navegación es lo que hace que la ficha se abra como panel
 * superpuesto en vez de reemplazar la pantalla. Sin eso, mirar un papel desde el armador costaría
 * perder la cartera a medio armar.
 */

import { useCallback } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

export function useAbrirInstrumento() {
  const navigate = useNavigate()
  const location = useLocation()

  return useCallback(
    (ticker: string) => {
      navigate(`/instrumento/${ticker}`, { state: { fondo: location } })
    },
    [navigate, location],
  )
}
