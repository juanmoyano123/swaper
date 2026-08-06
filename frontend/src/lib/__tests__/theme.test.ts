/** Criterio 3: oscuro por defecto, y la preferencia sobrevive a la recarga. */

import { describe, expect, it } from 'vitest'

import { TEMA_STORAGE_KEY, aplicarTema, leerTema } from '../theme'

describe('tema', () => {
  it('arranca en oscuro cuando no hay preferencia guardada', () => {
    expect(leerTema()).toBe('dark')
  })

  it('no sigue al sistema operativo: el default es una decisión de producto', () => {
    // Sin nada guardado, leerTema() devuelve 'dark' aunque el SO esté en claro. Es a propósito:
    // la spec pide oscuro por defecto, no "lo que prefiera el sistema".
    localStorage.removeItem(TEMA_STORAGE_KEY)
    expect(leerTema()).toBe('dark')
  })

  it('al pasar a claro lo aplica al documento y lo persiste', () => {
    aplicarTema('light')

    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem(TEMA_STORAGE_KEY)).toBe('light')
    // Una lectura nueva simula la recarga de la página.
    expect(leerTema()).toBe('light')
  })

  it('vuelve a oscuro y también lo persiste', () => {
    aplicarTema('light')
    aplicarTema('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(leerTema()).toBe('dark')
  })
})
