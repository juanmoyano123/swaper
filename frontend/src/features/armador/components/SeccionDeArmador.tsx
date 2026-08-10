/**
 * Encabezado de una sección de la página del Armador — refinamiento visual posterior a la Tanda 12.
 *
 * No es una tarjeta: es el rótulo que agrupa un tramo de la página sobre `--bg`. Las tarjetas
 * (`Panel`, o los `<section>` que arman su propio contenedor) van adentro, y por eso contrastan —
 * `--pan` sobre `--bg`, nunca `--pan` sobre `--pan`. Ver el docstring de `ArmadorPage.tsx` para la
 * regla completa de sección/tarjeta/sub-tarjeta.
 */
import type { ReactNode } from 'react'

export function SeccionDeArmador({
  rotulo,
  bajada,
  children,
}: {
  rotulo: string
  bajada?: string
  children: ReactNode
}) {
  return (
    <section aria-label={rotulo} style={{ display: 'grid', gap: 12 }}>
      <header>
        <h2
          className="rotulo"
          style={{ margin: 0, fontSize: 12, letterSpacing: '0.13em', color: 'var(--tx)' }}
        >
          {rotulo}
        </h2>
        {bajada && <p style={{ margin: '3px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>{bajada}</p>}
      </header>
      {children}
    </section>
  )
}
