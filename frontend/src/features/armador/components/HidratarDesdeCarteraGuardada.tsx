/**
 * F-041 — "Abrir en el armador" desde una cartera guardada navega acá con el mandato en
 * `location.state.carteraGuardada`. Se lee una sola vez al montar y se limpia el `state` con
 * `replace`, para que recargar la página no vuelva a pisar lo que el asesor ya esté editando.
 *
 * Sólo trae el mandato (`posiciones` + `montoTotal`), no la foto valuada: eso lo recalcula el
 * armador con los precios de hoy, que es justamente lo que "reabrir para seguir trabajando" pide
 * — a diferencia del detalle congelado de `/carteras/:id`, que muestra los precios del momento.
 */

import { useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { useArmadorAcciones, type PosicionArmador } from '../store/carteraStore'

interface EstadoDeNavegacionArmador {
  carteraGuardada?: { posiciones: PosicionArmador[]; montoTotalUsd: number }
}

export function HidratarDesdeCarteraGuardada() {
  const location = useLocation()
  const navigate = useNavigate()
  const acciones = useArmadorAcciones()
  const yaHidratado = useRef(false)

  useEffect(() => {
    if (yaHidratado.current) return

    const carteraGuardada = (location.state as EstadoDeNavegacionArmador | null)?.carteraGuardada
    if (!carteraGuardada) return

    yaHidratado.current = true
    acciones.cargarCartera(carteraGuardada.posiciones)
    acciones.fijarMontoTotal(carteraGuardada.montoTotalUsd)
    navigate(location.pathname, { replace: true })
  }, [location.pathname, location.state, navigate, acciones])

  return null
}
