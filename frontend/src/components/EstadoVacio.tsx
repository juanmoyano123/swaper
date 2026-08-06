/**
 * Cuando no hay nada que mostrar, se dice por qué.
 *
 * Una lista vacía sin explicación deja al asesor sin saber si no hay resultados, si el filtro es
 * muy angosto o si el dato nunca llegó. Son tres cosas distintas y llevan a acciones distintas.
 */

import type { ReactNode } from 'react'

export function EstadoVacio({ titulo, detalle }: { titulo: string; detalle?: ReactNode }) {
  return (
    <div style={{ padding: '22px 0', maxWidth: '62ch' }}>
      <p style={{ margin: 0, fontSize: 13.5, color: 'var(--tx)' }}>{titulo}</p>
      {detalle && (
        <p style={{ margin: '6px 0 0', fontSize: 12.5, color: 'var(--dim)', textWrap: 'pretty' }}>
          {detalle}
        </p>
      )}
    </div>
  )
}
