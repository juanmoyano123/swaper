/**
 * Formato es-AR y, sobre todo, que un dato que falta no se vea como un cero.
 *
 * Es la regla del dominio con consecuencia visual más directa: un bono sin TIR informada y un bono
 * con TIR cero son cosas distintas, y confundirlas en una grilla lleva a comprar el papel
 * equivocado.
 */

import { describe, expect, it } from 'vitest'

import {
  NO_APLICA,
  SIN_DATO,
  fmtCompacto,
  fmtFecha,
  fmtFechaHora,
  fmtMonto,
  fmtNumero,
  fmtPct,
} from '../fmt'

describe('formato es-AR', () => {
  it('usa coma decimal y punto de miles en los montos', () => {
    expect(fmtMonto(5264.5)).toBe('US$ 5.264,50')
    expect(fmtMonto(88400, 'ars', 0)).toBe('$ 88.400')
  })

  it('formatea porcentajes con coma', () => {
    expect(fmtPct(7.27)).toBe('7,27%')
    expect(fmtPct(7.3, 1)).toBe('7,3%')
  })

  it('compacta los volúmenes grandes', () => {
    expect(fmtCompacto(12_900_000)).toBe('12,9 MM')
    expect(fmtCompacto(4300)).toBe('4,3 M')
  })

  it('formatea fechas con el año completo', () => {
    // Año de cuatro dígitos: con vencimientos a 2029 y a 2038 en la misma grilla, "38" es ambiguo.
    expect(fmtFecha('2026-08-06')).toBe('06/08/2026')
  })

  it('no corre la fecha un día para atrás por la zona horaria', () => {
    // `new Date('2026-08-06')` es medianoche UTC, o sea el 5 de agosto a las 21:00 en Argentina.
    // Un vencimiento o un pago de cupón mostrado un día antes del real es un error de negocio.
    expect(fmtFecha('2026-01-01')).toBe('01/01/2026')
    expect(fmtFecha('2026-12-31')).toBe('31/12/2026')
  })

  it('escribe las horas en 24 y sin a. m. / p. m.', () => {
    // La barra de estado del dato declara la hora del snapshot, y se la compara contra horarios de
    // mercado que siempre se dicen en 24 horas: la rueda abre 11:00, la corrida matinal es 11:30.
    expect(fmtFechaHora(new Date(2026, 7, 6, 16, 24))).toBe('06/08/2026, 16:24')
    expect(fmtFechaHora(new Date(2026, 7, 6, 9, 5))).toBe('06/08/2026, 09:05')
  })
})

describe('dato faltante', () => {
  it('un dato ausente se muestra como s/d, nunca como cero', () => {
    expect(fmtPct(null)).toBe(SIN_DATO)
    expect(fmtMonto(undefined)).toBe(SIN_DATO)
    expect(fmtNumero(null)).toBe(SIN_DATO)
    expect(fmtCompacto(null)).toBe(SIN_DATO)
    expect(fmtFecha(null)).toBe(SIN_DATO)
  })

  it('cero es un valor y se muestra como tal', () => {
    expect(fmtPct(0)).toBe('0,00%')
    expect(fmtMonto(0)).toBe('US$ 0,00')
    expect(fmtPct(0)).not.toBe(SIN_DATO)
  })

  it('NaN cuenta como dato ausente y no imprime NaN en pantalla', () => {
    expect(fmtNumero(Number.NaN)).toBe(SIN_DATO)
  })

  it('"no aplica" es distinto de "sin dato"', () => {
    // Una acción no tiene TIR: eso no es un dato que falta, es una magnitud que no existe.
    expect(NO_APLICA).not.toBe(SIN_DATO)
  })

  it('una fecha inválida no se muestra como Invalid Date', () => {
    expect(fmtFecha('cualquier cosa')).toBe(SIN_DATO)
  })
})
