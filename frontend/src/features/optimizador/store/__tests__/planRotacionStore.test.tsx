/**
 * El store del plan de rotaciones — F-036. GWT-2 (aceptar), GWT-3 (deshacer, LIFO) y GWT-4
 * (descartar sobrevive a aceptar/deshacer), más los derivados que el provider expone.
 */

import { act, renderHook } from '@testing-library/react'
import { createElement, type ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import type { Candidata } from '../../../../lib/rotaciones/esquemaRotaciones'
import { PlanRotacionProvider, usePlanRotacion, usePlanRotacionAcciones } from '../planRotacionStore'

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_rendimiento',
    segmento: 'usd_hard',
    origen: {
      ticker: origenTicker,
      emisor: 'X',
      rendimiento: 0.1,
      duracion: 3,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 100_000,
    },
    destino: {
      ticker: destinoTicker,
      emisor: 'X',
      rendimiento: 0.12,
      duracion: 4,
      moneda_cupon: 'USD',
      ley: null,
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 200_000,
    },
    delta: { rendimiento_pp: 2, duracion: 1 },
    flags: {
      mismo_emisor: false,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'nota',
    costo: null,
  }
}

function envolver(posiciones: { ticker: string; peso: number }[]) {
  return ({ children }: { children: ReactNode }) =>
    createElement(PlanRotacionProvider, { posiciones }, children)
}

function montar(posiciones: { ticker: string; peso: number }[]) {
  return renderHook(() => ({ plan: usePlanRotacion(), acciones: usePlanRotacionAcciones() }), {
    wrapper: envolver(posiciones),
  })
}

describe('PlanRotacionProvider', () => {
  it('arranca vacío, con la cartera acumulada igual a la original', () => {
    const originales = [{ ticker: 'A', peso: 100 }]
    const { result } = montar(originales)
    expect(result.current.plan.aceptadas).toEqual([])
    expect(result.current.plan.descartadas).toEqual([])
    expect(result.current.plan.posicionesAcumuladas).toEqual(originales)
    expect(result.current.plan.clavesExcluidas).toEqual(new Set())
  })

  it('aceptar mueve la cartera acumulada y agrega la candidata a la pila (GWT-2)', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }])
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    expect(result.current.plan.aceptadas).toEqual([candidata('A', 'B')])
    expect(result.current.plan.posicionesAcumuladas).toEqual([{ ticker: 'B', peso: 100 }])
  })

  it('aceptar la misma clave dos veces es un no-op', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }])
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    expect(result.current.plan.aceptadas).toHaveLength(1)
  })

  it('deshacer saca sólo la última y todo vuelve exacto (GWT-3, LIFO)', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }])
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    act(() => result.current.acciones.aceptar(candidata('B', 'C')))
    expect(result.current.plan.posicionesAcumuladas).toEqual([{ ticker: 'C', peso: 100 }])

    act(() => result.current.acciones.deshacerUltima())
    expect(result.current.plan.aceptadas).toEqual([candidata('A', 'B')])
    expect(result.current.plan.posicionesAcumuladas).toEqual([{ ticker: 'B', peso: 100 }])

    act(() => result.current.acciones.deshacerUltima())
    expect(result.current.plan.aceptadas).toEqual([])
    expect(result.current.plan.posicionesAcumuladas).toEqual([{ ticker: 'A', peso: 100 }])
  })

  it('deshacer con la pila vacía es un no-op', () => {
    const originales = [{ ticker: 'A', peso: 100 }]
    const { result } = montar(originales)
    act(() => result.current.acciones.deshacerUltima())
    expect(result.current.plan.posicionesAcumuladas).toEqual(originales)
  })

  it('descartar sobrevive a aceptar y deshacer, y no vuelve a proponerse (GWT-4)', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }, { ticker: 'C', peso: 50 }])
    act(() => result.current.acciones.descartar('C->D'))
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    act(() => result.current.acciones.deshacerUltima())
    expect(result.current.plan.descartadas).toEqual(['C->D'])
    expect(result.current.plan.clavesExcluidas.has('C->D')).toBe(true)
  })

  it('clavesExcluidas incluye la inversa de cada aceptada, para no proponer "deshacer" disfrazado', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }])
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    expect(result.current.plan.clavesExcluidas).toEqual(new Set(['B->A']))
  })

  it('deshacer saca del set de exclusión la inversa de lo deshecho', () => {
    const { result } = montar([{ ticker: 'A', peso: 100 }])
    act(() => result.current.acciones.aceptar(candidata('A', 'B')))
    act(() => result.current.acciones.deshacerUltima())
    expect(result.current.plan.clavesExcluidas).toEqual(new Set())
  })
})
