/**
 * Ingreso por invitación, sin registro abierto.
 *
 * Sólo hay login: `signInWithPassword` contra Supabase Auth. No existe un formulario de alta —las
 * invitaciones se mandan desde el panel de Supabase, no desde acá— y tampoco un "olvidé mi
 * contraseña": las dos cosas abrirían una puerta que la spec de F-014 pide cerrada.
 *
 * El caso especial es el link de invitación en sí. Cuando el asesor lo abre, Supabase le arma una
 * sesión temporal y dispara el evento `PASSWORD_RECOVERY` —el mismo mecanismo que usa para
 * "olvidé mi contraseña", reusado acá porque el problema es idéntico: probar que es dueño del
 * mail antes de dejarlo elegir una contraseña—. Mientras esa sesión esté activa se muestra el
 * formulario para definirla en lugar del de ingreso; sin esto, el link serviría para autenticar
 * una vez y el asesor nunca podría volver a entrar.
 */

import type { AuthError } from '@supabase/supabase-js'
import { useEffect, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { supabase } from '@/lib/supabase'

type EstadoDeNavegacion = { desde?: { pathname: string } } | null

/** Los mensajes de Supabase vienen en inglés; acá se traducen los que puede ver un asesor real. */
function mensajeDeAuthError(error: AuthError): string {
  if (error.message.includes('Invalid login credentials')) {
    return 'El email o la contraseña no son correctos.'
  }
  if (error.message.includes('Email not confirmed')) {
    return 'La invitación todavía no fue confirmada. Revisá el mail de invitación.'
  }
  return error.message
}

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const destino = (location.state as EstadoDeNavegacion)?.desde?.pathname || '/'

  const [definiendoContrasena, setDefiniendoContrasena] = useState(false)
  const [email, setEmail] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const { data: suscripcion } = supabase.auth.onAuthStateChange((evento) => {
      if (evento === 'PASSWORD_RECOVERY') setDefiniendoContrasena(true)
    })
    return () => suscripcion.subscription.unsubscribe()
  }, [])

  async function ingresar(evento: FormEvent) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)

    const { error: errorSupabase } = await supabase.auth.signInWithPassword({
      email,
      password: contrasena,
    })

    setEnviando(false)
    if (errorSupabase) {
      setError(mensajeDeAuthError(errorSupabase))
      return
    }
    navigate(destino, { replace: true })
  }

  async function definirContrasena(evento: FormEvent) {
    evento.preventDefault()
    setEnviando(true)
    setError(null)

    const { error: errorSupabase } = await supabase.auth.updateUser({ password: contrasena })

    setEnviando(false)
    if (errorSupabase) {
      setError(mensajeDeAuthError(errorSupabase))
      return
    }
    navigate('/', { replace: true })
  }

  if (definiendoContrasena) {
    return (
      <Pantalla
        titulo="Definir contraseña"
        bajada="Es la última vez que hace falta el link de invitación."
      >
        <Panel>
          <form
            onSubmit={definirContrasena}
            aria-label="Definir contraseña"
            style={{ display: 'grid', gap: 12, maxWidth: 320 }}
          >
            <div>
              <label
                htmlFor="contrasena-nueva"
                style={{
                  display: 'block',
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--dim)',
                  marginBottom: 4,
                }}
              >
                Contraseña nueva
              </label>
              <input
                id="contrasena-nueva"
                type="password"
                required
                minLength={8}
                autoComplete="new-password"
                value={contrasena}
                onChange={(evento) => setContrasena(evento.target.value)}
                style={{
                  display: 'block',
                  width: '100%',
                  font: 'inherit',
                  fontSize: 13,
                  padding: '7px 10px',
                  borderRadius: 3,
                  border: '1px solid var(--lin)',
                  background: 'var(--pan2)',
                  color: 'var(--tx)',
                }}
              />
            </div>

            {error && (
              <p role="alert" style={{ margin: 0, fontSize: 12.5, color: 'var(--neg)' }}>
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={enviando}
              style={{
                font: 'inherit',
                fontSize: 13,
                fontWeight: 600,
                padding: '8px 12px',
                borderRadius: 3,
                border: '1px solid var(--ac)',
                background: 'var(--ac)',
                color: '#0a0e13',
                cursor: enviando ? 'default' : 'pointer',
                opacity: enviando ? 0.7 : 1,
              }}
            >
              {enviando ? 'Guardando…' : 'Guardar y entrar'}
            </button>
          </form>
        </Panel>
      </Pantalla>
    )
  }

  return (
    <Pantalla titulo="Ingresar" bajada="Acceso por invitación. No hay registro abierto.">
      <Panel>
        <form onSubmit={ingresar} aria-label="Ingresar" style={{ display: 'grid', gap: 12, maxWidth: 320 }}>
          <div>
            <label
              htmlFor="email"
              style={{
                display: 'block',
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--dim)',
                marginBottom: 4,
              }}
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(evento) => setEmail(evento.target.value)}
              style={{
                display: 'block',
                width: '100%',
                font: 'inherit',
                fontSize: 13,
                padding: '7px 10px',
                borderRadius: 3,
                border: '1px solid var(--lin)',
                background: 'var(--pan2)',
                color: 'var(--tx)',
              }}
            />
          </div>

          <div>
            <label
              htmlFor="contrasena"
              style={{
                display: 'block',
                fontSize: 10,
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: 'var(--dim)',
                marginBottom: 4,
              }}
            >
              Contraseña
            </label>
            <input
              id="contrasena"
              type="password"
              required
              autoComplete="current-password"
              value={contrasena}
              onChange={(evento) => setContrasena(evento.target.value)}
              style={{
                display: 'block',
                width: '100%',
                font: 'inherit',
                fontSize: 13,
                padding: '7px 10px',
                borderRadius: 3,
                border: '1px solid var(--lin)',
                background: 'var(--pan2)',
                color: 'var(--tx)',
              }}
            />
          </div>

          {error && (
            <p role="alert" style={{ margin: 0, fontSize: 12.5, color: 'var(--neg)' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={enviando}
            style={{
              font: 'inherit',
              fontSize: 13,
              fontWeight: 600,
              padding: '8px 12px',
              borderRadius: 3,
              border: '1px solid var(--ac)',
              background: 'var(--ac)',
              color: '#0a0e13',
              cursor: enviando ? 'default' : 'pointer',
              opacity: enviando ? 0.7 : 1,
            }}
          >
            {enviando ? 'Ingresando…' : 'Ingresar'}
          </button>

          <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>
            El acceso lo habilita un asesor con permisos desde el panel de Supabase. No hay alta
            abierta.
          </p>
        </form>
      </Panel>
    </Pantalla>
  )
}
