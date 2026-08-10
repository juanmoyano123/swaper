/**
 * F-042 — genera el `.xlsx` a partir de las hojas puras de `hojasExcel.ts`. `write-excel-file` se
 * importa recién acá, con `import()` dinámico: Vite lo corta en un chunk propio, así que abrir
 * cualquier otra pantalla no paga el costo de la librería.
 *
 * Se usa `write-excel-file/browser` — mismo criterio que `read-excel-file/browser` (F-005): el
 * paquete no tiene un entrypoint por defecto, y el build de browser es el que corresponde acá.
 */

import { hojasDesdeModelo, type CeldaExcel } from './hojasExcel'
import type { ModeloExport } from './modelo'

function tipoDeCelda(celda: CeldaExcel): StringConstructor | NumberConstructor | DateConstructor {
  if (celda.tipo === 'numero') return Number
  if (celda.tipo === 'fecha') return Date
  return String
}

export async function generarExcel(modelo: ModeloExport): Promise<Blob> {
  const { default: writeXlsxFile } = await import('write-excel-file/browser')

  const hojas = hojasDesdeModelo(modelo)
  const resultado = await writeXlsxFile(
    hojas.map((hoja) => ({
      sheet: hoja.nombre,
      stickyRowsCount: hoja.filasFijas,
      columns: hoja.anchoDeColumnas?.map((width) => ({ width })),
      data: hoja.filas.map((fila) =>
        fila.map((celda) => ({
          value: celda.valor,
          type: tipoDeCelda(celda),
          ...(celda.formato ? { format: celda.formato } : {}),
        })),
      ),
    })),
  )

  return resultado.toBlob()
}
