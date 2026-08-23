/**
 * Los schemas del snapshot — round-trip serializar→parsear y la whitelist exacta de claves
 * (GWT-4: una cartera guardada no puede llevar ningún campo de identificación de cliente).
 */

import { describe, expect, it } from 'vitest'

import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import {
  esquemaFilaDetalle,
  esquemaFilaListado,
  esquemaSnapshotArmador,
  esquemaSnapshotCargada,
  esquemaSnapshotCartera,
  type SnapshotArmador,
  type SnapshotCargada,
} from '../lib/esquemaSnapshot'

function candidata(): Candidata {
  return {
    tipo: 'mejora_perfil',
    segmento: 'usd_hard',
    origen: {
      ticker: 'AL30D',
      emisor: 'República Argentina',
      rendimiento: 0.11,
      duracion: 3.5,
      moneda_cupon: 'USD',
      ley: 'Ley N.Y.',
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 100_000,
    },
    destino: {
      ticker: 'BGC4D',
      emisor: 'República Argentina',
      rendimiento: 0.132,
      duracion: 2.5,
      moneda_cupon: 'USD',
      ley: 'Ley N.Y.',
      calificacion: null,
      lamina: 1,
      frecuencia_cupon: 'semestral',
      volumen_usd: 300_000,
    },
    delta: { rendimiento_pp: 2.2, duracion: -1 },
    flags: {
      mismo_emisor: true,
      pasa_a_cable: false,
      mejora_ley: false,
      empeora_ley: false,
      mejora_volumen: true,
      posible_distress: false,
    },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: null,
  }
}

function snapshotCargada(overrides: Partial<SnapshotCargada> = {}): SnapshotCargada {
  return {
    version: 1,
    origen: 'cargada',
    tipoDeCambio: 1050,
    perfil: 'moderado',
    posiciones: [
      { id: 'p1', fila: 1, tickerDeclarado: 'AL30D', nominal: 1000, monto: null, valida: true, motivo: null },
    ],
    valuadas: [{ ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, pesoReal: 100 }],
    excluidas: [],
    totalInvertidoUsd: 700,
    plan: { aceptadas: [candidata()], descartadas: ['BGC4D->AL30D'] },
    ...overrides,
  }
}

function snapshotArmador(overrides: Partial<SnapshotArmador> = {}): SnapshotArmador {
  return {
    version: 1,
    origen: 'armador',
    tipoDeCambio: 1050,
    montoTotalUsd: 10_000,
    posiciones: [{ ticker: 'AL30D', peso: 100, clase: 'renta_fija' }],
    resueltas: [
      {
        ticker: 'AL30D',
        clase: 'renta_fija',
        peso: 100,
        moneda: 'usd',
        precio: 70,
        vn: 14_285.7,
        cantidad: null,
        invertido: 10_000,
        invertidoUsd: 10_000,
      },
    ],
    totalInvertidoUsd: 10_000,
    ...overrides,
  }
}

describe('esquemaSnapshotCargada', () => {
  it('round-trip: serializa y vuelve a parsear sin pérdida', () => {
    const original = snapshotCargada()
    const parseado = esquemaSnapshotCargada.parse(JSON.parse(JSON.stringify(original)))
    expect(parseado).toEqual(original)
  })

  it('rechaza una clave no declarada al nivel de cartera (GWT-4)', () => {
    const conPii = { ...snapshotCargada(), nombreCliente: 'Juan Pérez' }
    expect(() => esquemaSnapshotCargada.parse(conPii)).toThrow('unrecognized')
  })

  it('rechaza una clave no declarada dentro de una posición valuada', () => {
    const original = snapshotCargada()
    const conPii = {
      ...original,
      valuadas: [{ ...original.valuadas[0], dniCliente: '12345678' }],
    }
    expect(() => esquemaSnapshotCargada.parse(conPii)).toThrow('unrecognized')
  })

  it('el conjunto de claves de una posición valuada es exactamente el declarado', () => {
    const parseado = esquemaSnapshotCargada.parse(snapshotCargada())
    expect(Object.keys(parseado.valuadas[0]).sort()).toEqual(
      ['invertido', 'invertidoUsd', 'moneda', 'pesoReal', 'ticker'].sort(),
    )
  })
})

