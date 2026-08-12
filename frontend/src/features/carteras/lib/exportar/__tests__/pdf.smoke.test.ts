import { describe, expect, it } from 'vitest'

import { generarPdf } from '../pdf'
import type { ModeloExport } from '../modelo'

const modelo: ModeloExport = {
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
  ],
  plazoPromedio: { anios: 3.5, posicionesExcluidas: 0 },
  vector: null,
  calendario: { disponible: false, monedas: [], meses: [], totalPorMoneda: {}, detalle: [] },
  declaraciones: { lamina: { aplica: true, posicionesSinLamina: 1, pctSinAjustar: 40 }, mercadoDisponible: true, perfilConcentracion: 'moderado', notas: ['nota de prueba'] },
  pie: { capturadoEn: '2026-08-10T11:45:00Z', demoraMinutos: 20, demoraFuente: 'BYMA', snapshotEn: '2026-08-10T12:00:00Z', generadoEn: '2026-08-10T13:30:00Z', mercadoDisponible: true },
}

describe('generarPdf (smoke)', () => {
  it('produce un Blob no vacío', async () => {
    const blob = await generarPdf(modelo)
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.size).toBeGreaterThan(0)
  })
})
