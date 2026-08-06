/**
 * Criterio 2, primera mitad: cuando la API devuelve un error, el cliente lo traduce al contrato
 * en vez de dejar pasar un objeto a medias.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'
import { z } from 'zod'

import { apiFetch } from '../client'
import { ApiError, ErrorDeRed } from '../errors'

const esquema = z.object({ ok: z.boolean() })

function responderCon(cuerpo: unknown, status = 200, headers: Record<string, string> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify(cuerpo), {
          status,
          headers: { 'Content-Type': 'application/json', ...headers },
        }),
      ),
    ),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('apiFetch', () => {
  it('devuelve el cuerpo validado cuando la respuesta cumple el esquema', async () => {
    responderCon({ ok: true })
    await expect(apiFetch('/api/v1/x', esquema)).resolves.toEqual({ ok: true })
  })

  it('traduce el contrato de error del backend a ApiError', async () => {
    responderCon(
      {
        error: {
          code: 'validation_error',
          message: 'El monto tiene que ser mayor a cero',
          details: [{ field: 'monto', issue: 'greater_than' }],
          request_id: 'abc123',
        },
      },
      422,
    )

    const error = await apiFetch('/api/v1/x', esquema).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ApiError)
    const api = error as ApiError
    expect(api.code).toBe('validation_error')
    expect(api.message).toBe('El monto tiene que ser mayor a cero')
    expect(api.status).toBe(422)
    expect(api.requestId).toBe('abc123')
    expect(api.details).toEqual([{ field: 'monto', issue: 'greater_than' }])
  })

  it('deriva el código del status cuando el error no viene con el shape del contrato', async () => {
    // Caso real: /health devuelve su propio cuerpo con status 503, no el contrato de error.
    responderCon({ status: 'error', database: 'error' }, 503, { 'X-Request-ID': 'req-9' })

    const error = (await apiFetch('/api/v1/health', esquema).catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('service_unavailable')
    expect(error.status).toBe(503)
    expect(error.requestId).toBe('req-9')
  })

  it('falla fuerte si la respuesta 2xx no cumple el esquema', async () => {
    responderCon({ ok: 'no es un booleano' })

    const error = (await apiFetch('/api/v1/x', esquema).catch((e: unknown) => e)) as ApiError

    expect(error).toBeInstanceOf(ApiError)
    expect(error.code).toBe('contract_mismatch')
  })

  it('distingue el servicio caído de un error del servicio', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))

    const error = await apiFetch('/api/v1/x', esquema).catch((e: unknown) => e)

    expect(error).toBeInstanceOf(ErrorDeRed)
    expect((error as ErrorDeRed).message).toBe('No hay conexión con el servicio')
  })
})
