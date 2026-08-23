/**
 * La ficha de un FCI como panel superpuesto — F-057, mismo patrón que `InstrumentoDrawer.tsx`.
 */

import { useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { FichaFciContenido } from './FichaFciContenido'

export function FichaFciDrawer() {
  const { codigoCafci } = useParams<{ codigoCafci: string }>()
  const navigate = useNavigate()

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
      aria-label={`Ficha del fondo ${codigoCafci ?? ''}`}
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
        <h2 style={{ font: '15px/1.3 inherit', margin: 0 }}>Fondo común</h2>
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
        <FichaFciContenido codigoCafci={codigoCafci ?? null} />
      </div>
    </aside>
  )
}
