/**
 * Las alertas de `/api/v1/calendario/universo`, tal cual — sin colapsar, sin filtrar, sin umbral.
 *
 * Hoy la grilla cubre 70 de 431 emisiones (`cobertura_del_calendario`), y esa alerta llega acá con
 * el resto: el mensaje ya está redactado por el backend para decir el hecho con nombre y apellido,
 * y no se reescribe. El color es lo único que decide la severidad, mismo criterio que la barra de
 * F-013 — nunca un fondo teñido a lo ancho, que enseñaría a ignorarlo.
 */

import type { AlertaCalendario, SeveridadCalendario } from '../lib/schema'

const COLOR: Record<SeveridadCalendario, string> = {
  error: 'var(--neg)',
  advertencia: 'var(--ac2)',
  info: 'var(--dim)',
}

export function AlertasCalendario({ alertas }: { alertas: AlertaCalendario[] }) {
  if (alertas.length === 0) return null

  return (
    <div style={{ display: 'grid', gap: 6, marginTop: 12 }}>
      {alertas.map((alerta) => (
        <div
          key={alerta.codigo}
          style={{
            borderLeft: `2px solid ${COLOR[alerta.severidad]}`,
            background: 'var(--pan2)',
            borderRadius: '0 3px 3px 0',
            padding: '7px 10px',
          }}
        >
          <p style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
            {alerta.mensaje}
          </p>
          {alerta.accion_requerida !== null && (
            <p style={{ margin: '4px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>
              {alerta.accion_requerida}
            </p>
          )}
          <p className="mono" style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--sd)' }}>
            {alerta.codigo}
          </p>
        </div>
      ))}
    </div>
  )
}
