/**
 * Criterio 2, segunda mitad: la vista muestra el mensaje del contrato y el código de soporte, y
 * nunca una pantalla en blanco.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApiError, ErrorDeRed } from '@/lib/api/errors'

import { EstadoError } from '../EstadoError'

describe('EstadoError', () => {
  it('muestra el mensaje del backend y el código de soporte', () => {
    render(
      <EstadoError
        error={
          new ApiError({
            code: 'validation_error',
            message: 'El monto tiene que ser mayor a cero',
            status: 422,
            requestId: 'abc123',
          })
        }
      />,
    )

    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('El monto tiene que ser mayor a cero')).toBeInTheDocument()
    // El request_id existe para rastrear el error en los logs: tiene que llegar a la pantalla.
    expect(screen.getByText(/abc123/)).toBeInTheDocument()
    expect(screen.getByText(/validation_error/)).toBeInTheDocument()
  })

  it('dice que no hay conexión cuando el servicio no responde', () => {
    render(<EstadoError error={new ErrorDeRed(new TypeError('Failed to fetch'))} />)
    expect(screen.getByText('No hay conexión con el servicio')).toBeInTheDocument()
  })

  it('no inventa un mensaje técnico ante un error desconocido', () => {
    render(<EstadoError error={new Error('ReferenceError: x is not defined')} />)
    expect(screen.getByText('Ocurrió un error inesperado')).toBeInTheDocument()
    expect(screen.queryByText(/ReferenceError/)).not.toBeInTheDocument()
  })

  it('el botón reintentar avisa a quien lo montó', async () => {
    const reintentar = vi.fn<() => void>()
    render(<EstadoError error={new ErrorDeRed(null)} onRetry={reintentar} />)

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }))

    expect(reintentar).toHaveBeenCalledOnce()
  })
})