describe('esquemaSnapshotArmador', () => {
  it('round-trip: serializa y vuelve a parsear sin pérdida', () => {
    const original = snapshotArmador()
    const parseado = esquemaSnapshotArmador.parse(JSON.parse(JSON.stringify(original)))
    expect(parseado).toEqual(original)
  })

  it('rechaza una clave no declarada dentro de una resuelta', () => {
    const original = snapshotArmador()
    const conPii = {
      ...original,
      resueltas: [{ ...original.resueltas[0], contactoAsesor: 'juan@ejemplo.com' }],
    }
    expect(() => esquemaSnapshotArmador.parse(conPii)).toThrow('unrecognized')
  })
})

describe('F-046: codigoCafci y cuotapartes, agregados el 23/08/2026', () => {
  it('un snapshot guardado antes de F-046 (sin codigoCafci ni cuotapartes) sigue parseando', () => {
    // `snapshotArmador()` no declara estos campos: es exactamente la forma de una fila vieja.
    const parseado = esquemaSnapshotArmador.parse(snapshotArmador())
    expect(parseado.posiciones[0].codigoCafci).toBeUndefined()
    expect(parseado.resueltas[0].codigoCafci).toBeUndefined()
    expect(parseado.resueltas[0].cuotapartes).toBeUndefined()
  })

  it('un FCI con codigoCafci y cuotapartes round-tripea sin pérdida', () => {
    const original = snapshotArmador({
      posiciones: [{ ticker: 'Fondo X', peso: 100, clase: 'fci', codigoCafci: '1234' }],
      resueltas: [
        {
          ticker: 'Fondo X',
          clase: 'fci',
          peso: 100,
          moneda: 'ars',
          precio: null,
          vn: null,
          cantidad: null,
          invertido: 150_000,
          invertidoUsd: 100,
          codigoCafci: '1234',
          cuotapartes: 10,
        },
      ],
    })
    const parseado = esquemaSnapshotArmador.parse(JSON.parse(JSON.stringify(original)))
    expect(parseado).toEqual(original)
  })

  it('un FCI legado sin codigoCafci en el mandato también parsea, declarado sin identificar', () => {
    const original = snapshotArmador({
      posiciones: [{ ticker: 'FCI legado', peso: 100, clase: 'fci' }],
      resueltas: [
        {
          ticker: 'FCI legado',
          clase: 'fci',
          peso: 100,
          moneda: null,
          precio: null,
          vn: null,
          cantidad: null,
          invertido: null,
          invertidoUsd: null,
        },
      ],
    })
    const parseado = esquemaSnapshotArmador.parse(original)
    expect(parseado.posiciones[0].codigoCafci).toBeUndefined()
  })
})

describe('esquemaSnapshotCartera (union discriminada)', () => {
  it('discrimina por `origen` y valida cada forma con su propio schema', () => {
    expect(esquemaSnapshotCartera.parse(snapshotCargada()).origen).toBe('cargada')
    expect(esquemaSnapshotCartera.parse(snapshotArmador()).origen).toBe('armador')
  })

  it('rechaza un origen desconocido', () => {
    expect(() => esquemaSnapshotCartera.parse({ ...snapshotCargada(), origen: 'otro' })).toThrow(
      /invalid|no coincide/i,
    )
  })
})

