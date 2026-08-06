/** Encabezado común de las pantallas: título, bajada de una línea y el contenido debajo. */

import type { ReactNode } from 'react'

export function Pantalla({
  titulo,
  bajada,
  children,
}: {
  titulo: ReactNode
  bajada?: string
  children?: ReactNode
}) {
  return (
    <div style={{ padding: '14px 18px' }}>
      <header style={{ marginBottom: 12 }}>
        <h1 style={{ font: '600 17px/1.25 inherit', margin: 0, letterSpacing: '-0.01em' }}>
          {titulo}
        </h1>
        {bajada && (
          <p style={{ margin: '4px 0 0', fontSize: 12.5, color: 'var(--dim)', textWrap: 'pretty' }}>
            {bajada}
          </p>
        )}
      </header>
      {children}
    </div>
  )
}
