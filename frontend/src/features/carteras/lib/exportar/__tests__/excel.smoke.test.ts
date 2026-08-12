import { describe, expect, it } from 'vitest'
import { generarExcel } from '../excel'
import type { ModeloExport } from '../modelo'

const modelo: ModeloExport = {
  encabezado: { nombre: 'x', descripcion: null, origen: 'armador', snapshotEn: '2026-08-10T12:00:00Z', tipoDeCambio: 1050, montoUsd: 100 },
  bloques: [],
  excluidas: [],
  rendimientos: [],
  plazoPromedio: { anios: null, posicionesExcluidas: 0 },
  vector: null,
  calendario: { disponible: false, monedas: [], meses: [], totalPorMoneda: {}, detalle: [] },
  declaraciones: { lamina: { aplica: false, posicionesSinLamina: 0, pctSinAjustar: null }, mercadoDisponible: false, perfilConcentracion: null, notas: [] },
  pie: { capturadoEn: null, demoraMinutos: null, demoraFuente: null, snapshotEn: '2026-08-10T12:00:00Z', generadoEn: '2026-08-10T12:00:00Z', mercadoDisponible: false },
}

describe('generarExcel (smoke)', () => {
  it('produce un Blob', async () => {
    const blob = await generarExcel(modelo)
    expect(blob).toBeInstanceOf(Blob)
    expect(blob.size).toBeGreaterThan(0)
  })
})
