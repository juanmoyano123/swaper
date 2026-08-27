/**
 * Los tres GWT de F-042 verificados a nivel de las hojas de Excel (no sobre el modelo, que ya se
 * testea en `modelo.test.ts`): que la celda de rendimiento sea un número crudo con formato de
 * porcentaje, que ninguna celda de ninguna hoja combine naturalezas, que la lámina faltante quede
 * declarada, y que el pie aparezca en la hoja Parámetros.
 */

import { describe, expect, it } from 'vitest'

import { SIN_DATO, NO_APLICA } from '@/lib/fmt'

import type { ModeloExport } from '../modelo'
import { hojasDesdeModelo, type FilaExcel } from '../hojasExcel'

function modeloBase(overrides: Partial<ModeloExport> = {}): ModeloExport {
  return {
    encabezado: {
      nombre: 'Renta USD · perfil moderado',
      descripcion: null,
      origen: 'armador',
      snapshotEn: '2026-08-10T12:00:00Z',
      tipoDeCambio: 1050,
      montoUsd: 10_000,
    },
    bloques: [
      {
        id: 'soberanos',
        rotulo: 'Soberanos y subsoberanos',
        filas: [
          {
            ticker: 'AL30D',
            bloque: 'soberanos',
            emisorODenominacion: 'República Argentina',
            ley: 'Ley N.Y.',
            calificacion: null,
            sector: 'Soberano',
            naturaleza: 'tir_usd',
            naturalezaNombre: 'TIR en dólares (hard dollar)',
            rendimiento: 0.12,
            rendimientoAplica: true,
            duracion: 3.5,
            duracionAplica: true,
            vencimiento: '2030-07-09',
            lamina: null,
            laminaAplica: true,
            moneda: 'usd',
            precio: 70,
            vnOCantidad: 5714,
            invertido: 4000,
            invertidoUsd: 4000,
            pesoPedido: 40,
            pesoReal: 40,
          },
        ],
      },
    ],
    excluidas: [],
    rendimientos: [
      { naturaleza: 'tir_usd', nombre: 'TIR en dólares (hard dollar)', pctCartera: 40, rendimientoPond: 0.12, posiciones: 1, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tir_dolar_linked', nombre: 'Rendimiento dólar linked', pctCartera: 0, rendimientoPond: null, posiciones: 0, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tasa_real_cer', nombre: 'Tasa real sobre CER (por encima de inflación)', pctCartera: 0, rendimientoPond: null, posiciones: 0, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tir_ea_ars', nombre: 'TIR efectiva anual en pesos', pctCartera: 0, rendimientoPond: null, posiciones: 0, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tna_nominal_ars', nombre: 'TNA nominal en pesos', pctCartera: 0, rendimientoPond: null, posiciones: 0, posicionesExcluidas: 0, pctExcluido: 0 },
    ],
    plazoPromedio: { anios: 3.5, posicionesExcluidas: 0 },
    vector: null,
    calendario: { disponible: false, monedas: [], meses: [], totalPorMoneda: {}, detalle: [] },
    declaraciones: {
      lamina: { aplica: true, posicionesSinLamina: 1, pctSinAjustar: 40 },
      mercadoDisponible: true,
      perfilConcentracion: 'moderado',
      notas: ['nota de prueba'],
    },
    pie: {
      capturadoEn: '2026-08-10T11:45:00Z',
      demoraMinutos: 20,
      demoraFuente: 'BYMA',
      snapshotEn: '2026-08-10T12:00:00Z',
      generadoEn: '2026-08-10T13:30:00Z',
      mercadoDisponible: true,
    },
    ...overrides,
  }
}

function hoja(modelo: ModeloExport, nombre: string): FilaExcel[] {
  const encontrada = hojasDesdeModelo(modelo).find((h) => h.nombre === nombre)
  if (!encontrada) throw new Error(`hoja no encontrada: ${nombre}`)
  return encontrada.filas
}

describe('GWT-1: rendimientos abiertos, número crudo con formato porcentual', () => {
  it('la celda de rendimiento ponderado es un número (fracción) con formato de porcentaje, no un string es-AR', () => {
    const filas = hoja(modeloBase(), 'Rendimientos')
    const filaTirUsd = filas[1] // fila 0 es el encabezado
    const celdaRendimiento = filaTirUsd[2]
    expect(celdaRendimiento.tipo).toBe('numero')
    expect(celdaRendimiento.valor).toBeCloseTo(0.12)
    expect(celdaRendimiento.formato).toBe('0.00%')
  })

  it('las cinco naturalezas aparecen en filas separadas, ninguna celda las combina', () => {
    const filas = hoja(modeloBase(), 'Rendimientos')
    // encabezado + 5 naturalezas + fila vacía + plazo promedio = 8
    const nombresDeNaturaleza = filas.slice(1, 6).map((f) => f[0].valor)
    expect(nombresDeNaturaleza).toEqual([
      'TIR en dólares (hard dollar)',
      'Rendimiento dólar linked',
      'Tasa real sobre CER (por encima de inflación)',
      'TIR efectiva anual en pesos',
      'TNA nominal en pesos',
    ])
    // Ninguna hoja completa del export tiene una fila "Total" que sume rendimientos.
    const todasLasHojas = hojasDesdeModelo(modeloBase())
    for (const h of todasLasHojas) {
      for (const fila of h.filas) {
        const primeraCelda = String(fila[0]?.valor ?? '')
        expect(primeraCelda.toLowerCase()).not.toMatch(/rendimiento total|tir total|rendimiento promedio/)
      }
    }
  })
})

