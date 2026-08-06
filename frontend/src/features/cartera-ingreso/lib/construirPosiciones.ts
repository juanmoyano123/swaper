/**
 * Convierte filas crudas + un mapeo de columnas en la lista de posiciones que consume F-029.
 *
 * Acá se aplica la regla central de la feature: un valor no numérico en el nominal o el monto no
 * se descarta ni se interpreta como cero, se conserva la fila con `valida: false` y el motivo
 * exacto. `esquemaPosicionCruda.parse` al final de cada fila es la última barrera — si esta función
 * tuviera un bug que produjera, por ejemplo, un `NaN` en vez de `null`, se corta acá con una
 * excepción en vez de dejarlo pasar como si fuera un dato real.
 */

import { parseNumeroArg } from './parseNumero'
import { esquemaPosicionCruda } from './schemas'
import type { MapeoColumnas, PosicionCruda } from '../types'

/**
 * @param filas Filas de datos (sin encabezado).
 * @param mapeo Qué campo del dominio es cada columna. Se asume ya validado con `mapeoCompleto`.
 * @param offsetFila Número de fila de origen de la primera fila de `filas`, para que el motivo de
 *   error señale la fila real (contando el encabezado, si lo hubo).
 */
export function construirPosiciones(
  filas: string[][],
  mapeo: MapeoColumnas,
  offsetFila: number,
): PosicionCruda[] {
  const idxTicker = mapeo.indexOf('ticker')
  const idxNominal = mapeo.indexOf('nominal')
  const idxMonto = mapeo.indexOf('monto')

  return filas.map((celdas, i) => {
    const tickerDeclarado = (celdas[idxTicker] ?? '').trim()
    const nominalTexto = (idxNominal >= 0 ? celdas[idxNominal] : undefined)?.trim() ?? ''
    const montoTexto = (idxMonto >= 0 ? celdas[idxMonto] : undefined)?.trim() ?? ''

    const nominal = nominalTexto === '' ? null : parseNumeroArg(nominalTexto)
    const monto = montoTexto === '' ? null : parseNumeroArg(montoTexto)

    const motivos: string[] = []
    if (tickerDeclarado === '') motivos.push('falta el ticker')
    if (nominalTexto !== '' && nominal === null) {
      motivos.push(`el nominal "${nominalTexto}" no es un número`)
    }
    if (montoTexto !== '' && monto === null) {
      motivos.push(`el monto "${montoTexto}" no es un número`)
    }
    if (nominal === null && monto === null && nominalTexto === '' && montoTexto === '') {
      motivos.push('no trae nominal ni monto')
    }

    const valida = motivos.length === 0

    return esquemaPosicionCruda.parse({
      // Determinístico y único dentro de la tabla: alcanza para la key de React y no depende de
      // que el entorno tenga `crypto.randomUUID` (no todos los runtimes de test lo dan por hecho).
      id: `pos-${offsetFila + i}`,
      fila: offsetFila + i,
      tickerDeclarado,
      nominal,
      monto,
      valida,
      motivo: valida ? null : motivos.join('; '),
    } satisfies PosicionCruda)
  })
}
