/**
 * Los tres GWT de F-042 sobre las secciones del PDF, más la validación de que ningún string
 * generado se sale de Windows-1252 (jsPDF con `helvetica` no puede dibujar fuera de esa página de
 * códigos).
 */

import { describe, expect, it } from 'vitest'

import type { ModeloExport } from '../modelo'
import { seccionesDesdeModelo, type SeccionPdf, type TablaPdf } from '../seccionesPdf'

// Windows-1252 cubre 0x00–0xFF salvo un puñado de posiciones sin asignar (0x81/0x8D/0x8F/0x90/0x9D).
const SIN_ASIGNAR_WINANSI = new Set([0x81, 0x8d, 0x8f, 0x90, 0x9d])
function esWinAnsi(texto: string): boolean {
  for (const char of texto) {
    const codigo = char.codePointAt(0)!
    if (codigo > 0xff || SIN_ASIGNAR_WINANSI.has(codigo)) return false
  }
  return true
}

function modeloBase(overrides: Partial<ModeloExport> = {}): ModeloExport {
  return {
    encabezado: { nombre: 'Renta USD · perfil moderado', descripcion: null, origen: 'armador', snapshotEn: '2026-08-10T12:00:00Z', tipoDeCambio: 1050, montoUsd: 10_000 },
    bloques: [
      {
        id: 'soberanos',
        rotulo: 'Soberanos y subsoberanos',
        filas: [
          {
            ticker: 'AL30D', bloque: 'soberanos', emisorODenominacion: 'República Argentina', ley: 'Ley N.Y.',
            calificacion: null, sector: 'Soberano', naturaleza: 'tir_usd', naturalezaNombre: 'TIR en dólares (hard dollar)',
            rendimiento: 0.12, rendimientoAplica: true, duracion: 3.5, duracionAplica: true, vencimiento: '2030-07-09',
            lamina: null, laminaAplica: true, moneda: 'usd', precio: 70, vnOCantidad: 5714, invertido: 4000,
            invertidoUsd: 4000, pesoPedido: 40, pesoReal: 40,
          },
        ],
      },
    ],
    excluidas: [],
    rendimientos: [
      { naturaleza: 'tir_usd', nombre: 'TIR en dólares (hard dollar)', pctCartera: 40, rendimientoPond: 0.12, posiciones: 1, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tir_dolar_linked', nombre: 'Rendimiento dólar linked', pctCartera: 0, rendimientoPond: null, posiciones: 0, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tasa_real_cer', nombre: 'Tasa real sobre CER (por encima de inflación)', pctCartera: 30, rendimientoPond: 0.09, posiciones: 1, posicionesExcluidas: 0, pctExcluido: 0 },
      { naturaleza: 'tna_nominal_ars', nombre: 'TNA nominal en pesos', pctCartera: 30, rendimientoPond: 0.35, posiciones: 1, posicionesExcluidas: 0, pctExcluido: 0 },
    ],
    plazoPromedio: { anios: 3.5, posicionesExcluidas: 0 },
    vector: null,
    calendario: { disponible: false, monedas: [], meses: [], totalPorMoneda: {}, detalle: [] },
    declaraciones: { lamina: { aplica: true, posicionesSinLamina: 1, pctSinAjustar: 40 }, mercadoDisponible: true, perfilConcentracion: 'moderado', notas: ['Los rendimientos se muestran abiertos por naturaleza de tasa.'] },
    pie: { capturadoEn: '2026-08-10T11:45:00Z', demoraMinutos: 20, demoraFuente: 'BYMA', snapshotEn: '2026-08-10T12:00:00Z', generadoEn: '2026-08-10T13:30:00Z', mercadoDisponible: true },
    ...overrides,
  }
}

function tabla(doc: ReturnType<typeof seccionesDesdeModelo>, titulo: string): TablaPdf {
  const encontrada = doc.secciones.find((s): s is TablaPdf => s.tipo === 'tabla' && s.titulo === titulo)
  if (!encontrada) throw new Error(`tabla no encontrada: ${titulo}`)
  return encontrada
}

