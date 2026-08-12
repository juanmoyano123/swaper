/**
 * El punto donde F-014 enchufa la verificación de sesión.
 *
 * Esto NO es el aislamiento por asesor: eso lo aplica Row Level Security en PostgreSQL contra
 * `user_id`, adentro de la base, y sigue valiendo aunque este componente tuviera un bug. Lo que
 * hace acá es más chico: decidir si hay alguien logueado y, si no, mandarlo a `/login` sin que
 * ninguna pantalla de adentro tenga que enterarse.
 *
 * Se suscribe a `onAuthStateChange` en vez de preguntar una sola vez porque la sesión puede
 * desaparecer sin que el asesor haga nada —el refresh token vence, o cierra sesión en otra
 * pestaña— y ahí es donde importa el último criterio de aceptación de F-014: la sesión expirada
 * no se detecta recién cuando algo falla a mitad de una operación, se detecta acá y redirige
 * llevándose la ubicación (`state.desde`), así `LoginPage` puede devolver al asesor adonde
 * estaba en vez de mandarlo siempre a la pantalla por default.
 */

import type { Session } from '@supabase/supabase-js'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import { EstadoCarga } from '@/components/EstadoCarga'
import { supabase } from '@/lib/supabase'

export function RequiereSesion({ children }: { children: ReactNode }) {
  const location = useLocation()
  // undefined: todavía no se consultó a Supabase. null: se consultó y no hay sesión.
  const [sesion, setSesion] = useState<Session | null | undefined>(undefined)

  useEffect(() => {
    let vigente = true

    supabase.auth.getSession().then(({ data }) => {
      if (vigente) setSesion(data.session)
    })

    const { data: suscripcion } = supabase.auth.onAuthStateChange((_evento, nuevaSesion) => {
      setSesion(nuevaSesion)
    })

    return () => {
      vigente = false
      suscripcion.subscription.unsubscribe()
    }
  }, [])

  if (sesion === undefined) {
    return <EstadoCarga que="la sesión" />
  }

  if (sesion === null) {
    return <Navigate to="/login" replace state={{ desde: location }} />
  }

  return <>{children}</>
}
