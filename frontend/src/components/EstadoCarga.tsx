/** Cómo se ve una consulta en curso. Una sola forma, para toda la aplicación. */

export function EstadoCarga({ que = 'los datos' }: { que?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className="mono"
      style={{ color: 'var(--dim)', fontSize: 11, padding: '18px 0', animation: 'pulso 1.6s infinite' }}
    >
      Cargando {que}…
    </div>
  )
}
