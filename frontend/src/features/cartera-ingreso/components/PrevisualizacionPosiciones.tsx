/**
 * El paso obligatorio de las tres vías: mostrar lo que el sistema entendió antes de confirmar.
 *
 * Las filas inválidas se muestran igual que las válidas, con su motivo al lado — no desaparecen de
 * la lista. Ocultarlas sería la misma falta que descartarlas en silencio.
 */

import { fmtNumero } from '@/lib/fmt'

import type { PosicionCruda, ViaIngreso } from '../types'

import { BotonAccion } from './BotonAccion'

const NOMBRE_VIA: Record<ViaIngreso, string> = {
  portapapeles: 'pegado desde el portapapeles',
  archivo: 'archivo subido',
  manual: 'carga manual',
}

export function PrevisualizacionPosiciones({
  origen,
  posiciones,
  onConfirmar,
  onVolver,
}: {
  origen: ViaIngreso
  posiciones: PosicionCruda[]
  onConfirmar: () => void
  onVolver: () => void
}) {
  const invalidas = posiciones.filter((p) => !p.valida).length

  return (
    <div>
      <p style={{ margin: '0 0 10px', fontSize: 12.5, color: 'var(--dim)' }}>
        Se leyeron <strong style={{ color: 'var(--tx)' }}>{posiciones.length}</strong>{' '}
        {posiciones.length === 1 ? 'fila' : 'filas'} del {NOMBRE_VIA[origen]}
        {invalidas > 0 && (
          <>
            {', '}
            <span style={{ color: 'var(--neg)' }}>
              {invalidas} {invalidas === 1 ? 'inválida' : 'inválidas'}
            </span>
          </>
        )}
        {'. Revisá antes de confirmar.'}
      </p>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr>
              {['Fila', 'Ticker', 'Nominal', 'Monto', 'Estado'].map((columna, i) => (
                <th
                  key={columna}
                  style={{
                    textAlign: i >= 2 && i <= 3 ? 'right' : 'left',
                    padding: '5px 8px',
                    fontSize: 10.5,
                    color: 'var(--dim)',
                    fontWeight: 400,
                    borderBottom: '1px solid var(--lin)',
                  }}
                >
                  {columna}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {posiciones.map((p) => (
              <tr
                key={p.id}
                style={{ background: p.valida ? undefined : 'color-mix(in srgb, var(--neg) 8%, transparent)' }}
              >
                <td className="mono" style={{ padding: '5px 8px', fontSize: 11, color: 'var(--dim)' }}>
                  {p.fila}
                </td>
                <td className="mono" style={{ padding: '5px 8px', fontSize: 12 }}>
                  {p.tickerDeclarado || <span style={{ color: 'var(--neg)' }}>(sin ticker)</span>}
                </td>
                <td className="mono" style={{ padding: '5px 8px', fontSize: 12, textAlign: 'right' }}>
                  {fmtNumero(p.nominal)}
                </td>
                <td className="mono" style={{ padding: '5px 8px', fontSize: 12, textAlign: 'right' }}>
                  {fmtNumero(p.monto)}
                </td>
                <td style={{ padding: '5px 8px', fontSize: 11 }}>
                  {p.valida ? (
                    <span style={{ color: 'var(--pos)' }}>válida</span>
                  ) : (
                    <span style={{ color: 'var(--neg)' }}>{p.motivo}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <BotonAccion variante="primario" onClick={onConfirmar}>
          Confirmar cartera
        </BotonAccion>
        <BotonAccion onClick={onVolver}>Volver a cargar</BotonAccion>
      </div>
    </div>
  )
}
