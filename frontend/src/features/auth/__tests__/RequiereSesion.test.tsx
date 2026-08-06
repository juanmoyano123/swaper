/**
 * Criterio 4 de F-014: una sesión que no está (o que deja de estar) redirige a /login sin que la
 * pantalla protegida tenga que hacer nada. El aislamiento por asesor no se prueba acá -eso es
 * RLS contra la base real, en `backend/tests/test_auth_integration.py`- esto sólo prueba el guard
 * de rutas del lado del cliente.
 */

import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

type Escucha = (evento: string, sesion: unknown) => void

const escuchas: Escucha[] = []
const getSessionMock = vi.fn()

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: (...args: unknown[]) => getSessionMock(...args),
      onAuthStateChange: (cb: Escucha) => {
        escuchas.push(cb)
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      },
    },
  },
}))

import { RequiereSesion } from '../RequiereSesion'

function montar(entrada = '/protegida') {
  return render(
    <MemoryRouter initialEntries={[entrada]}>
      <Routes>
        <Route path="/login" element={<div>pantalla de login</div>} />
        <Route
          path="/protegida"
          element={
            <RequiereSesion>
              <div>contenido protegido</div>
            </RequiereSesion>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  escuchas.length = 0
  vi.clearAllMocks()
})

describe('RequiereSesion', () => {
  it('mientras se consulta la sesión muestra un estado de carga, no la pantalla vacía', () => {
    getSessionMock.mockReturnValue(new Promise(() => {}))

    montar()

    expect(screen.getByRole('status')).toHaveTextContent('sesión')
    expect(screen.queryByText('contenido protegido')).not.toBeInTheDocument()
  })

  it('sin sesión redirige a /login', async () => {
    getSessionMock.mockResolvedValue({ data: { session: null } })

    montar()

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })

  it('con sesión válida muestra el contenido protegido', async () => {
    getSessionMock.mockResolvedValue({ data: { session: { access_token: 'tok-123' } } })

    montar()

    expect(await screen.findByText('contenido protegido')).toBeInTheDocument()
  })

  it('si la sesión expira en caliente, redirige a /login sin esperar a la próxima navegación', async () => {
    getSessionMock.mockResolvedValue({ data: { session: { access_token: 'tok-123' } } })
    montar()
    await screen.findByText('contenido protegido')

    // Lo que dispara `autoRefreshToken` cuando el refresh falla: la propia librería llama a los
    // suscriptores de `onAuthStateChange` con `SIGNED_OUT` y sesión null.
    escuchas.forEach((cb) => cb('SIGNED_OUT', null))

    expect(await screen.findByText('pantalla de login')).toBeInTheDocument()
  })
})
