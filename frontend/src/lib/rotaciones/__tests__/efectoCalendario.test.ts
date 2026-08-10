/**
 * GWT-1 de F-036 (`plan.md:1708`): qué mes se llena y qué mes se vacía si se acepta una rotación,
 * moneda por moneda, sin sumar entre monedas (regla 3) y declarando cuando una punta no tiene
 * cronograma calculable (regla 1).
 */

import { describe, expect, it } from 'vitest'

import type { AlertaCalendario, CalendarioUniverso, MesDelCalendario } from '../../cartera/esquemaCalendario'
import { diffCalendario } from '../efectoCalendario'
import type { Candidata } from '../esquemaRotaciones'

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

function mes(etiqueta: string, renta: Record<string, number>): MesDelCalendario {
  return {
    anio: 2026,
    mes: 9,
    etiqueta,
    nombre: etiqueta,
    con_renta: Object.values(renta).some((v) => v > 0) ? 1 : 0,
    con_amortizacion: 0,
    sin_renta: Object.values(renta).every((v) => v === 0),
    renta,
    amortizacion: { usd: 0, ars: 0 },
    instrumentos: [],
  }
}

function calendario(overrides: {
  meses: MesDelCalendario[]
  monedas?: string[]
  alertas?: AlertaCalendario[]
  con_montos?: boolean
}): CalendarioUniverso {
  return {
    resumen: {
      hoy: '2026-08-10',
      desde: '2026-08-10',
      hasta: '2027-07-10',
      con_montos: overrides.con_montos ?? true,
      monedas: overrides.monedas ?? ['usd', 'ars'],
      instrumentos: 1,
      meses_sin_renta: [],
      renta_anual: { usd: 0, ars: 0 },
      amortizacion_anual: { usd: 0, ars: 0 },
      pendientes_este_mes: 0,
      flujos: { evaluados: 1, con_flujos: 1, pagos: 1, sin_cronograma: 0, sin_paridad: 0, sin_paridad_que_cotizan: 0, vencidos: 0 },
    },
    meses: overrides.meses,
    alertas: overrides.alertas ?? [],
  }
}

const DOS_MESES_ACTUAL = [mes('2026-09', { usd: 100, ars: 0 }), mes('2026-10', { usd: 0, ars: 0 })]

describe('diffCalendario', () => {
  it('declara que un mes se llena cuando la renta pasa de cero a positivo, por moneda', () => {
    const actual = calendario({ meses: DOS_MESES_ACTUAL })
    const simulado = calendario({
      meses: [mes('2026-09', { usd: 100, ars: 0 }), mes('2026-10', { usd: 50, ars: 0 })],
    })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.calculable).toBe(true)
    expect(efecto.seLlenan).toEqual([{ etiqueta: '2026-10', nombre: '2026-10', moneda: 'usd' }])
    expect(efecto.seVacian).toEqual([])
  })

  it('declara que un mes se vacía cuando la renta pasa de positivo a cero', () => {
    const actual = calendario({ meses: DOS_MESES_ACTUAL })
    const simulado = calendario({ meses: [mes('2026-09', { usd: 0, ars: 0 }), mes('2026-10', { usd: 0, ars: 0 })] })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.seVacian).toEqual([{ etiqueta: '2026-09', nombre: '2026-09', moneda: 'usd' }])
    expect(efecto.seLlenan).toEqual([])
  })

  it('un mismo mes puede llenarse en una moneda y vaciarse en otra, y nunca se suman', () => {
    const actual = calendario({ meses: [mes('2026-09', { usd: 100, ars: 0 })] })
    const simulado = calendario({ meses: [mes('2026-09', { usd: 0, ars: 500 })] })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.seLlenan).toEqual([{ etiqueta: '2026-09', nombre: '2026-09', moneda: 'ars' }])
    expect(efecto.seVacian).toEqual([{ etiqueta: '2026-09', nombre: '2026-09', moneda: 'usd' }])
  })

  it('un cambio de monto sin cruzar cero sólo se cuenta, no se detalla', () => {
    const actual = calendario({ meses: [mes('2026-09', { usd: 100, ars: 0 })] })
    const simulado = calendario({ meses: [mes('2026-09', { usd: 150, ars: 0 })] })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.seLlenan).toEqual([])
    expect(efecto.seVacian).toEqual([])
    expect(efecto.mesesQueCambian).toBe(1)
  })

  it('meses sin cambios no se declaran de ninguna forma', () => {
    const actual = calendario({ meses: [mes('2026-09', { usd: 100, ars: 0 })] })
    const simulado = calendario({ meses: [mes('2026-09', { usd: 100, ars: 0 })] })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto).toEqual({ calculable: true, motivoNoCalculable: null, seLlenan: [], seVacian: [], mesesQueCambian: 0 })
  })

  it('no calculable si el destino tiene la alerta posicion_sin_calendario, y nombra el ticker', () => {
    const actual = calendario({ meses: DOS_MESES_ACTUAL })
    const simulado = calendario({
      meses: DOS_MESES_ACTUAL,
      alertas: [
        {
          codigo: 'posicion_sin_calendario',
          mensaje: 'x',
          severidad: 'advertencia',
          accion_requerida: null,
          detalle: { cantidad: 1, motivos: { B: 'sin_paridad' } },
        },
      ],
    })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.calculable).toBe(false)
    expect(efecto.motivoNoCalculable).toContain('B')
  })

  it('no calculable si el origen está fuera del universo en el calendario actual, y nombra el ticker', () => {
    const actual = calendario({
      meses: DOS_MESES_ACTUAL,
      alertas: [
        {
          codigo: 'posicion_fuera_del_universo',
          mensaje: 'x',
          severidad: 'advertencia',
          accion_requerida: null,
          detalle: { cantidad: 1, tickers: ['A'] },
        },
      ],
    })
    const simulado = calendario({ meses: DOS_MESES_ACTUAL })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.calculable).toBe(false)
    expect(efecto.motivoNoCalculable).toContain('A')
  })

  it('no calculable si las ventanas de doce meses no coinciden', () => {
    const actual = calendario({ meses: [mes('2026-09', { usd: 100, ars: 0 })] })
    const simulado = calendario({ meses: [mes('2026-10', { usd: 100, ars: 0 })] })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.calculable).toBe(false)
  })

  it('no calculable si algún calendario no trae montos', () => {
    const actual = calendario({ meses: DOS_MESES_ACTUAL, con_montos: false })
    const simulado = calendario({ meses: DOS_MESES_ACTUAL })
    const efecto = diffCalendario(actual, simulado, candidata('A', 'B'))
    expect(efecto.calculable).toBe(false)
  })
})
