/**
 * El final de F-028: la lista quedó confirmada, cruda todavía.
 *
 * A propósito no hay acá ni un instrumento resuelto, ni una emisión, ni un plazo de liquidación —
 * eso es F-029, que arranca de esta misma lista. Mostrar algo más que el ticker declarado y el
 * monto sería inventar una resolución que todavía no pasó.
 */

import { fmtNumero } from '@/lib/fmt'

import type { PosicionCruda } from '../types'

import { BotonAccion } from './BotonAccion'

export function CarteraConfirmada({
  posiciones,
  onCargarOtra,
}: {
  posiciones: PosicionCruda[]
  onCargarOtra: () => void
}) {
  const invalidas = posiciones.filter((p) => !p.valida).length

  return (
    <div>
      <p style={{ margin: '0 0 10px', fontSize: 12.5, color: 'var(--dim)' }}>
        Cartera cargada: {posiciones.length} {posiciones.length === 1 ? 'posición' : 'posiciones'}
        {invalidas > 0 && (
          <span style={{ color: 'var(--neg)' }}>
            {' '}
            ({invalidas} sin resolver hasta corregirla)
          </span>
        )}
        {'. Lista para que F-029 resuelva cada ticker contra el universo.'}
      </p>

      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
        {posiciones.map((p) => (
          <li
            key={p.id}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '5px 8px',
              borderRadius: 3,
              background: 'var(--pan2)',
            }}
          >
            <span className="mono" style={{ fontSize: 12, minWidth: 90 }}>
              {p.tickerDeclarado || '(sin ticker)'}
            </span>
            <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)', flex: 1 }}>
              {p.nominal !== null && `nominal ${fmtNumero(p.nominal)}`}
              {p.nominal !== null && p.monto !== null && ' · '}
              {p.monto !== null && `monto US$ ${fmtNumero(p.monto)}`}
            </span>
            {!p.valida && <span style={{ fontSize: 11, color: 'var(--neg)' }}>{p.motivo}</span>}
          </li>
        ))}
      </ul>

      <div style={{ marginTop: 14 }}>
        <BotonAccion onClick={onCargarOtra}>Cargar otra cartera</BotonAccion>
      </div>
    </div>
  )
}
