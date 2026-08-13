/**
 * El control para reordenar las secciones del armador.
 *
 * **Flechas y no drag & drop.** Un drag necesita puntero fino y no tiene equivalente de teclado sin
 * construirle uno aparte; dos botones son operables con teclado y lector de pantalla desde el
 * primer día, y para seis elementos el costo de usarlos es un clic por posición. Si algún día son
 * quince, se reevalúa.
 *
 * Se abre y se cierra: reordenar es algo que se hace una vez cada tanto, y dejar doce botones
 * permanentes arriba de la pantalla le robaría espacio al trabajo de todos los días.
 */

import { useState } from 'react'

import type { SeccionId } from '../lib/plegado'
import { SECCION_POR_ID } from '../lib/secciones'
import { useOrdenSecciones } from '../hooks/useOrdenSecciones'

export function OrdenDeSecciones() {
  const { orden, mover, restaurar, esDeFabrica } = useOrdenSecciones()
  const [abierto, setAbierto] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-start' }}>
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        style={estiloBotonPrincipal}
      >
        {abierto ? '▴ listo' : '▾ Ordenar secciones'}
      </button>

      {abierto && (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 4,
            padding: 10,
            borderRadius: 3,
            border: '1px solid var(--lin)',
            background: 'var(--pan)',
            minWidth: 280,
          }}
        >
          <p style={{ margin: '0 0 4px', fontSize: 11, color: 'var(--dim)' }}>
            El orden queda guardado en este navegador.
          </p>
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 4 }}>
            {orden.map((id, i) => {
              const seccion = SECCION_POR_ID.get(id)
              if (seccion === undefined) return null
              return (
                <li
                  key={id}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12 }}
                >
                  <span
                    aria-hidden
                    style={{
                      width: 3,
                      alignSelf: 'stretch',
                      background: seccion.acento,
                      borderRadius: 2,
                    }}
                  />
                  <span style={{ flex: 1 }}>{seccion.rotulo}</span>
                  <BotonMover
                    etiqueta={`Subir ${seccion.rotulo}`}
                    simbolo="▲"
                    deshabilitado={i === 0}
                    onClick={() => mover(id, 'arriba')}
                  />
                  <BotonMover
                    etiqueta={`Bajar ${seccion.rotulo}`}
                    simbolo="▼"
                    deshabilitado={i === orden.length - 1}
                    onClick={() => mover(id, 'abajo')}
                  />
                </li>
              )
            })}
          </ul>
          {!esDeFabrica && (
            <button
              type="button"
              onClick={restaurar}
              style={{ ...estiloBotonPrincipal, marginTop: 6, alignSelf: 'flex-start' }}
            >
              Restaurar orden original
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function BotonMover({
  etiqueta,
  simbolo,
  deshabilitado,
  onClick,
}: {
  etiqueta: string
  simbolo: string
  deshabilitado: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={deshabilitado}
      aria-label={etiqueta}
      style={{
        font: 'inherit',
        fontSize: 11,
        lineHeight: 1,
        padding: '4px 7px',
        borderRadius: 3,
        border: '1px solid var(--lin)',
        background: 'var(--pan2)',
        color: deshabilitado ? 'var(--lin)' : 'var(--tx)',
        cursor: deshabilitado ? 'default' : 'pointer',
      }}
    >
      {simbolo}
    </button>
  )
}

const estiloBotonPrincipal = {
  font: 'inherit',
  fontSize: 11.5,
  padding: '5px 10px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
  cursor: 'pointer',
} as const
