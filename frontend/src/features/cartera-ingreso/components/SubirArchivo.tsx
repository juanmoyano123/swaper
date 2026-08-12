/** Selector de archivo para la segunda vía: un CSV o un Excel exportado del sistema del banco. */

import type { ChangeEvent } from 'react'

import { BotonAccion } from './BotonAccion'

export function SubirArchivo({
  onArchivo,
  onVolver,
}: {
  onArchivo: (archivo: File) => void
  onVolver: () => void
}) {
  function alElegir(evento: ChangeEvent<HTMLInputElement>) {
    const archivo = evento.target.files?.[0]
    // Limpiar el input: si el asesor sube el mismo archivo dos veces seguidas (por ejemplo, tras
    // corregirlo afuera), el segundo `change` tiene que disparar igual.
    evento.target.value = ''
    if (archivo) onArchivo(archivo)
  }

  return (
    <div>
      <label
        htmlFor="archivo-cartera"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 4,
          padding: '28px 16px',
          border: '1px dashed var(--sd)',
          borderRadius: 4,
          background: 'var(--pan2)',
          cursor: 'pointer',
          textAlign: 'center',
        }}
      >
        <span style={{ fontSize: 13, color: 'var(--tx)' }}>Elegir un archivo CSV o Excel (.xlsx)</span>
        <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>
          Si las columnas no vienen en el orden esperado, se va a pedir el mapeo.
        </span>
        <input
          id="archivo-cartera"
          aria-label="Archivo de cartera"
          type="file"
          accept=".csv,.xlsx,.xls,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={alElegir}
          style={{
            position: 'absolute',
            width: 1,
            height: 1,
            padding: 0,
            margin: -1,
            overflow: 'hidden',
            clip: 'rect(0,0,0,0)',
            border: 0,
          }}
        />
      </label>
      <div style={{ marginTop: 10 }}>
        <BotonAccion onClick={onVolver}>Volver</BotonAccion>
      </div>
    </div>
  )
}
