/**
 * La ficha como panel superpuesto, sobre la pantalla desde la que se la abrió.
 *
 * Se monta solo cuando se llegó navegando desde adentro de la aplicación. Entrar por un link
 * compartido o recargar cae en la página completa, que es el comportamiento correcto: sin pantalla
 * de fondo, un panel flotando sobre el vacío no tendría sentido.
 */

import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { FichaDelActivo } from './FichaDelActivo'

export function InstrumentoDrawer() {
  const { ticker } = useParams<{ ticker: string }>()
  const navigate = useNavigate()

  // Volver atrás en el historial, y no navegar a una ruta fija: así la pantalla de fondo reaparece
  // con su estado y su scroll donde estaban.
  const cerrar = () => navigate(-1)

  useEffect(() => {
    const alPresionar = (evento: KeyboardEvent) => {
      if (evento.key === 'Escape') navigate(-1)
    }
    document.addEventListener('keydown', alPresionar)
    return () => document.removeEventListener('keydown', alPresionar)
  }, [navigate])

  return (
    <aside
      role="dialog"
      aria-modal="true"
      aria-label={`Ficha de ${ticker ?? 'instrumento'}`}
      style={{
        position: 'fixed',
        top: 52,
        right: 0,
        bottom: 0,
        width: 430,
        maxWidth: '100vw',
        zIndex: 50,
        background: 'var(--pan)',
        borderLeft: '1px solid var(--ac)',
        boxShadow: '-16px 0 40px rgba(0, 0, 0, 0.35)',
        overflowY: 'auto',
      }}
    >
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 1,
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          gap: 12,
          padding: '12px 14px',
          background: 'var(--pan)',
          borderBottom: '1px solid var(--lin)',
        }}
      >
        <h2 className="mono" style={{ font: '20px/1.2 ui-monospace, monospace', margin: 0 }}>
          {ticker}
        </h2>
        <button
          type="button"
          onClick={cerrar}
          aria-label="Cerrar la ficha"
          style={{
            font: 'inherit',
            fontSize: 14,
            width: 26,
            height: 26,
            borderRadius: 3,
            border: '1px solid var(--lin)',
            background: 'transparent',
            color: 'var(--dim)',
            cursor: 'pointer',
          }}
        >
          ✕
        </button>
      </header>

      <div style={{ padding: 14 }}>
        <FichaDelActivo ticker={ticker} />
      </div>
    </aside>
  )
}
