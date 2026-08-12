/**
 * Lee un archivo subido (`.csv`, `.xlsx` o `.xls`) y lo devuelve como grilla de texto, en el mismo
 * formato que produce `parsePegado` para el portapapeles — así todo lo que sigue (detección de
 * encabezado, mapeo, construcción de posiciones) es una sola ruta de código sin importar de dónde
 * vinieron las filas.
 *
 * `read-excel-file` se eligió por chico: no arrastra la librería completa de lectura/escritura de
 * planillas que traen paquetes como `xlsx`, solo el parser de `.xlsx`, y corre en el navegador sin
 * polyfills de Node.
 */

// El paquete no tiene entrada raíz: hay que elegir el build. `/browser` es el que no arrastra
// nada de `fs` ni de Buffer de Node, así que es el único que Vite puede empaquetar sin polyfills.
// `readSheet` (y no el export por default, que devuelve todas las hojas del archivo) porque acá
// solo interesa la primera hoja, que es donde viene la cartera.
import { readSheet } from 'read-excel-file/browser'

import { parseCsv } from './parseTabla'

function celdaComoTexto(celda: unknown): string {
  if (celda == null) return ''
  // Una fecha de Excel en formato ISO es al menos legible; nunca debería caer en las columnas de
  // ticker/nominal/monto, pero si pasa, mejor esto que "[object Object]".
  if (celda instanceof Date) return celda.toISOString().slice(0, 10)
  return String(celda)
}

export async function leerArchivo(archivo: File): Promise<string[][]> {
  const nombre = archivo.name.toLowerCase()

  if (nombre.endsWith('.csv') || archivo.type === 'text/csv') {
    const texto = await archivo.text()
    return parseCsv(texto)
  }

  if (nombre.endsWith('.xlsx') || nombre.endsWith('.xls')) {
    const filas = await readSheet(archivo)
    return filas.map((fila) => fila.map(celdaComoTexto))
  }

  throw new Error(`El formato de "${archivo.name}" no se reconoce. Subí un CSV o un Excel (.xlsx).`)
}
