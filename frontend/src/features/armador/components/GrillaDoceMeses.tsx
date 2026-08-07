/**
 * Las doce columnas de la grilla-selector — diseño A2 sobre la vista colapsada del universo.
 *
 * `/api/v1/calendario/universo` no trae montos: cada columna es un mes con la lista de papeles que
 * pagan ahí, no una barra de plata (esa vista existe recién con una cartera concreta, F-021). Clic
 * en un mes lo abre en `DetalleMes`; clic en un papel lo entra o saca de la cartera — ver
 * `RenglonPapel` para la iluminación multi-mes.
 */

import type { MesDelCalendario } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

import { RenglonPapel } from './RenglonPapel'

export function GrillaDoceMeses({ meses }: { meses: MesDelCalendario[] }) {
  const { selMes } = useArmador()
  const { alternarMes } = useArmadorAcciones()

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${meses.length}, minmax(0, 1fr))`,
        gap: 8,
        alignItems: 'start',
      }}
    >
      {meses.map((mes, indice) => (
        <ColumnaMes
          key={mes.etiqueta}
          mes={mes}
          seleccionada={selMes === indice}
          onSeleccionar={() => alternarMes(indice)}
        />
      ))}
    </div>
  )
}

function ColumnaMes({
  mes,
  seleccionada,
  onSeleccionar,
}: {
  mes: MesDelCalendario
  seleccionada: boolean
  onSeleccionar: () => void
}) {
  return (
    <div
      style={{
        background: seleccionada ? 'var(--sel)' : 'transparent',
        borderRadius: 4,
        padding: '5px 3px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
        minWidth: 0,
      }}
    >
      <button
        type="button"
        onClick={onSeleccionar}
        aria-pressed={seleccionada}
        style={{
          font: `${seleccionada ? 700 : 600} 11px/1.25 inherit`,
          // El mes seleccionado va en --ac; el mes sin ningún pago en el universo se distingue en
          // --dim aunque no esté seleccionado — son dos estados distintos y no se pisan (GWT-3).
          color: seleccionada ? 'var(--ac)' : mes.sin_renta ? 'var(--dim)' : 'var(--tx)',
          background: 'none',
          border: 'none',
          padding: '2px 3px 4px',
          cursor: 'pointer',
          textAlign: 'left',
          width: '100%',
        }}
      >
        {mes.nombre}
        <span
          className="mono"
          style={{ display: 'block', fontSize: 9.5, color: 'var(--dim)', fontWeight: 400, marginTop: 1 }}
        >
          {mes.sin_renta ? 'sin pagos en el universo' : `${mes.con_renta} pagan`}
        </span>
      </button>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {mes.instrumentos.map((instrumento) => (
          <RenglonPapel key={instrumento.ticker} instrumento={instrumento} />
        ))}
      </div>
    </div>
  )
}
