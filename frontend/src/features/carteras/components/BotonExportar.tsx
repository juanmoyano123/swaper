/**
 * F-042 — descarga la cartera (guardada o en curso) como Excel o PDF. Arma el `ModeloExport` desde
 * el snapshot recién al hacer click, no antes: exportar es una acción explícita, igual que guardar
 * (mismo criterio que `GuardarCartera`).
 *
 * `excel.ts`/`pdf.ts` cargan `write-excel-file`/`jspdf` recién con `import()` dinámico puertas
 * adentro — este componente los importa de forma estática, así que ese límite de carga diferida
 * sigue siendo el de la librería pesada, no el de este archivo.
 */

import { useState } from 'react'

import { descargarBlob, nombreDeArchivo } from '../lib/exportar/descargar'
import { generarExcel } from '../lib/exportar/excel'
import { modeloDesdeSnapshot, type ContextoExport } from '../lib/exportar/modelo'
import { generarPdf } from '../lib/exportar/pdf'
import type { SnapshotCartera } from '../lib/esquemaSnapshot'
import { Boton } from './Boton'

type Formato = 'excel' | 'pdf'

export function BotonExportar({ snapshot, contexto }: { snapshot: SnapshotCartera; contexto: ContextoExport }) {
  const [pendiente, setPendiente] = useState<Formato | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function exportar(formato: Formato) {
    setError(null)
    setPendiente(formato)
    try {
      const modelo = modeloDesdeSnapshot(snapshot, contexto)
      if (formato === 'excel') {
        descargarBlob(await generarExcel(modelo), nombreDeArchivo(contexto, 'xlsx'))
      } else {
        descargarBlob(await generarPdf(modelo), nombreDeArchivo(contexto, 'pdf'))
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'No se pudo generar el archivo.')
    } finally {
      setPendiente(null)
    }
  }

  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
      <Boton type="button" disabled={pendiente !== null} onClick={() => void exportar('excel')}>
        {pendiente === 'excel' ? 'Generando Excel…' : 'Descargar Excel'}
      </Boton>
      <Boton type="button" disabled={pendiente !== null} onClick={() => void exportar('pdf')}>
        {pendiente === 'pdf' ? 'Generando PDF…' : 'Descargar PDF'}
      </Boton>
      {error && (
        <span role="alert" style={{ fontSize: 11, color: 'var(--neg)' }}>
          {error}
        </span>
      )}
    </div>
  )
}
