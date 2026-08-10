/**
 * Encabezado de una sección de la página del Armador — refinamiento visual posterior a la Tanda
 * 12, extendido en la Etapa 2 del rediseño con plegado e identidad propia.
 *
 * No es una tarjeta: es el rótulo que agrupa un tramo de la página sobre `--bg`. Las tarjetas
 * (`Panel`, o los `<section>` que arman su propio contenedor) van adentro, y por eso contrastan —
 * `--pan` sobre `--bg`, nunca `--pan` sobre `--pan`. Ver el docstring de `ArmadorPage.tsx` para la
 * regla completa de sección/tarjeta/sub-tarjeta.
 *
 * **Plegado**: cada sección se puede colapsar para enfocarse en una sola sin que las demás
 * inunden la pantalla — el estado vive en `localStorage` (`useSeccionPlegada`, no en el store de
 * la cartera, ver `lib/plegado.ts`) y sobrevive a un refresh. Al plegar, `resumen` sigue visible:
 * es lo que permite saber qué hay adentro sin abrir la sección. El patrón de cabecera-botón +
 * chevron es el mismo que `BarraEstadoDato.tsx` ya usaba para su detalle.
 *
 * **Identidad**: el borde izquierdo de 3px en `acento` (un `--catN` de la paleta categórica) es la
 * separación visual entre secciones que antes no existía — cada una se reconoce por su color de
 * borde antes de leer el rótulo.
 */
import type { ReactNode } from 'react'

import type { SeccionId } from '../lib/plegado'
import { useSeccionPlegada } from '../hooks/useSeccionPlegada'

export function SeccionDeArmador({
  id,
  rotulo,
  bajada,
  acento,
  resumen,
  children,
}: {
  id: SeccionId
  rotulo: string
  bajada?: string
  /** Color de identidad de la sección — un `var(--catN)` de la paleta categórica de `index.css`. */
  acento: string
  /** Resumen de una línea, visible aunque la sección esté plegada. */
  resumen?: ReactNode
  children: ReactNode
}) {
  const [plegada, alternar] = useSeccionPlegada(id)
  const idContenido = `seccion-armador-${id}`

  return (
    <section
      aria-label={rotulo}
      style={{
        display: 'grid',
        gap: 12,
        borderLeft: `3px solid ${acento}`,
        paddingLeft: 14,
      }}
    >
      <header>
        <button
          type="button"
          onClick={alternar}
          aria-expanded={!plegada}
          aria-controls={idContenido}
          style={{
            display: 'flex',
            alignItems: 'baseline',
            justifyContent: 'space-between',
            gap: 12,
            width: '100%',
            font: 'inherit',
            background: 'none',
            border: 'none',
            padding: 0,
            cursor: 'pointer',
            textAlign: 'left',
          }}
        >
          <span>
            <span
              className="rotulo"
              style={{ fontSize: 12, letterSpacing: '0.13em', color: 'var(--tx)' }}
            >
              {rotulo}
            </span>
            {bajada && !plegada && (
              <p style={{ margin: '3px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>
                {bajada}
              </p>
            )}
            {plegada && resumen && (
              <p className="mono" style={{ margin: '3px 0 0', fontSize: 11, color: 'var(--dim)' }}>
                {resumen}
              </p>
            )}
          </span>
          <span
            aria-hidden
            className="mono"
            style={{ fontSize: 11, color: 'var(--dim)', whiteSpace: 'nowrap', flexShrink: 0 }}
          >
            {plegada ? '▾ mostrar' : '▴ ocultar'}
          </span>
        </button>
      </header>
      {!plegada && <div id={idContenido}>{children}</div>}
    </section>
  )
}
