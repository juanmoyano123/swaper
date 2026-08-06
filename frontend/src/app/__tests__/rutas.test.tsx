/**
 * Criterio 1: se navega a cada una de las seis rutas y cada una renderiza su layout sin errores
 * de consola.
 *
 * El chequeo de consola no es decorativo: React reporta por ahí las claves duplicadas, los hooks
 * mal usados y los warnings de router. Si esos pasan sin que nadie los mire, se acumulan hasta que
 * la consola deja de servir para depurar.
 */

import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { crearQueryClient } from '../queryClient'
import { rutas } from '../rutas'

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

function montar(ruta: string) {
  const router = createMemoryRouter(rutas, { initialEntries: [ruta] })
  return render(
    <QueryClientProvider client={crearQueryClient()}>
      <RouterProvider router={router} />
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
})
