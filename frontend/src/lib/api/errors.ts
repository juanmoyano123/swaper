/**
 * Los dos modos en que una consulta puede fallar, como clases distintas.
 *
 * "El servicio respondió con un error" y "el servicio no respondió" son estados diferentes para el
 * usuario —uno se reintenta solo, el otro no— y mezclarlos obligaría a cada vista a adivinar cuál
 * está viendo.
 */

/** El backend respondió, y lo que dijo es que algo salió mal. */
export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details: unknown
  /** Identificador del request en los logs del backend. Se le muestra al usuario para soporte. */
  readonly requestId: string | null

  constructor(args: {
    code: string
    message: string
    status: number
    details?: unknown
    requestId?: string | null
  }) {
    super(args.message)
    this.name = 'ApiError'
    this.code = args.code
    this.status = args.status
    this.details = args.details ?? null
    this.requestId = args.requestId ?? null
  }
}

/** El backend no contestó: está caído, no hay red, o la conexión se cortó a mitad de camino. */
export class ErrorDeRed extends Error {
  readonly causa: unknown

  constructor(causa: unknown) {
    super('No hay conexión con el servicio')
    this.name = 'ErrorDeRed'
    this.causa = causa
  }
}

/**
 * Qué se le muestra a la persona que está usando la app.
 *
 * Para un ApiError se usa el mensaje del contrato tal como lo escribió el backend: es el único que
 * sabe qué pasó. Para cualquier otra cosa hay un texto fijo, porque el `message` de un error
 * inesperado suele ser jerga técnica que no le dice nada a un asesor.
 */
export function mensajeParaUsuario(error: unknown): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof ErrorDeRed) return error.message
  return 'Ocurrió un error inesperado'
}

/** Un 4xx es determinístico: reintentarlo da el mismo resultado y solo gasta tiempo. */
export function vale_reintentar(error: unknown): boolean {
  if (error instanceof ErrorDeRed) return true
  if (error instanceof ApiError) return error.status >= 500
  return false
}
