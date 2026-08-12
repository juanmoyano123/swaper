/**
 * Los tres GWT de F-042 verificados sobre `modeloDesdeSnapshot`, más los casos borde de cartera
 * vieja (sin `mercado`), bloques en orden fijo y renta variable con "no aplica".
 */

import { describe, expect, it } from 'vitest'

import type { MercadoCongelado, SnapshotArmador, SnapshotCargada } from '../../esquemaSnapshot'
import { modeloDesdeSnapshot, type ContextoExport } from '../modelo'

const contexto: ContextoExport = {
  nombre: 'Renta USD · perfil moderado',
  descripcion: null,
  snapshotEn: '2026-08-10T12:00:00Z',
  generadoEn: '2026-08-10T13:30:00Z',
}

function especie(overrides: Partial<MercadoCongelado['especies'][number]> = {}): MercadoCongelado['especies'][number] {
  return {
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
    ...overrides,
  }
}

function mercado(overrides: Partial<MercadoCongelado> = {}): MercadoCongelado {
  return {
    especies: [especie()],
    vector: null,
    perfilConcentracion: 'moderado',
    calendario: null,
    fuenteDelDato: { capturadoEn: '2026-08-10T11:45:00Z', demoraMinutos: 20, demoraFuente: 'BYMA' },
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

function snapshotCargada(overrides: Partial<SnapshotCargada> = {}): SnapshotCargada {
  return {
    version: 1,
    origen: 'cargada',
    tipoDeCambio: 1050,
    perfil: 'moderado',
    posiciones: [{ id: 'p1', fila: 1, tickerDeclarado: 'AL30D', nominal: 1000, monto: null, valida: true, motivo: null }],
    valuadas: [{ ticker: 'AL30D', moneda: 'usd', invertido: 700, invertidoUsd: 700, pesoReal: 100 }],
    excluidas: [],
    totalInvertidoUsd: 700,
    plan: { aceptadas: [], descartadas: [] },
    ...overrides,
  }
}

describe('GWT-1: rendimientos abiertos por naturaleza, nunca promediados', () => {
  it('con tres naturalezas de tasa, cada una llega abierta con su propio rendimiento ponderado', () => {
    const snapshot = snapshotArmador({
      posiciones: [
        { ticker: 'AL30D', peso: 40, clase: 'renta_fija' },
        { ticker: 'TX26', peso: 30, clase: 'renta_fija' },
        { ticker: 'LECAP-S31', peso: 30, clase: 'renta_fija' },
      ],
      resueltas: [
        { ticker: 'AL30D', clase: 'renta_fija', peso: 40, moneda: 'usd', precio: 70, vn: 5714, cantidad: null, invertido: 4000, invertidoUsd: 4000 },
        { ticker: 'TX26', clase: 'renta_fija', peso: 30, moneda: 'ars', precio: 900, vn: 333, cantidad: null, invertido: 3000, invertidoUsd: 3000 },
        { ticker: 'LECAP-S31', clase: 'renta_fija', peso: 30, moneda: 'ars', precio: 850, vn: 353, cantidad: null, invertido: 3000, invertidoUsd: 3000 },
      ],
      totalInvertidoUsd: 10_000,
      mercado: mercado({
        especies: [
          especie({ ticker: 'AL30D', naturaleza: 'tir_usd', naturaleza_nombre: 'TIR en dólares (hard dollar)', rendimiento: 0.12 }),
          especie({ ticker: 'TX26', naturaleza: 'tasa_real_cer', naturaleza_nombre: 'Tasa real sobre CER (por encima de inflación)', rendimiento: 0.09, moneda_cupon: 'ARS' }),
          especie({ ticker: 'LECAP-S31', naturaleza: 'tna_nominal_ars', naturaleza_nombre: 'TNA nominal en pesos', rendimiento: 0.35, moneda_cupon: 'ARS' }),
        ],
      }),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)

    expect(modelo.rendimientos).toHaveLength(4) // las cuatro naturalezas fijas, siempre las mismas
    const porNaturaleza = new Map(modelo.rendimientos.map((r) => [r.naturaleza, r]))
    expect(porNaturaleza.get('tir_usd')?.rendimientoPond).toBeCloseTo(0.12)
    expect(porNaturaleza.get('tasa_real_cer')?.rendimientoPond).toBeCloseTo(0.09)
    expect(porNaturaleza.get('tna_nominal_ars')?.rendimientoPond).toBeCloseTo(0.35)
    // Ninguna celda las combina: no existe ningún campo de "rendimiento total" en el modelo.
    expect(Object.keys(modelo.encabezado)).not.toContain('rendimientoTotal')
    expect('rendimientoTotal' in modelo).toBe(false)
  })

  it('renta variable y FCI quedan "no aplica", no "s/d": no entran en `rendimientos`', () => {
    const snapshot = snapshotArmador({
      posiciones: [
        { ticker: 'AL30D', peso: 50, clase: 'renta_fija' },
        { ticker: 'GGAL', peso: 30, clase: 'renta_variable' },
        { ticker: 'FCI-RENTA', peso: 20, clase: 'fci' },
      ],
      resueltas: [
        { ticker: 'AL30D', clase: 'renta_fija', peso: 50, moneda: 'usd', precio: 70, vn: 7142, cantidad: null, invertido: 5000, invertidoUsd: 5000 },
        { ticker: 'GGAL', clase: 'renta_variable', peso: 30, moneda: 'usd', precio: 30, vn: null, cantidad: 100, invertido: 3000, invertidoUsd: 3000 },
        { ticker: 'FCI-RENTA', clase: 'fci', peso: 20, moneda: null, precio: null, vn: null, cantidad: null, invertido: null, invertidoUsd: null },
      ],
      totalInvertidoUsd: 8000,
      mercado: mercado({ especies: [especie(), especie({ ticker: 'GGAL', denominacion: 'Grupo Financiero Galicia' })] }),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)
    const bloqueRv = modelo.bloques.find((b) => b.id === 'renta_variable')
    const bloqueFci = modelo.bloques.find((b) => b.id === 'fci')

    expect(bloqueRv?.filas[0].rendimientoAplica).toBe(false)
    expect(bloqueRv?.filas[0].laminaAplica).toBe(false)
    expect(bloqueFci?.filas[0].rendimientoAplica).toBe(false)
    // Sólo la renta fija (AL30D) aporta al desglose de rendimientos.
    const conPosiciones = modelo.rendimientos.filter((r) => r.posiciones > 0)
    expect(conPosiciones).toHaveLength(1)
    expect(conPosiciones[0].naturaleza).toBe('tir_usd')
  })
})

describe('GWT-2: posiciones sin lámina declaradas, con el porcentaje sin ajustar', () => {
  it('dos posiciones sin lámina informada: conteo y porcentaje exactos', () => {
    const snapshot = snapshotArmador({
      posiciones: [
        { ticker: 'AL30D', peso: 40, clase: 'renta_fija' },
        { ticker: 'GD30D', peso: 35, clase: 'renta_fija' },
        { ticker: 'AE38D', peso: 25, clase: 'renta_fija' },
      ],
      resueltas: [
        { ticker: 'AL30D', clase: 'renta_fija', peso: 40, moneda: 'usd', precio: 70, vn: 5714, cantidad: null, invertido: 4000, invertidoUsd: 4000 },
        { ticker: 'GD30D', clase: 'renta_fija', peso: 35, moneda: 'usd', precio: 65, vn: 5384, cantidad: null, invertido: 3500, invertidoUsd: 3500 },
        { ticker: 'AE38D', clase: 'renta_fija', peso: 25, moneda: 'usd', precio: 55, vn: 4545, cantidad: null, invertido: 2500, invertidoUsd: 2500 },
      ],
      totalInvertidoUsd: 10_000,
      mercado: mercado({
        especies: [
          especie({ ticker: 'AL30D', lamina: 1 }),
          especie({ ticker: 'GD30D', lamina: null }), // sin lámina informada — soberano real (PROGRESS.md:859-860)
          especie({ ticker: 'AE38D', lamina: null }), // ídem
        ],
      }),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)

    expect(modelo.declaraciones.lamina.aplica).toBe(true)
    expect(modelo.declaraciones.lamina.posicionesSinLamina).toBe(2)
    // GD30D (35%) + AE38D (25%) de peso real, sobre invertidoUsd/totalInvertidoUsd*100.
    expect(modelo.declaraciones.lamina.pctSinAjustar).toBeCloseTo(60)
  })

  it('sin ninguna posición ajustable (todo renta variable), el porcentaje es null, no cero', () => {
    const snapshot = snapshotArmador({
      posiciones: [{ ticker: 'GGAL', peso: 100, clase: 'renta_variable' }],
      resueltas: [
        { ticker: 'GGAL', clase: 'renta_variable', peso: 100, moneda: 'usd', precio: 30, vn: null, cantidad: 300, invertido: 9000, invertidoUsd: 9000 },
      ],
      totalInvertidoUsd: 9000,
      mercado: mercado({ especies: [] }),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)
    expect(modelo.declaraciones.lamina.pctSinAjustar).toBeNull()
    expect(modelo.declaraciones.lamina.posicionesSinLamina).toBe(0)
  })
})

describe('GWT-3: el pie declara la hora del snapshot de precios y la demora de la fuente', () => {
  it('con mercado congelado, el pie trae capturadoEn y demora, separado de cuándo se generó el archivo', () => {
    const modelo = modeloDesdeSnapshot(snapshotArmador({ mercado: mercado() }), contexto)
    expect(modelo.pie).toEqual({
      capturadoEn: '2026-08-10T11:45:00Z',
      demoraMinutos: 20,
      demoraFuente: 'BYMA',
      snapshotEn: '2026-08-10T12:00:00Z',
      generadoEn: '2026-08-10T13:30:00Z',
      mercadoDisponible: true,
    })
  })

  it('sin fuenteDelDato, se declara `s/d` en vez de inventar una hora', () => {
    const modelo = modeloDesdeSnapshot(
      snapshotArmador({ mercado: mercado({ fuenteDelDato: null }) }),
      contexto,
    )
    expect(modelo.pie.capturadoEn).toBeNull()
    expect(modelo.pie.demoraMinutos).toBeNull()
  })
})

describe('Cartera guardada antes de F-042 (sin `mercado`)', () => {
  it('arma el modelo igual, con los atributos de mercado ausentes y declarados', () => {
    const modelo = modeloDesdeSnapshot(snapshotArmador(), contexto)

    expect(modelo.declaraciones.mercadoDisponible).toBe(false)
    expect(modelo.declaraciones.notas[0]).toMatch(/guardada antes de F-042/)
    expect(modelo.vector).toBeNull()
    expect(modelo.calendario.disponible).toBe(false)
    expect(modelo.declaraciones.lamina.aplica).toBe(false)
    expect(modelo.pie.capturadoEn).toBeNull()
    // Las posiciones y montos, en cambio, siguen exportándose — eso sí estaba en F-041.
    expect(modelo.bloques.flatMap((b) => b.filas)).toHaveLength(1)
  })

  it('origen cargada: idéntico criterio', () => {
    const modelo = modeloDesdeSnapshot(snapshotCargada(), contexto)
    expect(modelo.declaraciones.mercadoDisponible).toBe(false)
    expect(modelo.bloques.flatMap((b) => b.filas)).toHaveLength(1)
  })
})

describe('Bloques: orden fijo, vacío ausente', () => {
  it('sólo aparecen los bloques con contenido, en el orden de la mesa', () => {
    const snapshot = snapshotArmador({
      posiciones: [
        { ticker: 'GGAL', peso: 60, clase: 'renta_variable' },
        { ticker: 'AL30D', peso: 40, clase: 'renta_fija' },
      ],
      resueltas: [
        { ticker: 'GGAL', clase: 'renta_variable', peso: 60, moneda: 'usd', precio: 30, vn: null, cantidad: 200, invertido: 6000, invertidoUsd: 6000 },
        { ticker: 'AL30D', clase: 'renta_fija', peso: 40, moneda: 'usd', precio: 70, vn: 5714, cantidad: null, invertido: 4000, invertidoUsd: 4000 },
      ],
      totalInvertidoUsd: 10_000,
      mercado: mercado(),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)
    // Soberanos antes que renta variable (orden de la mesa), y no hay bloque "corporativos" ni "fci".
    expect(modelo.bloques.map((b) => b.id)).toEqual(['soberanos', 'renta_variable'])
  })

  it('un ticker sin mercado congelado cae en "sin clasificar", no se le adivina la clase', () => {
    const modelo = modeloDesdeSnapshot(snapshotArmador(), contexto) // sin `mercado`
    expect(modelo.bloques.map((b) => b.id)).toEqual(['sin_clasificar'])
  })
})

describe('excluidas (origen cargada)', () => {
  it('declara el motivo con el ticker declarado, no el id interno de la fila', () => {
    const snapshot = snapshotCargada({
      posiciones: [{ id: 'p2', fila: 2, tickerDeclarado: 'XYZINEXISTENTE', nominal: 500, monto: null, valida: true, motivo: null }],
      valuadas: [],
      excluidas: [{ id: 'p2', motivo: 'no_resuelta', montoDeclarado: null }],
      totalInvertidoUsd: 0,
    })
    const modelo = modeloDesdeSnapshot(snapshot, contexto)
    expect(modelo.excluidas).toEqual([{ ticker: 'XYZINEXISTENTE', motivo: 'no resuelta contra el universo', montoDeclarado: null }])
  })
})

describe('calendario: separado por moneda', () => {
  it('nunca suma renta de distintas monedas en un mismo total', () => {
    const snapshot = snapshotArmador({
      mercado: mercado({
        calendario: {
          meses: [
            {
              anio: 2026,
              mes: 9,
              etiqueta: '09/2026',
              nombre: 'Septiembre 2026',
              renta: { usd: 35, ars: 1200 },
              amortizacion: null,
              instrumentos: [
                { ticker: 'AL30D', moneda: 'usd', fechas: ['2026-09-09'], renta: 35, amortizacion: null },
                { ticker: 'TX26', moneda: 'ars', fechas: ['2026-09-15'], renta: 1200, amortizacion: null },
              ],
            },
          ],
          rentaAnual: { usd: 420, ars: 14_400 },
          amortizacionAnual: null,
        },
      }),
    })

    const modelo = modeloDesdeSnapshot(snapshot, contexto)
    expect(modelo.calendario.disponible).toBe(true)
    expect(modelo.calendario.monedas.sort()).toEqual(['ars', 'usd'])
    expect(modelo.calendario.totalPorMoneda).toEqual({ usd: 420, ars: 14_400 })
    expect(modelo.calendario.meses[0].porMoneda).toEqual({ usd: 35, ars: 1200 })
  })
})
