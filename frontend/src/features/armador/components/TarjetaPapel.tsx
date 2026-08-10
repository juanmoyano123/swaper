/**
 * Un papel dentro de un panel de mes, como tarjeta — F-016, rediseñada el 08/08/2026.
 *
 * Reemplaza al renglón de una sola línea (`RenglonPapel`): con doce columnas angostas, el ticker +
 * moneda + cupón + TIR rotulada + año no entraban legibles y el texto desbordaba encima de la
 * columna vecina. La tarjeta entera es el botón: clickearla entra o saca el papel de la cartera
 * (`alternarPapel`), y como cada mes en el que el papel paga pinta su propia tarjeta contra el
 * mismo `pos`, la iluminación multi-mes (GWT-1/GWT-2) sale sola — mismo mecanismo que tenía
 * `RenglonPapel`, sin ningún cálculo acá de "en qué otros meses está este ticker".
 *
 * Sin moneda ni badge de tipo de liquidación (Cable/MEP): no hay un dato real que distinga eso —
 * la última letra del ticker no alcanza (regla 11 del dominio, ver `CLAUDE.md`) y no se traduce.
 *
 * **Calificación (Etapa 5 del rediseño del armador)**: literal, tal como la declaró la
 * calificadora — nunca se ordena ni se compara contra otra (texto libre de cuatro fuentes
 * distintas, sin escala común). `undefined` (sin cruce con el universo) y `null` (cruzó, sin
 * calificación informada) se muestran igual, "sin calif.": la distinción entre las dos no le sirve
 * a quien mira la tarjeta.
 */

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtPct, SIN_DATO } from '@/lib/fmt'

import type { InstrumentoDelMes } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

export function TarjetaPapel({
  instrumento,
  calificacion,
}: {
  instrumento: InstrumentoDelMes
  /** `undefined` = el ticker no cruzó contra el universo; `null` = cruzó pero sin calificación
   *  informada por la fuente. Los dos se muestran como "sin calif.", nunca se ocultan (regla 11). */
  calificacion?: string | null
}) {
  const { pos } = useArmador()
  const { alternarPapel } = useArmadorAcciones()
  const seleccionado = pos.some((p) => p.ticker === instrumento.ticker)

  // Sólo el año: es lo que la spec pide en la tarjeta colapsada. La fecha completa queda para una
  // ficha de detalle, si hiciera falta más adelante.
  const anioVencimiento = instrumento.vencimiento?.slice(0, 4) ?? null

  return (
    <button
      type="button"
      onClick={() => alternarPapel(instrumento.ticker)}
      aria-pressed={seleccionado}
      title={`${instrumento.ticker} · ${instrumento.emision}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 3,
        width: '100%',
        minWidth: 0,
        padding: '7px 9px',
        borderRadius: 4,
        border: `1px solid ${seleccionado ? 'var(--ac)' : 'var(--lin)'}`,
        background: seleccionado ? 'var(--sel)' : 'var(--pan2)',
        color: 'var(--tx)',
        cursor: 'pointer',
        textAlign: 'left',
      }}
    >
      <span
        className="mono"
        style={{
          fontSize: 12.5,
          fontWeight: 600,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {instrumento.ticker}
      </span>
      <div className="mono" style={{ display: 'flex', flexWrap: 'wrap', columnGap: 10, rowGap: 2, fontSize: 10.5 }}>
        <Campo rotulo="Cupón" valor={fmtPct(instrumento.pct_renta * 100)} color="var(--ac2)" />
        <span style={{ color: 'var(--pos)', fontWeight: 600, whiteSpace: 'nowrap' }}>
          {instrumento.rendimiento === null
            ? SIN_DATO
            : `${fmtPct(instrumento.rendimiento * 100)} ${unidadDeNaturaleza(instrumento.naturaleza)}`}
        </span>
        <Campo rotulo="Vto" valor={anioVencimiento ?? SIN_DATO} color="var(--sd)" />
        <Campo rotulo="Calif." valor={calificacion ?? 'sin calif.'} color="var(--sd)" />
      </div>
    </button>
  )
}

function Campo({ rotulo, valor, color }: { rotulo: string; valor: string; color: string }) {
  return (
    <span style={{ whiteSpace: 'nowrap' }}>
      <span style={{ color: 'var(--dim)' }}>{rotulo} </span>
      <span style={{ color, fontWeight: 600 }}>{valor}</span>
    </span>
  )
}
