/**
 * El único lugar por donde el frontend habla con la API.
 *
 * Toda respuesta se valida contra su esquema antes de entrar a la aplicación. Si el backend
 * devuelve algo que no cumple el contrato, esto falla fuerte en vez de dejar pasar un objeto a
 * medias: mostrar la mitad de un dato financiero es peor que no mostrarlo.
 */

import type { z } from 'zod'

import { ApiError, ErrorDeRed } from './errors'
import { esquemaError } from './schemas'

// Vacío en desarrollo: el proxy de Vite resuelve /api contra el backend local. En producción se
// define VITE_API_URL en tiempo de build para el caso de dominios distintos.
const BASE = import.meta.env.VITE_API_URL ?? ''

/** Códigos para los fallos que no traen el contrato de error del backend. */
function codigoDeStatus(status: number): string {
  if (status === 401) return 'unauthorized'
  if (status === 403) return 'forbidden'
  if (status === 404) return 'not_found'
  if (status === 503) return 'service_unavailable'
  if (status >= 500) return 'internal_error'
  return 'request_error'
}

function mensajeDeStatus(status: number): string {
  if (status === 401) return 'La sesión no es válida o expiró'
  if (status === 403) return 'No tenés permiso para ver esto'
  if (status === 404) return 'No se encontró lo que se pidió'
  if (status === 503) return 'El servicio no está disponible en este momento'
  if (status >= 500) return 'El servicio tuvo un problema al procesar el pedido'
  return 'El pedido no pudo completarse'
}

async function comoApiError(respuesta: Response): Promise<ApiError> {
  let cuerpo: unknown = null
  try {
    cuerpo = await respuesta.json()
  } catch {
    // Cuerpo vacío o que no es JSON: se arma el error con el status y nada más.
  }

  // El camino feliz del error: el backend habla el contrato de errors.py.
  const contrato = esquemaError.safeParse(cuerpo)
  if (contrato.success) {
    const { code, message, details, request_id } = contrato.data.error
    return new ApiError({
      code,
      message,
      status: respuesta.status,
      details: details ?? null,
      requestId: request_id ?? null,
    })
  }

  // Hay respuestas de error que no usan ese shape —el 503 de /health devuelve el health mismo—,
  // así que el status es lo único confiable.
  return new ApiError({
    code: codigoDeStatus(respuesta.status),
    message: mensajeDeStatus(respuesta.status),
    status: respuesta.status,
    details: cuerpo,
    requestId: respuesta.headers.get('X-Request-ID'),
  })
}

/**
 * Hace la request y devuelve el cuerpo ya validado.
 *
 * Lanza `ApiError` si el backend respondió mal o si respondió algo que no cumple el esquema, y
 * `ErrorDeRed` si no respondió nada.
 */
export async function apiFetch<T>(
  ruta: string,
  esquema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  let respuesta: Response
  try {
    respuesta = await fetch(`${BASE}${ruta}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch (causa) {
    throw new ErrorDeRed(causa)
  }

  if (!respuesta.ok) throw await comoApiError(respuesta)

  let cuerpo: unknown
  try {
    cuerpo = await respuesta.json()
  } catch (causa) {
    throw new ApiError({
      code: 'contract_mismatch',
      message: 'El servicio devolvió una respuesta que no se pudo leer',
      status: respuesta.status,
      details: String(causa),
      requestId: respuesta.headers.get('X-Request-ID'),
    })
  }

  const parseado = esquema.safeParse(cuerpo)
  if (!parseado.success) {
    // Que el contrato no coincida es un bug del backend o del frontend, y se quiere ver ahora.
    throw new ApiError({
      code: 'contract_mismatch',
      message: 'El servicio devolvió datos con un formato inesperado',
      status: respuesta.status,
      details: parseado.error.issues,
      requestId: respuesta.headers.get('X-Request-ID'),
    })
  }

  return parseado.data
}
