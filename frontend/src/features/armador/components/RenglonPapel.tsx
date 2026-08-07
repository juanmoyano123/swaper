/**
 * Un papel dentro de un mes de la grilla, en una sola línea — GWT-4 de la spec.
 *
 * El renglón entero es el botón. Clickearlo entra o saca el papel de la cartera del store
 * (`alternarPapel`), y como cada mes en el que el papel paga pinta su propio `RenglonPapel` contra
 * el mismo `pos`, la iluminación multi-mes (GWT-1/GWT-2) sale sola: no hay acá ningún cálculo de
 * "en qué otros meses está este ticker".
 */

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtPct, SIN_DATO } from '@/lib/fmt'

import type { InstrumentoDelMes } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

export function RenglonPapel({ instrumento }: { instrumento: InstrumentoDelMes }) {
  const { pos } = useArmador()
  const { alternarPapel } = useArmadorAcciones()
  const seleccionado = pos.some((p) => p.ticker === instrumento.ticker)

  // Sólo el año: es lo que la spec pide en el renglón colapsado. La fecha completa está en la
  // tarjeta del detalle del mes.
  const anioVencimiento = instrumento.vencimiento?.slice(0, 4) ?? null

  return (
    <button
      type="button"
      onClick={() => alternarPapel(instrumento.ticker)}
      aria-pressed={seleccionado}
      className="mono"
      title={`${instrumento.ticker} · ${instrumento.emision}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        width: '100%',
        fontSize: 10.5,
        padding: '3px 5px',
        borderRadius: 3,
        border: 'none',
        borderLeft: seleccionado ? '2px solid var(--ac)' : '2px solid transparent',
        background: seleccionado ? 'var(--sel)' : 'transparent',
        color: 'var(--tx)',
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {instrumento.ticker}
      </span>
      <span style={{ color: 'var(--dim)', flexShrink: 0 }}>{instrumento.moneda}</span>
      <span style={{ color: 'var(--ac2)', flexShrink: 0 }}>{fmtPct(instrumento.pct_renta * 100)}</span>
      <span style={{ color: 'var(--dim)', marginLeft: 'auto', flexShrink: 0 }}>
        {instrumento.rendimiento === null
          ? SIN_DATO
          : `${fmtPct(instrumento.rendimiento * 100)} ${unidadDeNaturaleza(instrumento.naturaleza)}`}
      </span>
      <span style={{ color: 'var(--sd)', flexShrink: 0 }}>{anioVencimiento ?? SIN_DATO}</span>
    </button>
  )
}
