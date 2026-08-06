/**
 * El contrato de salida de F-028: una lista de posiciones crudas, lista para que F-029 resuelva
 * cada ticker contra el universo.
 *
 * A propósito NO hay acá ningún campo de instrumento, especie ni moneda resuelta — eso es trabajo
 * de F-029. Esta feature solo declara lo que el cliente escribió o pegó, tal como lo escribió.
 */

/** Las tres puertas de entrada del Flujo B. */
export type ViaIngreso = 'portapapeles' | 'archivo' | 'manual'

/**
 * Una posición tal como se leyó, antes de resolver el ticker.
 *
 * `nominal` y `monto` son casilleros independientes: un resumen de cuenta puede traer uno, el
 * otro, o los dos. Alcanza con que uno de los dos sea un número válido para que la fila sea válida.
 * Si vino un valor no numérico en cualquiera de los dos, la fila se marca inválida — nunca se
 * completa con cero ni se descarta en silencio.
 */
export interface PosicionCruda {
  /** Identificador de fila para la key de React y para referenciar el error en la previsualización. */
  id: string
  /** Número de fila de origen (1-based, contando encabezado si lo hubo), para que el asesor la ubique. */
  fila: number
  /** Tal como vino. Nunca se normaliza, nunca se deriva de otro campo. */
  tickerDeclarado: string
  nominal: number | null
  monto: number | null
  valida: boolean
  /** Por qué la fila es inválida. `null` cuando `valida` es `true`. */
  motivo: string | null
}

/** A qué campo del dominio corresponde cada columna de la tabla de origen. */
export type CampoPosicion = 'ticker' | 'nominal' | 'monto' | 'ignorar'

/**
 * El mapeo columna → campo, ya sea detectado por encabezado conocido o elegido a mano por el
 * asesor cuando el sistema no pudo inferirlo.
 *
 * Es un array porque el orden de las columnas de origen importa para volver a leer las filas; el
 * índice del array es el índice de columna.
 */
export type MapeoColumnas = CampoPosicion[]

/** Una tabla cruda, todavía sin interpretar: puede o no traer encabezado reconocible. */
export interface TablaCruda {
  /** `null` cuando no se pudo reconocer un encabezado con las columnas esperadas. */
  encabezados: string[] | null
  /** Las filas de datos, sin la fila de encabezado si la hubo. */
  filas: string[][]
}
