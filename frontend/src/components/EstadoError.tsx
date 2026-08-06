/**
 * La traducción única del contrato de error de la API a algo que se pueda leer en pantalla.
 *
 * Ninguna feature escribe su propio estado de error: van todas por acá. Así el mensaje que ve el
 * asesor es siempre el que mandó el backend, y el `request_id` —que existe justamente para rastrear
 * un error en los logs— llega hasta la pantalla en vez de quedarse en la consola.
 */

import { ApiError, mensajeParaUsuario } from '@/lib/api/errors'

export function EstadoError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const esApi = error instanceof ApiError
  const codigo = esApi ? error.code : null
  const requestId = esApi ? error.requestId : null

  return (
    <div
      role="alert"
      style={{
        border: '1px solid var(--neg)',
        borderLeftWidth: 3,
        borderRadius: 4,
        background: 'var(--pan)',
        padding: '12px 14px',
        maxWidth: '62ch',
      }}
    >
      <p style={{ margin: 0, fontSize: 13.5, color: 'var(--tx)', textWrap: 'pretty' }}>
        {mensajeParaUsuario(error)}
      </p>

      {(codigo || requestId) && (
        <p className="mono" style={{ margin: '8px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>
          {codigo}
          {requestId && (
            <>
              {' · '}código de soporte: {requestId}
            </>
          )}
        </p>
      )}

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          style={{
            marginTop: 10,
            font: 'inherit',
            fontSize: 12,
            padding: '5px 11px',
            borderRadius: 3,
            border: '1px solid var(--lin)',
            background: 'transparent',
            color: 'var(--tx)',
            cursor: 'pointer',
          }}
        >
          Reintentar
        </button>
      )}
    </div>
  )
}