describe('GWT-2: la lámina faltante queda declarada en la hoja Declaraciones', () => {
  it('cuenta la posición sin lámina y su porcentaje sin ajustar', () => {
    const filas = hoja(modeloBase(), 'Declaraciones')
    const filaLamina = filas.find((f) => String(f[0].valor).includes('sin lámina informada'))
    expect(filaLamina).toBeDefined()
    expect(filaLamina![0].valor).toBe('1 posición(es) sin lámina informada')
    expect(filaLamina![1].tipo).toBe('numero')
    expect(filaLamina![1].valor).toBeCloseTo(40)
    expect(filaLamina![1].formato).toBe('0.00"%"')
  })

  it('en la hoja Cartera, la fila con lámina null muestra `s/d`, no cero', () => {
    const filas = hoja(modeloBase(), 'Cartera')
    const filaAl30d = filas[1]
    const celdaLamina = filaAl30d[10]
    expect(celdaLamina.tipo).toBe('texto')
    expect(celdaLamina.valor).toBe(SIN_DATO)
  })

  it('una posición de renta variable muestra "no aplica" en lámina, no `s/d`', () => {
    const modelo = modeloBase({
      bloques: [
        {
          id: 'renta_variable',
          rotulo: 'Renta variable',
          filas: [
            {
              ticker: 'GGAL',
              bloque: 'renta_variable',
              emisorODenominacion: 'Grupo Financiero Galicia',
              ley: null,
              calificacion: null,
              sector: null,
              naturaleza: null,
              naturalezaNombre: null,
              rendimiento: null,
              rendimientoAplica: false,
              duracion: null,
              duracionAplica: false,
              vencimiento: null,
              lamina: null,
              laminaAplica: false,
              moneda: 'usd',
              precio: 30,
              vnOCantidad: 100,
              invertido: 3000,
              invertidoUsd: 3000,
              pesoPedido: 100,
              pesoReal: 100,
            },
          ],
        },
      ],
    })
    const filas = hoja(modelo, 'Cartera')
    const celdaLamina = filas[1][10]
    expect(celdaLamina.valor).toBe(NO_APLICA)
  })
})

describe('GWT-3: el pie aparece en la hoja Parámetros', () => {
  it('trae la hora de captura de precios, la demora de la fuente y la fecha de generación', () => {
    const filas = hoja(modeloBase(), 'Parámetros')
    const filaPrecios = filas.find((f) => f[0].valor === 'Precios capturados el')
    const filaDemora = filas.find((f) => f[0].valor === 'Demora declarada de la fuente')
    const filaGenerado = filas.find((f) => f[0].valor === 'Archivo generado el')

    expect(filaPrecios![1].tipo).toBe('fecha')
    expect(filaDemora![1].valor).toBe('20 min (BYMA)')
    expect(filaGenerado![1].tipo).toBe('fecha')
  })

  it('sin fuente del dato, declara `s/d` en vez de una fecha inventada', () => {
    const modelo = modeloBase({
      pie: { capturadoEn: null, demoraMinutos: null, demoraFuente: null, snapshotEn: '2026-08-10T12:00:00Z', generadoEn: '2026-08-10T13:30:00Z', mercadoDisponible: false },
    })
    const filas = hoja(modelo, 'Parámetros')
    const filaPrecios = filas.find((f) => f[0].valor === 'Precios capturados el')
    expect(filaPrecios![1].valor).toBe(SIN_DATO)
    expect(filaPrecios![1].tipo).toBe('texto')
  })
})

describe('Hoja Calendario: nunca una columna que cruce monedas', () => {
  it('una columna por moneda, sin ningún total combinado', () => {
    const modelo = modeloBase({
      calendario: {
        disponible: true,
        monedas: ['usd', 'ars'],
        meses: [{ etiqueta: '09/2026', nombre: 'Septiembre 2026', porMoneda: { usd: 35, ars: 1200 } }],
        totalPorMoneda: { usd: 420, ars: 14_400 },
        detalle: [],
      },
    })
    const filas = hoja(modelo, 'Calendario')
    expect(filas[0].map((c) => c.valor)).toEqual(['Mes', 'Renta USD', 'Renta ARS'])
    const filaTotal = filas.find((f) => f[0].valor === 'Total anual')
    expect(filaTotal![1].valor).toBeCloseTo(420)
    expect(filaTotal![2].valor).toBeCloseTo(14_400)
  })
})
