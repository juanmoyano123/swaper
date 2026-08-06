/**
 * Divide texto plano en una grilla de filas y columnas, tolerando los separadores con los que
 * puede llegar un resumen de cuenta: tabulador (lo más común al pegar desde una tabla de un
 * navegador o de Excel), punto y coma, barra vertical, o columnas alineadas con espacios.
 *
 * La coma se descarta a propósito como separador de columnas: en un resumen en español es casi
 * siempre el separador decimal ("1.234,56"), y tratarla como separador de columnas rompería todos
 * los montos. Un CSV real que use coma como delimitador se reconoce aparte, en `parseCsv`, porque
 * ahí el delimitador viene declarado por el formato del archivo y no hay que adivinarlo del texto.
 */

function dividirLineas(texto: string): string[] {
  return texto
    .split(/\r\n|\r|\n/)
    .map((linea) => linea.trimEnd())
    .filter((linea) => linea.trim() !== '')
}

const SEPARADORES_SIN_AMBIGUEDAD = ['\t', ';', '|'] as const

/** Cuál separador aparece en la mayoría de las líneas de la muestra, en orden de preferencia. */
function detectarSeparadorPegado(lineas: string[]): string {
  for (const candidato of SEPARADORES_SIN_AMBIGUEDAD) {
    const conSeparador = lineas.filter((l) => l.includes(candidato)).length
    if (conSeparador >= Math.ceil(lineas.length / 2)) return candidato
  }
  // Sin tabulador, punto y coma ni barra: texto alineado a mano, con dos o más espacios entre
  // columnas (un espacio simple es parte de "Bono Argentina 2035" y no separa nada).
  return '  '
}

/** Pegado desde el portapapeles: texto plano, sin comillas que escapen el separador. */
export function parsePegado(texto: string): string[][] {
  const lineas = dividirLineas(texto)
  if (lineas.length === 0) return []

  const separador = detectarSeparadorPegado(lineas)
  const patron = separador === '  ' ? /\s{2,}/ : separador

  return lineas.map((linea) => linea.split(patron).map((celda) => celda.trim()))
}

/** Una línea de CSV respetando comillas: una coma o punto y coma adentro de comillas no separa. */
function parseLineaCsv(linea: string, delimitador: string): string[] {
  const celdas: string[] = []
  let actual = ''
  let entreComillas = false

  for (let i = 0; i < linea.length; i++) {
    const c = linea[i]

    if (entreComillas) {
      if (c === '"') {
        if (linea[i + 1] === '"') {
          actual += '"'
          i++
        } else {
          entreComillas = false
        }
      } else {
        actual += c
      }
      continue
    }

    if (c === '"') {
      entreComillas = true
    } else if (c === delimitador) {
      celdas.push(actual.trim())
      actual = ''
    } else {
      actual += c
    }
  }
  celdas.push(actual.trim())
  return celdas
}

/** El punto y coma es el delimitador habitual de un CSV exportado con configuración regional
 *  argentina, porque la coma la usa el número. Se elige por conteo en la primera línea. */
function detectarDelimitadorCsv(primeraLinea: string): string {
  const puntoYComa = (primeraLinea.match(/;/g) ?? []).length
  const coma = (primeraLinea.match(/,/g) ?? []).length
  return puntoYComa >= coma ? ';' : ','
}

/** Archivo `.csv` subido: sigue el formato RFC 4180 (comillas para escapar el delimitador). */
export function parseCsv(texto: string): string[][] {
  const lineas = dividirLineas(texto)
  if (lineas.length === 0) return []

  const delimitador = detectarDelimitadorCsv(lineas[0])
  return lineas.map((linea) => parseLineaCsv(linea, delimitador))
}
