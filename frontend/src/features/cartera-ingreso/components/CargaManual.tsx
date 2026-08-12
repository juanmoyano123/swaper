/**
 * Tercera vía: cargar la cartera posición por posición.
 *
 * Cada fila pasa por la misma `construirPosiciones` que las otras dos vías —el hook la llama al
 * agregar—, así que un nominal mal escrito a mano se marca inválido con su motivo exactamente
 * igual que uno mal escrito en un CSV. No hay una segunda regla de validación para esta vía.
 */

import { useState } from 'react'
import type { ReactNode } from 'react'

import { fmtNumero } from '@/lib/fmt'

import type { PosicionCruda } from '../types'

import { BotonAccion } from './BotonAccion'

export function CargaManual({
  posiciones,
  onAgregar,
  onQuitar,
  onConfirmar,
  onVolver,
}: {
  posiciones: PosicionCruda[]
  onAgregar: (ticker: string, nominalTexto: string, montoTexto: string) => void
  onQuitar: (id: string) => void
  onConfirmar: () => void
  onVolver: () => void
}) {
  const [ticker, setTicker] = useState('')
  const [nominal, setNominal] = useState('')
  const [monto, setMonto] = useState('')

  function agregar() {
    if (ticker.trim() === '') return
    onAgregar(ticker, nominal, monto)
    setTicker('')
    setNominal('')
    setMonto('')
  }

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 110px 130px auto', gap: 8, alignItems: 'end' }}>
        <Campo etiqueta="Ticker">
          <input
            aria-label="Ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            className="mono"
            style={estiloInput}
          />
        </Campo>
        <Campo etiqueta="Nominal">
          <input
            aria-label="Nominal"
            value={nominal}
            onChange={(e) => setNominal(e.target.value)}
            placeholder="1.000,50"
            className="mono"
            style={estiloInput}
          />
        </Campo>
        <Campo etiqueta="Monto (US$)">
          <input
            aria-label="Monto"
            value={monto}
            onChange={(e) => setMonto(e.target.value)}
            placeholder="1.200,00"
            className="mono"
            style={estiloInput}
          />
        </Campo>
        <BotonAccion variante="primario" onClick={agregar} disabled={ticker.trim() === ''}>
          Agregar
        </BotonAccion>
      </div>

      {posiciones.length > 0 && (
        <ul style={{ listStyle: 'none', margin: '14px 0 0', padding: 0, display: 'grid', gap: 4 }}>
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
                border: p.valida ? '1px solid var(--lin)' : '1px solid var(--neg)',
              }}
            >
              <span className="mono" style={{ fontSize: 12, minWidth: 80 }}>
                {p.tickerDeclarado || '(sin ticker)'}
              </span>
              <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)', flex: 1 }}>
                {p.nominal !== null && `nominal ${fmtNumero(p.nominal)}`}
                {p.nominal !== null && p.monto !== null && ' · '}
                {p.monto !== null && `monto US$ ${fmtNumero(p.monto)}`}
                {!p.valida && <span style={{ color: 'var(--neg)' }}> — {p.motivo}</span>}
              </span>
              <button
                type="button"
                onClick={() => onQuitar(p.id)}
                aria-label={`Quitar ${p.tickerDeclarado || 'la fila'}`}
                style={{
                  font: 'inherit',
                  fontSize: 12,
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--dim)',
                  cursor: 'pointer',
                }}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
        <BotonAccion variante="primario" onClick={onConfirmar} disabled={posiciones.length === 0}>
          Confirmar carga
        </BotonAccion>
        <BotonAccion onClick={onVolver}>Volver</BotonAccion>
      </div>
    </div>
  )
}

const estiloInput = {
  width: '100%',
  font: 'inherit',
  fontSize: 12.5,
  padding: '6px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <label style={{ display: 'block' }}>
      <span style={{ display: 'block', fontSize: 10.5, color: 'var(--dim)', marginBottom: 3 }}>{etiqueta}</span>
      {children}
    </label>
  )
}
