/** Las tres puertas de entrada del Flujo B, para elegir por dónde entra la cartera del cliente. */

import type { ViaIngreso } from '../types'

const OPCIONES: { via: ViaIngreso; titulo: string; detalle: string }[] = [
  {
    via: 'portapapeles',
    titulo: 'Pegar desde el portapapeles',
    detalle: 'El formato en que llega el resumen de cuenta.',
  },
  {
    via: 'archivo',
    titulo: 'Subir un CSV o Excel',
    detalle: 'Si las columnas no vienen en el orden esperado, se pide el mapeo.',
  },
  {
    via: 'manual',
    titulo: 'Cargar posición por posición',
    detalle: 'A mano, una fila a la vez.',
  },
]

export function SelectorVia({ onElegir }: { onElegir: (via: ViaIngreso) => void }) {
  return (
    <div>
      <p style={{ margin: '0 0 14px', fontSize: 13.5, color: 'var(--tx)' }}>
        No hay ninguna cartera cargada. Elegí cómo entra.
      </p>
      <div style={{ display: 'grid', gap: 8 }}>
        {OPCIONES.map(({ via, titulo, detalle }) => (
          <button
            key={via}
            type="button"
            onClick={() => onElegir(via)}
            style={{
              display: 'block',
              width: '100%',
              textAlign: 'left',
              font: 'inherit',
              padding: '10px 12px',
              borderRadius: 4,
              border: '1px solid var(--lin)',
              background: 'var(--pan2)',
              color: 'var(--tx)',
              cursor: 'pointer',
            }}
          >
            <span style={{ fontSize: 13, fontWeight: 600 }}>{titulo}</span>
            <span style={{ display: 'block', marginTop: 2, fontSize: 11.5, color: 'var(--dim)' }}>
              {detalle}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
