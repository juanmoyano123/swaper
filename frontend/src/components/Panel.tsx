/** Contenedor base de todo bloque de contenido: fondo, borde de 1 px y un rótulo opcional. */

import type { ReactNode } from 'react'

export function Panel({
  rotulo,
  titulo,
  acciones,
  children,
  className,
  ariaLabel,
}: {
  /** Rótulo en mayúsculas del design system, en color de acento. */
  rotulo?: string
  titulo?: ReactNode
  acciones?: ReactNode
  children?: ReactNode
  className?: string
  /** Nombre accesible del `<section>`, para paneles que ya lo declaraban a mano antes de migrar acá. */
  ariaLabel?: string
}) {
  return (
    <section
      className={className}
      aria-label={ariaLabel}
      style={{
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: '12px 16px',
      }}
    >
      {(rotulo || titulo || acciones) && (
        <header
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            gap: 12,
            marginBottom: children ? 10 : 0,
          }}
        >
          <div>
            {rotulo && <div className="rotulo">{rotulo}</div>}
            {titulo && <h2 style={{ font: '600 15px/1.3 inherit', margin: '2px 0 0' }}>{titulo}</h2>}
          </div>
          {acciones}
        </header>
      )}
      {children}
    </section>
  )
}
