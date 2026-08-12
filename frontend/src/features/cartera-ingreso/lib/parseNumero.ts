/**
 * Interpreta un número tal como puede venir escrito en un resumen de cuenta argentino: con coma
 * decimal y punto de miles ("1.234.567,89"), pero también en formato en-US si el archivo salió de
 * un Excel con esa configuración regional ("1,234,567.89"), o directo, sin separador de miles.
 *
 * No es una adivinanza: cuando el formato es genuinamente ambiguo (por ejemplo "1.234" podría ser
 * mil doscientos treinta y cuatro o uno con veintitrés centésimos) se resuelve con una regla fija
 * y documentada, no con una heurística estadística. Cuando el texto no es un número en ningún
 * formato razonable, se devuelve `null`: la regla del dominio es dejar el dato vacío y alertar, no
 * inventarlo.
 */
export function parseNumeroArg(texto: string): number | null {
  if (texto == null) return null

  // Símbolos de moneda y espacios (incluido el NBSP que copian algunas planillas) no son parte del
  // número. El signo negativo entre paréntesis, sí — es una convención contable habitual.
  let limpio = texto
    .trim()
    .replace(/^u\$s\s*/i, '')
    .replace(/^(us\$|ars\$|\$)\s*/i, '')
    .replace(/[\s ]/g, '')

  if (limpio === '') return null

  let negativo = false
  const entreParentesis = /^\((.+)\)$/.exec(limpio)
  if (entreParentesis) {
    negativo = true
    limpio = entreParentesis[1]
  }
  if (limpio.startsWith('-')) {
    negativo = true
    limpio = limpio.slice(1)
  } else if (limpio.startsWith('+')) {
    limpio = limpio.slice(1)
  }

  if (!/^[0-9.,]+$/.test(limpio)) return null

  const tieneComa = limpio.includes(',')
  const tienePunto = limpio.includes('.')

  let normalizado: string
  if (tieneComa && tienePunto) {
    // Los dos separadores aparecen: el que está más a la derecha es el decimal, el otro es de
    // miles y se descarta.
    const ultimaComa = limpio.lastIndexOf(',')
    const ultimoPunto = limpio.lastIndexOf('.')
    if (ultimaComa > ultimoPunto) {
      normalizado = limpio.replace(/\./g, '').replace(',', '.')
    } else {
      normalizado = limpio.replace(/,/g, '')
    }
  } else if (tieneComa) {
    // Solo coma: convención argentina, es el separador decimal.
    normalizado = limpio.replace(',', '.')
  } else if (tienePunto) {
    // Solo punto. Con exactamente tres dígitos después del último punto y más de un grupo posible
    // de miles, es separador de miles ("1.234" → 1234, "12.345.678" → 12345678). Con una cantidad
    // de dígitos distinta de tres, es separador decimal ("1234.5", "1234.56").
    const grupos = limpio.split('.')
    const pareceMiles =
      grupos.length > 1 && grupos.slice(1).every((g) => g.length === 3) && grupos[0].length <= 3
    normalizado = pareceMiles ? limpio.replace(/\./g, '') : limpio
  } else {
    normalizado = limpio
  }

  if (normalizado === '' || normalizado === '.') return null

  const valor = Number(normalizado)
  if (!Number.isFinite(valor)) return null

  return negativo ? -valor : valor
}
