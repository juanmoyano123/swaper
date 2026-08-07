/**
 * La jerarquía visual — F-013.
 *
 * Lo que se prueba es el criterio de producto, no el CSS: que sólo el error lleve el color negativo
 * y que el resumen de una línea no invente ceros. Una barra que grita en rojo todo el tiempo se
 * vuelve invisible en una semana, y en este dominio la mayoría de las alertas son hechos ciertos y
 * permanentes sobre el dato.
 */

import { describe, expect, it } from 'vitest'

import { ORDEN, colorDe, nombreDe, resumirConteos } from '../lib/severidad'

describe('el color de cada severidad', () => {
  it('reserva el color negativo para el error y sólo para él', () => {
    expect(colorDe('error')).toBe('var(--neg)')
    expect(colorDe('advertencia')).toBe('var(--ac2)')
    expect(colorDe('info')).toBe('var(--dim)')
  })

  it('sin alertas el punto va en positivo y no en gris', () => {
    // "No hay nada que declarar" es un estado, no la ausencia de uno: gris lo haría
    // indistinguible de "todavía no cargó".
    expect(colorDe(null)).toBe('var(--pos)')
  })
})

describe('el orden de urgencia', () => {
  it('pone el error primero y la información última', () => {
    // El orden alfabético de los valores es advertencia, error, info: casi el inverso.
    expect(ORDEN).toEqual(['error', 'advertencia', 'info'])
  })
})

describe('el resumen de una línea', () => {
  it('nombra los niveles presentes de mayor a menor urgencia', () => {
    expect(resumirConteos({ info: 2, advertencia: 4, error: 1 })).toBe(
      '1 error · 4 advertencias · 2 información',
    )
  })

  it('omite los niveles vacíos en vez de escribir un cero', () => {
    // Un cero acá ocupa el lugar de algo que sí pasa. Es distinto del cero de un monto, donde el
    // cero es el dato.
    expect(resumirConteos({ error: 0, advertencia: 3, info: 0 })).toBe('3 advertencias')
  })

  it('dice "sin alertas" cuando no hay ninguna', () => {
    expect(resumirConteos({})).toBe('sin alertas')
  })

  it('concuerda en singular', () => {
    expect(resumirConteos({ advertencia: 1 })).toBe('1 advertencia')
    expect(resumirConteos({ info: 1 })).toBe('1 aviso')
  })
})

describe('el nombre de cada nivel', () => {
  it('está en español', () => {
    expect(nombreDe('error')).toBe('errores')
    expect(nombreDe('advertencia')).toBe('advertencias')
  })
})