describe('GWT-1: rendimientos abiertos por naturaleza, en filas separadas', () => {
  it('la tabla trae las cuatro naturalezas, cada una en su fila, con su rendimiento propio', () => {
    const doc = seccionesDesdeModelo(modeloBase())
    const t = tabla(doc, 'Rendimientos por naturaleza de tasa')
    expect(t.filas).toHaveLength(4)
    expect(t.filas.map((f) => f[0])).toEqual([
      'TIR en dólares (hard dollar)',
      'Rendimiento dólar linked',
      'Tasa real sobre CER (por encima de inflación)',
      'TNA nominal en pesos',
    ])
    // Ninguna fila de ninguna sección junta dos naturalezas en un solo número.
    for (const seccion of doc.secciones) {
      if (seccion.tipo !== 'tabla') continue
      for (const fila of seccion.filas) {
        expect(fila[0].toLowerCase()).not.toMatch(/rendimiento total|tir total|promedio general/)
      }
    }
  })
})

describe('GWT-2: la declaración de lámina cuenta la posición faltante y su porcentaje', () => {
  it('el párrafo de declaraciones incluye el conteo y el porcentaje sin ajustar', () => {
    const doc = seccionesDesdeModelo(modeloBase())
    const declaraciones = doc.secciones.find((s) => s.tipo === 'parrafo' && s.titulo === 'Declaraciones')
    expect(declaraciones?.tipo).toBe('parrafo')
    expect((declaraciones as { texto: string }).texto).toMatch(/1 posición\(es\) sin lámina informada \(40,00% de la cartera sin ajustar\)/)
  })

  it('sin mercado congelado, declara la ausencia en vez de fabricar un porcentaje', () => {
    const modelo = modeloBase({ declaraciones: { lamina: { aplica: false, posicionesSinLamina: 0, pctSinAjustar: null }, mercadoDisponible: false, perfilConcentracion: null, notas: ['Cartera guardada antes de F-042.'] } })
    const doc = seccionesDesdeModelo(modelo)
    const declaraciones = doc.secciones.find((s) => s.tipo === 'parrafo' && s.titulo === 'Declaraciones')
    expect((declaraciones as { texto: string }).texto).toMatch(/sin dato — cartera guardada antes de F-042/)
  })
})

describe('GWT-3: el pie declara la hora del snapshot de precios y la demora de la fuente', () => {
  it('una sola línea con las dos puntas, separada de cuándo se generó el documento', () => {
    const doc = seccionesDesdeModelo(modeloBase())
    expect(doc.pie).toMatch(/Precios capturados: 10\/08\/2026/)
    expect(doc.pie).toMatch(/Demora de la fuente: 20 min \(BYMA\)/)
    expect(doc.pie).toMatch(/Generado: 10\/08\/2026/)
  })

  it('sin fuente del dato, el pie declara `s/d`, no inventa una hora', () => {
    const modelo = modeloBase({ pie: { capturadoEn: null, demoraMinutos: null, demoraFuente: null, snapshotEn: '2026-08-10T12:00:00Z', generadoEn: '2026-08-10T13:30:00Z', mercadoDisponible: false } })
    const doc = seccionesDesdeModelo(modelo)
    expect(doc.pie).toMatch(/Precios capturados: s\/d/)
  })
})

describe('WinAnsi: ningún texto generado se sale de la página de códigos', () => {
  it('todos los strings del documento son representables en Windows-1252', () => {
    const doc = seccionesDesdeModelo(modeloBase())
    const strings: string[] = [doc.titulo, doc.bajada, doc.pie]
    for (const seccion of doc.secciones as SeccionPdf[]) {
      if (seccion.tipo === 'parrafo') {
        if (seccion.titulo) strings.push(seccion.titulo)
        strings.push(seccion.texto)
      } else {
        strings.push(...seccion.columnas)
        for (const fila of seccion.filas) strings.push(...fila)
      }
    }
    const noRepresentables = strings.filter((s) => !esWinAnsi(s))
    expect(noRepresentables).toEqual([])
  })
})
