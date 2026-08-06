/**
 * Los otros dos criterios de F-014 que se prueban del lado del cliente:
 *
 *   GIVEN un visitante sin invitación WHEN intenta registrarse
 *   THEN no existe formulario de registro abierto y el acceso es denegado
 *
 * -se prueba por ausencia: no hay ningún campo ni link de alta en esta pantalla- y el camino
 * completo de invitación: el link manda a Supabase Auth a emitir `PASSWORD_RECOVERY`, y desde acá
 * eso tiene que abrir el formulario de "definir contraseña", no el de login.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

type Escucha = (evento: string, sesion: unknown) => void

const escuchas: Escucha[] = []
const signInMock = vi.fn()
const updateUserMock = vi.fn()

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      signInWithPassword: (...args: unknown[]) => signInMock(...args),
      updateUser: (...args: unknown[]) => updateUserMock(...args),
      onAuthStateChange: (cb: Escucha) => {
        escuchas.push(cb)
        return { data: { subscription: { unsubscribe: vi.fn() } } }
      },
    },
  },
}))

import { LoginPage } from '../LoginPage'

function montar(entrada: string | { pathname: string; state?: unknown } = '/login') {
  return render(
    <MemoryRouter initialEntries={[entrada]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>pantalla por default</div>} />
        <Route path="/armador" element={<div>pantalla de armador</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => {
  escuchas.length = 0
  vi.clearAllMocks()
})

describe('sin registro abierto', () => {
  it('no hay ningún campo ni acción para darse de alta', () => {
    montar()

    expect(screen.queryByLabelText(/confirm/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /registrar|crear cuenta|alta/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeInTheDocument()
  })
})

describe('ingreso con email y contraseña', () => {
  it('manda el email y la contraseña tal como se cargaron', async () => {
    signInMock.mockResolvedValue({ error: null })
    montar()

    await userEvent.type(screen.getByLabelText('Email'), 'asesor@x.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreta-123')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(signInMock).toHaveBeenCalledWith({ email: 'asesor@x.com', password: 'secreta-123' })
  })

  it('con credenciales inválidas muestra el error traducido, no el mensaje crudo de Supabase', async () => {
    signInMock.mockResolvedValue({ error: { message: 'Invalid login credentials' } })
    montar()

    await userEvent.type(screen.getByLabelText('Email'), 'asesor@x.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'mala')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    const alerta = await screen.findByRole('alert')
    expect(alerta).toHaveTextContent('El email o la contraseña no son correctos.')
  })

  it('al loguearse bien vuelve a la pantalla desde la que lo mandaron a /login', async () => {
    signInMock.mockResolvedValue({ error: null })
    montar({ pathname: '/login', state: { desde: { pathname: '/armador' } } })

    await userEvent.type(screen.getByLabelText('Email'), 'asesor@x.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreta-123')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByText('pantalla de armador')).toBeInTheDocument()
  })

  it('sin ubicación previa, entra a la pantalla por default', async () => {
    signInMock.mockResolvedValue({ error: null })
    montar()

    await userEvent.type(screen.getByLabelText('Email'), 'asesor@x.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreta-123')
    await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))

    expect(await screen.findByText('pantalla por default')).toBeInTheDocument()
  })
})

describe('link de invitación', () => {
  it('con PASSWORD_RECOVERY muestra el formulario de contraseña nueva en vez del de ingreso', async () => {
    montar()

    escuchas.forEach((cb) => cb('PASSWORD_RECOVERY', {}))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Definir contraseña' }),
    ).toBeInTheDocument()
    expect(screen.queryByLabelText('Email')).not.toBeInTheDocument()
  })

  it('define la contraseña con updateUser y entra a la aplicación', async () => {
    updateUserMock.mockResolvedValue({ error: null })
    montar()
    escuchas.forEach((cb) => cb('PASSWORD_RECOVERY', {}))
    await screen.findByRole('heading', { level: 1, name: 'Definir contraseña' })

    await userEvent.type(screen.getByLabelText('Contraseña nueva'), 'nueva-secreta-123')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar y entrar' }))

    expect(updateUserMock).toHaveBeenCalledWith({ password: 'nueva-secreta-123' })
    expect(await screen.findByText('pantalla por default')).toBeInTheDocument()
  })
})