function mercadoCongelado() {
  return {
    especies: [
      {
        ticker: 'AL30D',
        clase_activo: 'bono_soberano',
        segmento: 'usd_hard',
        naturaleza: 'tir_usd',
        naturaleza_nombre: 'TIR en dólares (hard dollar)',
        rendimiento: 0.12,
        duracion: 3.5,
        vencimiento: '2030-07-09',
        ley: 'Ley N.Y.',
        emisor: 'República Argentina',
        lamina: 1,
        calificacion: null,
        sector: 'Soberano',
        moneda_cupon: 'USD',
        denominacion: null,
      },
    ],
    vector: [
      {
        id: 'duracion' as const,
        nombre: 'Duración',
        valor: 3.5,
        unidad: 'años' as const,
        grupos: [],
        cobertura: { conDato: 1, posiciones: 1, pesoConDato: 100, pesoTotal: 100, notas: [] },
      },
    ],
    perfilConcentracion: 'moderado' as const,
    calendario: {
      meses: [
        {
          anio: 2026,
          mes: 9,
          etiqueta: '09/2026',
          nombre: 'Septiembre 2026',
          renta: { usd: 35 },
          amortizacion: null,
          instrumentos: [{ ticker: 'AL30D', moneda: 'usd', fechas: ['2026-09-09'], renta: 35, amortizacion: null }],
        },
      ],
      rentaAnual: { usd: 420 },
      amortizacionAnual: null,
    },
    fuenteDelDato: { capturadoEn: '2026-08-10T12:00:00Z', demoraMinutos: 20, demoraFuente: 'BYMA' },
  }
}

describe('esquemaSnapshotCargada — mercado congelado (F-042)', () => {
  it('sin `mercado` (fila guardada antes de F-042) parsea igual', () => {
    const original = snapshotCargada()
    expect(original.mercado).toBeUndefined()
    const parseado = esquemaSnapshotCargada.parse(JSON.parse(JSON.stringify(original)))
    expect(parseado.mercado).toBeUndefined()
  })

  it('con `mercado`, round-trip sin pérdida', () => {
    const original = snapshotCargada({ mercado: mercadoCongelado() })
    const parseado = esquemaSnapshotCargada.parse(JSON.parse(JSON.stringify(original)))
    expect(parseado).toEqual(original)
  })

  it('rechaza una clave no declarada dentro de una especie congelada (GWT-4 heredado)', () => {
    const original = snapshotCargada({ mercado: mercadoCongelado() })
    const conPii = {
      ...original,
      mercado: { ...original.mercado, especies: [{ ...original.mercado!.especies[0], telefonoCliente: '11-5555' }] },
    }
    expect(() => esquemaSnapshotCargada.parse(conPii)).toThrow('unrecognized')
  })

  it('rechaza una clave no declarada dentro de la cobertura de un eje', () => {
    const original = snapshotCargada({ mercado: mercadoCongelado() })
    const eje = original.mercado!.vector![0]
    const conPii = {
      ...original,
      mercado: { ...original.mercado, vector: [{ ...eje, cobertura: { ...eje.cobertura, dniAsesor: '1' } }] },
    }
    expect(() => esquemaSnapshotCargada.parse(conPii)).toThrow('unrecognized')
  })
})

describe('esquemaFilaListado / esquemaFilaDetalle', () => {
  it('la fila del listado no exige el snapshot entero', () => {
    const fila = {
      id: 'c1',
      nombre: 'Renta USD · perfil moderado',
      descripcion: null,
      origen: 'cargada',
      moneda_referencia: 'usd',
      monto: 700,
      resumen: '1 posición',
      snapshot_en: '2026-08-10T12:00:00Z',
    }
    expect(esquemaFilaListado.parse(fila)).toEqual(fila)
  })

  it('la fila del detalle acepta el snapshot como valor sin parsear todavía', () => {
    const fila = {
      id: 'c1',
      nombre: 'x',
      descripcion: null,
      origen: 'armador',
      moneda_referencia: 'usd',
      monto: 10_000,
      resumen: '1 posición',
      snapshot_en: '2026-08-10T12:00:00Z',
      snapshot: snapshotArmador(),
    }
    const parseada = esquemaFilaDetalle.parse(fila)
    expect(esquemaSnapshotCartera.parse(parseada.snapshot).origen).toBe('armador')
  })
})
