/**
 * Qué se le manda al backend y qué se hace con lo que contesta.
 *
 * El punto que se cuida acá: **se mandan todas las posiciones**, también las que F-028 marcó
 * inválidas. Filtrarlas del pedido las sacaría del diagnóstico de cobertura, y una fila que no se
 * pudo leer sigue siendo plata del cliente.
 */

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/lib/supabase', () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: null } }) } },
}))

import type { PosicionCruda } from '@/features/cartera-ingreso/types'
import { ApiError } from '@/lib/api/errors'

import { RUTA_RESOLVER, firmaDeCartera, resolverCartera } from '../lib/resolverCartera'

afterEach(() => {
  vi.unstubAllGlobals()
})

const VALIDA: PosicionCruda = {
  id: 'p1',
  fila: 1,
  tickerDeclarado: 'AL30D',
  nominal: null,
  monto: 1000,
  valida: true,
  motivo: null,
}

const INVALIDA: PosicionCruda = {
  id: 'p2',
  fila: 2,
  tickerDeclarado: 'GD35',
  nominal: null,
  monto: null,
  valida: false,
  motivo: 'El nominal no es un número',
}

function COBERTURA_VACIA() {
  return {
    posiciones: 0,
    resueltas: 0,
    no_resueltas: 0,
    posiciones_con_monto: 0,
    posiciones_sin_monto: 0,
    posiciones_sin_monto_no_resueltas: 0,
    monto_declarado: 0,
    monto_no_resuelto: 0,
    porcentaje_no_resuelto: null,
  }
}

const RESPUESTA_VACIA = { posiciones: [], cobertura: COBERTURA_VACIA(), alertas: [] }

function espiarFetch(cuerpo: unknown = RESPUESTA_VACIA, status = 200) {
  const fetchMock = vi.fn(() =>
    Promise.resolve(
      new Response(JSON.stringify(cuerpo), {
        status,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function cuerpoEnviado(fetchMock: ReturnType<typeof espiarFetch>) {
  const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  return JSON.parse(String(init.body))
}

describe('resolverCartera', () => {
  it('manda las posiciones al endpoint de resolución, por POST y en el cuerpo', async () => {
    const fetchMock = espiarFetch()

    await resolverCartera([VALIDA])

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe(RUTA_RESOLVER)
    expect(init.method).toBe('POST')
    // Las tenencias del cliente no viajan en la URL: una query string se persiste en los logs de
    // acceso y en el historial del navegador.
    expect(url).not.toContain('AL30D')
  })

  it('manda también las filas que F-028 marcó inválidas', async () => {
    const fetchMock = espiarFetch()

    await resolverCartera([VALIDA, INVALIDA])

    const enviado = cuerpoEnviado(fetchMock)
    expect(enviado.posiciones).toHaveLength(2)
    expect(enviado.posiciones[1].ticker_declarado).toBe('GD35')
  })

  it('manda el ticker declarado tal como se escribió y no lo normaliza en el cliente', async () => {
    const fetchMock = espiarFetch()

    await resolverCartera([{ ...VALIDA, tickerDeclarado: '  al30 ' }])

    expect(cuerpoEnviado(fetchMock).posiciones[0].ticker_declarado).toBe('  al30 ')
  })

  it('manda el monto faltante como null y nunca como cero', async () => {
    const fetchMock = espiarFetch()

    await resolverCartera([INVALIDA])

    const posicion = cuerpoEnviado(fetchMock).posiciones[0]
    expect(posicion.monto).toBeNull()
    expect(posicion.nominal).toBeNull()
  })

  it('no manda el veredicto de formato de F-028: no es asunto de la resolución', async () => {
    const fetchMock = espiarFetch()

    await resolverCartera([INVALIDA])

    const posicion = cuerpoEnviado(fetchMock).posiciones[0]
    expect(posicion).not.toHaveProperty('valida')
    expect(posicion).not.toHaveProperty('motivo')
  })

  it('falla fuerte si el backend devuelve algo que no cumple el contrato', async () => {
    espiarFetch({ posiciones: [{ id: 'p1' }], cobertura: COBERTURA_VACIA(), alertas: [] })

    await expect(resolverCartera([VALIDA])).rejects.toBeInstanceOf(ApiError)
  })
})

describe('firmaDeCartera', () => {
  it('distingue dos carteras que difieren en un monto', () => {
    expect(firmaDeCartera([VALIDA])).not.toBe(firmaDeCartera([{ ...VALIDA, monto: 2000 }]))
  })

  it('no confunde un monto ausente con un cero', () => {
    expect(firmaDeCartera([{ ...VALIDA, monto: null }])).not.toBe(
      firmaDeCartera([{ ...VALIDA, monto: 0 }]),
    )
  })
})
