/**
 * Formateo de números en es-AR y, sobre todo, la distinción entre las tres cosas que una celda
 * vacía puede significar.
 *
 * Un dato que falta se muestra faltante: nunca se estima, nunca se rellena con cero, nunca queda
 * la celda muda. `s/d` y `0` son estados distintos y no pueden verse iguales — un bono que no
 * cotiza no es un bono que cotiza a cero.
 */

/** El dato no está. Distinto de cero y distinto de no aplicable. */
export const SIN_DATO = 's/d'

/** La magnitud no existe para este instrumento: una acción no tiene TIR. No es un faltante. */
export const NO_APLICA = 'no aplica'

type Numerico = number | null | undefined

/** `null`, `undefined` y `NaN` son lo mismo para la vista: no hay dato que mostrar. */
function falta(valor: Numerico): valor is null | undefined {
  return valor === null || valor === undefined || Number.isNaN(valor)
}

const decimal = (min: number, max: number) =>
  new Intl.NumberFormat('es-AR', { minimumFractionDigits: min, maximumFractionDigits: max })

const NUMERO_2 = decimal(2, 2)
const NUMERO_0 = decimal(0, 0)
const COMPACTO = decimal(1, 1)

/**
 * Convierte a Date respetando el huso local.
 *
 * `new Date('2026-08-06')` se interpreta como medianoche UTC, que en Argentina es el 5 de agosto a
 * las 21:00: un vencimiento o un pago de cupón se mostraría un día antes del que es. Las fechas sin
 * hora que devuelve la API (maturity, payment_date, issue_date) se construyen componente por
 * componente para que el día sea el que dice el dato.
 */
function aFecha(valor: string | Date): Date {
  if (valor instanceof Date) return valor

  const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor)
  if (soloFecha) {
    const [, anio, mes, dia] = soloFecha
    return new Date(Number(anio), Number(mes) - 1, Number(dia))
  }

  // Con hora y zona explícitas, el parseo nativo es correcto.
  return new Date(valor)
}

/** Número suelto con coma decimal y punto de miles. */
export function fmtNumero(valor: Numerico, decimales = 2): string {
  if (falta(valor)) return SIN_DATO
  return decimal(decimales, decimales).format(valor)
}

/** Monto con su símbolo de moneda. Los montos de flujo mensual van sin decimales. */
export function fmtMonto(valor: Numerico, moneda: 'usd' | 'ars' = 'usd', decimales = 2): string {
  if (falta(valor)) return SIN_DATO
  const simbolo = moneda === 'usd' ? 'US$' : '$'
  const numero = decimales === 0 ? NUMERO_0.format(valor) : NUMERO_2.format(valor)
  return `${simbolo} ${numero}`
}

/**
 * Porcentaje ya expresado en puntos (7.27 → "7,27%").
 *
 * No recibe ni imprime la unidad del rendimiento a propósito: una TIR en dólares, una tasa real
 * sobre CER y una TNA en pesos se formatean igual pero no significan lo mismo, y el rótulo que las
 * distingue lo pone la vista al lado del número. Un formateador que "supiera" la unidad invitaría
 * a compararlas.
 */
export function fmtPct(valor: Numerico, decimales = 2): string {
  if (falta(valor)) return SIN_DATO
  // Cantidad fija de decimales: en una columna, "7,3%" junto a "7,27%" se lee mal y se compara peor.
  return `${decimal(decimales, decimales).format(valor)}%`
}

/** Volúmenes grandes: 12.900.000 → "12,9 MM". */
export function fmtCompacto(valor: Numerico): string {
  if (falta(valor)) return SIN_DATO
  const abs = Math.abs(valor)
  if (abs >= 1_000_000) return `${COMPACTO.format(valor / 1_000_000)} MM`
  if (abs >= 1_000) return `${COMPACTO.format(valor / 1_000)} M`
  return NUMERO_0.format(valor)
}

// Año completo y no `dateStyle: 'short'`, que en es-AR abrevia a dos dígitos: con vencimientos a
// 2029 y a 2038 conviviendo en la misma grilla, "38" es ambiguo de más.
const FECHA = new Intl.DateTimeFormat('es-AR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

// `hour12: false` explícito: sin él, el ICU de Node formatea es-AR como "11:02 a. m.", y este
// dominio habla en 24 horas de punta a punta —la rueda abre 11:00, la corrida matinal es a las
// 11:30, la barra de estado del dato declara la hora del snapshot—. Una hora con sufijo obliga a
// traducirla mentalmente cada vez que se la compara con un horario de mercado.
const FECHA_HORA = new Intl.DateTimeFormat('es-AR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** Fecha dd/mm/aaaa. Acepta el ISO que devuelve la API. */
export function fmtFecha(valor: string | Date | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return SIN_DATO
  const fecha = aFecha(valor)
  if (Number.isNaN(fecha.getTime())) return SIN_DATO
  return FECHA.format(fecha)
}

/** Fecha con hora, para la barra de estado del dato (F-013) y el último refresh. */
export function fmtFechaHora(valor: string | Date | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return SIN_DATO
  const fecha = aFecha(valor)
  if (Number.isNaN(fecha.getTime())) return SIN_DATO
  return FECHA_HORA.format(fecha)
}
