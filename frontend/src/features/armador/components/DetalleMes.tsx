/**
 * El panel de detalle de un mes — diseño A5, visible cuando hay un mes seleccionado en la grilla.
 *
 * Recibe los doce meses completos y no sólo el elegido: cada tarjeta necesita cruzar su ticker
 * contra la ventana entera para dos cosas que no se pueden sacar del mes solo — el mini-calendario
 * de doce celdas y "en cuántos meses paga".
 */

import { MiniCalendario, type CeldaMes } from '@/components/MiniCalendario'
import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtFecha, fmtPct, SIN_DATO } from '@/lib/fmt'

import type { InstrumentoDelMes, MesDelCalendario } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

export function DetalleMes({ meses }: { meses: MesDelCalendario[] }) {
  const { selMes } = useArmador()
  if (selMes === null) return null

  const mes = meses[selMes]
  // `selMes` es un índice armado por esta misma pantalla (`alternarMes`) contra este mismo array,
  // así que fuera de rango sería un bug de programación y no un estado de datos a manejar.
  if (!mes) return null

  return (
    <div
      style={{
        border: '1px solid var(--ac)',
        borderRadius: 4,
        padding: '12px 16px',
        marginTop: 10,
      }}
    >
      <header style={{ marginBottom: 10 }}>
        <h3 style={{ font: '600 15px/1.3 inherit', margin: 0, color: 'var(--ac)' }}>{mes.nombre}</h3>
        <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--dim)' }}>
          {mes.con_renta === 0
            ? 'ningún papel del universo paga renta este mes'
            : `${mes.con_renta} papeles del universo pagan renta`}
        </p>
      </header>

      {mes.instrumentos.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Sin instrumentos que paguen en este mes.
        </p>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(232px, 1fr))',
            gap: 10,
          }}
        >
          {mes.instrumentos.map((instrumento) => (
            <TarjetaPapel key={instrumento.ticker} instrumento={instrumento} meses={meses} />
          ))}
        </div>
      )}
    </div>
  )
}

function TarjetaPapel({
  instrumento,
  meses,
}: {
  instrumento: InstrumentoDelMes
  meses: MesDelCalendario[]
}) {
  const { pos } = useArmador()
  const { alternarPapel } = useArmadorAcciones()
  const seleccionado = pos.some((p) => p.ticker === instrumento.ticker)

  // Doce celdas, una por mes de la ventana, cruzando este ticker contra cada mes: es la misma
  // lógica que hace que la iluminación de `RenglonPapel` salga sola, aplicada acá al calendario.
  const celdas: CeldaMes[] = meses.map((mesDeLaVentana) => {
    const pagaEsteMs = mesDeLaVentana.instrumentos.find((i) => i.ticker === instrumento.ticker)
    return pagaEsteMs && pagaEsteMs.pct_renta > 0 ? 'renta' : null
  })
  const cantidadDeMeses = celdas.filter((c) => c === 'renta').length

  return (
    <div
      style={{
        background: 'var(--pan2)',
        border: '1px solid var(--lin)',
        borderRadius: 3,
        padding: '10px 12px',
        display: 'grid',
        gap: 8,
      }}
    >
      <div>
        <span className="mono" style={{ fontSize: 13, color: 'var(--tx)' }}>
          {instrumento.ticker}
        </span>
        <span style={{ marginLeft: 6, fontSize: 11, color: 'var(--dim)' }}>{instrumento.emision}</span>
      </div>

      <div style={{ display: 'flex', gap: 14 }}>
        <Metrica
          rotulo={instrumento.rendimiento === null ? 'rendimiento' : unidadDeNaturaleza(instrumento.naturaleza)}
          valor={instrumento.rendimiento === null ? SIN_DATO : fmtPct(instrumento.rendimiento * 100)}
        />
        <Metrica rotulo="cupón" valor={fmtPct(instrumento.pct_renta * 100)} />
        <Metrica rotulo="meses que paga" valor={String(cantidadDeMeses)} />
      </div>

      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        {instrumento.naturaleza_nombre} · vence {fmtFecha(instrumento.vencimiento)}
      </p>

      <MiniCalendario meses={celdas} etiqueta={`${instrumento.ticker} paga en ${cantidadDeMeses} de 12 meses`} />

      <button
        type="button"
        onClick={() => alternarPapel(instrumento.ticker)}
        aria-pressed={seleccionado}
        style={{
          font: 'inherit',
          fontSize: 11.5,
          padding: '5px 10px',
          borderRadius: 3,
          border: `1px solid ${seleccionado ? 'var(--neg)' : 'var(--ac)'}`,
          background: 'transparent',
          color: seleccionado ? 'var(--neg)' : 'var(--ac)',
          cursor: 'pointer',
        }}
      >
        {seleccionado ? 'sacar de la cartera' : 'agregar a la cartera'}
      </button>
    </div>
  )
}

function Metrica({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 15, color: 'var(--tx)', fontWeight: 600 }}>
        {valor}
      </div>
      <div
        style={{
          fontSize: 9.5,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {rotulo}
      </div>
    </div>
  )
}
