/**
 * Red de contención para los errores de render.
 *
 * Cubre los bugs de la interfaz, no los fallos de datos: esos los muestra cada vista con
 * `EstadoError` en el lugar donde iban los datos, que es información mucho más útil que una
 * pantalla entera de error. Lo que este boundary evita es la pantalla en blanco.
 */

import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = { children: ReactNode }
type Estado = { error: Error | null }

export class ErrorBoundary extends Component<Props, Estado> {
  state: Estado = { error: null }

  static getDerivedStateFromError(error: Error): Estado {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Queda en la consola del navegador para poder depurarlo; el usuario ve el panel de abajo.
    console.error('Error de render no controlado:', error, info.componentStack)
  }

  render(): ReactNode {
    if (!this.state.error) return this.props.children

    return (
      <div style={{ padding: 24, maxWidth: '62ch' }}>
        <div
          role="alert"
          style={{
            border: '1px solid var(--neg)',
            borderLeftWidth: 3,
            borderRadius: 4,
            background: 'var(--pan)',
            padding: '14px 16px',
          }}
        >
          <h1 style={{ font: '600 15px/1.3 inherit', margin: 0 }}>Algo se rompió en la interfaz</h1>
          <p style={{ margin: '8px 0 0', fontSize: 12.5, color: 'var(--dim)', textWrap: 'pretty' }}>
            El error quedó registrado en la consola del navegador. Recargar la página deja la
            aplicación en un estado limpio.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              marginTop: 12,
              font: 'inherit',
              fontSize: 12,
              padding: '5px 11px',
              borderRadius: 3,
              border: '1px solid var(--ac)',
              background: 'var(--ac)',
              color: 'var(--bg)',
              cursor: 'pointer',
            }}
          >
            Recargar
          </button>
        </div>
      </div>
    )
  }
}
