/**
 * Los paneles de mes de la grilla-selector — diseño A2 sobre la vista colapsada del universo.
 *
 * `/api/v1/calendario/universo` no trae montos: cada panel es un mes con la lista de papeles que
 * pagan ahí, no una barra de plata (esa vista existe recién con una cartera concreta, F-021). Clic
 * en el encabezado de un mes lo sincroniza con la cordillera (F-021, `PanelRentaCordillera`
 * comparte el mismo `selMes`); clic en una tarjeta la entra o saca de la cartera — ver
 * `TarjetaPapel` para la iluminación multi-mes.
 *
 * **08/08/2026: reemplaza la grilla de doce columnas angostas de una línea + el panel de detalle
 * aparte (`DetalleMes`, retirado).** El contenido de un papel (ticker, cupón, TIR rotulada,
 * vencimiento) no entraba legible en un doceavo del ancho de la pantalla: desbordaba una columna
 * encima de la vecina. Ahora los paneles se acomodan en una grilla responsive (`auto-fill`, sin
 * cantidad fija de columnas) y las tarjetas — ya con el detalle que antes sólo se veía al abrir el
 * mes — quedan siempre visibles, apiladas dentro de cada panel.
 */

import type { MesDelCalendario } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

import { TarjetaPapel } from './TarjetaPapel'

export function GrillaDoceMeses({
  meses,
  calificacionPorTicker,
}: {
  meses: MesDelCalendario[]
  /** Calificación declarada por ticker, del cruce contra el universo — `undefined` si el ticker
   *  no cruzó, `null` si cruzó pero la fuente no la informó. Se muestra siempre, filtre o no. */
  calificacionPorTicker: Map<string, string | null>
}) {
  const { selMes } = useArmador()
  const { alternarMes } = useArmadorAcciones()

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
        gap: 10,
        alignItems: 'start',
      }}
    >
      {meses.map((mes, indice) => (
        <PanelMes
          key={mes.etiqueta}
          mes={mes}
          seleccionado={selMes === indice}
          onSeleccionar={() => alternarMes(indice)}
          calificacionPorTicker={calificacionPorTicker}
        />
      ))}
    </div>
  )
}

function PanelMes({
  mes,
  seleccionado,
  onSeleccionar,
  calificacionPorTicker,
}: {
  mes: MesDelCalendario
  seleccionado: boolean
  onSeleccionar: () => void
  calificacionPorTicker: Map<string, string | null>
}) {
  return (
    <div
      style={{
        background: seleccionado ? 'var(--sel)' : 'transparent',
        borderRadius: 4,
        padding: '5px 3px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minWidth: 0,
      }}
    >
      <button
        type="button"
        onClick={onSeleccionar}
        aria-pressed={seleccionado}
        style={{
          font: `${seleccionado ? 700 : 600} 11px/1.25 inherit`,
          // El mes seleccionado va en --ac; el mes sin ningún pago en el universo se distingue en
          // --dim aunque no esté seleccionado — son dos estados distintos y no se pisan (GWT-3).
          color: seleccionado ? 'var(--ac)' : mes.sin_renta ? 'var(--dim)' : 'var(--tx)',
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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {mes.instrumentos.map((instrumento) => (
          <TarjetaPapel
            key={instrumento.ticker}
            instrumento={instrumento}
            calificacion={calificacionPorTicker.get(instrumento.ticker)}
          />
        ))}
      </div>
    </div>
  )
}
