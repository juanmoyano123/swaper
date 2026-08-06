/**
 * Criterio 1: se navega a cada una de las seis rutas y cada una renderiza su layout sin errores
 * de consola.
 *
 * El chequeo de consola no es decorativo: React reporta por ahí las claves duplicadas, los hooks
 * mal usados y los warnings de router. Si esos pasan sin que nadie los mire, se acumulan hasta que
 * la consola deja de servir para depurar.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

// F-014: todas las rutas menos /login viven detrás de `RequiereSesion`. Estas pantallas no
// prueban el guard en sí -eso es `features/auth/__tests__/RequiereSesion.test.tsx`- así que acá
// se simula una sesión siempre presente para poder seguir probando lo que este archivo prueba de
// verdad: que cada una de las seis pantallas renderiza su layout.
vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: () =>
        Promise.resolve({ data: { session: { access_token: 'jwt-de-prueba' } } }),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}))

import { AppRoutes } from '../rutas'
import { crearQueryClient } from '../queryClient'

// La barra superior consulta el health apenas monta. Que el backend conteste o no es asunto de
// otro test; acá solo importa que no reviente el render.
beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({
            status: 'ok',
            database: 'ok',
            last_market_snapshot_at: null,
            warnings: [],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    ),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

type Entrada = string | { pathname: string; state: unknown }

/**
 * Monta la aplicación en las ubicaciones dadas. Aceptar varias entradas permite reproducir un
 * historial de verdad, que es lo que necesita cualquier prueba de "volver atrás".
 */
function montar(entradas: Entrada | Entrada[]) {
  const lista = Array.isArray(entradas) ? entradas : [entradas]
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <MemoryRouter initialEntries={lista} initialIndex={lista.length - 1}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const PANTALLAS = [
  { ruta: '/login', titulo: 'Ingresar' },
  { ruta: '/monitor', titulo: 'Monitor de mercado' },
  { ruta: '/armador', titulo: 'Armador' },
  { ruta: '/optimizador', titulo: 'Optimizador' },
  { ruta: '/carteras', titulo: 'Mis carteras' },
  { ruta: '/instrumento/AL30D', titulo: 'AL30D' },
] as const

describe('las seis pantallas', () => {
  it.each(PANTALLAS)('$ruta renderiza su layout sin errores de consola', async ({ ruta, titulo }) => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})

    montar(ruta)

    expect(await screen.findByRole('heading', { level: 1, name: titulo })).toBeInTheDocument()
    expect(error).not.toHaveBeenCalled()
    expect(warn).not.toHaveBeenCalled()
  })
})

describe('navegación de borde', () => {
  it('la raíz redirige al monitor', async () => {
    montar('/')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Monitor de mercado' }),
    ).toBeInTheDocument()
  })

  it('una ruta inexistente muestra el aviso y no una pantalla en blanco', async () => {
    montar('/no-existe')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Esa pantalla no existe' }),
    ).toBeInTheDocument()
  })

  it('el ingreso queda fuera del layout: sin barra superior', async () => {
    montar('/login')
    await screen.findByRole('heading', { level: 1, name: 'Ingresar' })
    expect(screen.queryByRole('link', { name: 'Monitor' })).not.toBeInTheDocument()
  })
})

describe('la ficha de instrumento se ve de dos formas', () => {
  it('entrando por la URL directa es una página completa', async () => {
    montar('/instrumento/AL30D')

    expect(await screen.findByRole('heading', { level: 1, name: 'AL30D' })).toBeInTheDocument()
    // Sin pantalla de fondo no hay drawer que superponer.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('abriéndola desde otra pantalla es un panel superpuesto que conserva el fondo', async () => {
    montar({ pathname: '/instrumento/AL30D', state: { fondo: { pathname: '/armador' } } })

    const drawer = await screen.findByRole('dialog', { name: 'Ficha de AL30D' })
    expect(drawer).toBeInTheDocument()
    // Lo que importa: la pantalla desde la que se abrió sigue montada detrás.
    expect(screen.getByRole('heading', { level: 1, name: 'Armador' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cerrar la ficha' })).toBeInTheDocument()
  })

  it('se cierra con Escape y devuelve la pantalla de fondo', async () => {
    // Con el historial real: se venía del armador y desde ahí se abrió la ficha.
    montar(['/armador', { pathname: '/instrumento/AL30D', state: { fondo: { pathname: '/armador' } } }])
    await screen.findByRole('dialog', { name: 'Ficha de AL30D' })

    await userEvent.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { level: 1, name: 'Armador' })).toBeInTheDocument()
  })
})
