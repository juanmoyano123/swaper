/**
 * F-022 — rendimientos por naturaleza de tasa, plazo promedio y sensibilidad por segmento.
 *
 * **Regla 2 del dominio, hecha pantalla**: cinco tarjetas, siempre las cinco, nunca un promedio.
 * Una TIR en dólares, un rendimiento dólar-linked, una tasa real sobre CER, una TIR efectiva anual
 * en pesos y una TNA nominal en pesos son magnitudes distintas — no hay acá ni va a haber un
 * control que las combine en un número. Las dos últimas cobran en la misma moneda y aun así van
 * separadas: una tasa efectiva y una nominal no son el mismo número (Tanda 2, 26/08/2026). El plazo promedio sí se agrega (la duración es años, unidad comparable entre
 * naturalezas), la sensibilidad de precio no se agrega entre segmentos: cada segmento es una curva
 * propia, aunque comparta unidad temporal con las demás.
 *
 * Sin mockup específico en el design system para este panel (igual que `PanelConcentracion`, F-020):
 * se sigue el mismo estilo de tarjeta/panel compacto ya establecido en esta carpeta.
 */

import { Panel } from '@/components/Panel'
import { nombreSegmento, unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import {
  plazoPromedio,
  rendimientosPorNaturaleza,
  sensibilidadPorSegmento,
  type RendimientoPorNaturaleza,
  type SensibilidadPorSegmento,
} from '../lib/rendimientos'

export function PanelRendimientos() {
  const { resueltas, porTicker } = useCarteraResuelta()

  if (resueltas.length === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          border: '1px dashed var(--lin)',
          borderRadius: 4,
          fontSize: 12,
          color: 'var(--dim)',
        }}
      >
        Sin posiciones de renta fija todavía: agregá papeles para ver los rendimientos por
        naturaleza de tasa y el plazo promedio.
      </div>
    )
  }

  const naturalezas = rendimientosPorNaturaleza(resueltas, porTicker)
  const plazo = plazoPromedio(resueltas, porTicker)
  const segmentos = sensibilidadPorSegmento(resueltas, porTicker)

  return (
    <Panel
      ariaLabel="Rendimientos"
      rotulo="Rendimientos"
      titulo="Por naturaleza de tasa, nunca promediados"
    >
      <div style={{ display: 'grid', gap: 14 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
          {naturalezas.map((n) => (
            <TarjetaNaturaleza key={n.naturaleza} datos={n} />
          ))}
        </div>

        <PlazoPromedio anios={plazo.anios} posicionesExcluidas={plazo.posicionesExcluidas} />

        <SensibilidadSegmentos segmentos={segmentos} />
      </div>
    </Panel>
  )
}

function TarjetaNaturaleza({ datos }: { datos: RendimientoPorNaturaleza }) {
  return (
    <div style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '10px 12px' }}>
      <div
        className="rotulo"
        style={{ fontSize: 9.5, letterSpacing: '0.08em', color: 'var(--dim)', textTransform: 'uppercase' }}
      >
        {unidadDeNaturaleza(datos.naturaleza)}
      </div>
      <div className="mono" style={{ fontSize: 22, fontWeight: 600, lineHeight: 1.2, color: 'var(--tx)' }}>
        {datos.rendimientoPond !== null ? fmtPct(datos.rendimientoPond * 100) : SIN_DATO}
      </div>
      <p className="mono" style={{ margin: '2px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>
        {fmtPct(datos.pctCartera, 1)} de la cartera
      </p>
      {datos.pctExcluido > 0 && (
        <p style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--ac2)', textWrap: 'pretty' }}>
          {datos.posicionesExcluidas} posición(es) sin rendimiento informado, {fmtPct(datos.pctExcluido, 1)}{' '}
          de la cartera, quedaron fuera del cálculo.
        </p>
      )}
    </div>
  )
}

function PlazoPromedio({
  anios,
  posicionesExcluidas,
}: {
  anios: number | null
  posicionesExcluidas: number
}) {
  return (
    <div style={{ borderTop: '1px solid var(--lin)', paddingTop: 12 }}>
      <div
        className="rotulo"
        style={{ fontSize: 9.5, letterSpacing: '0.08em', color: 'var(--dim)', textTransform: 'uppercase' }}
      >
        Plazo promedio
      </div>
      <div className="mono" style={{ fontSize: 20, fontWeight: 600, color: 'var(--tx)' }}>
        {anios !== null ? `${fmtNumero(anios, 1)} años` : SIN_DATO}
      </div>
      {posicionesExcluidas > 0 && (
        <p style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--ac2)' }}>
          {posicionesExcluidas} posición(es) sin duración informada quedaron fuera del cálculo.
        </p>
      )}
    </div>
  )
}

function SensibilidadSegmentos({ segmentos }: { segmentos: SensibilidadPorSegmento[] }) {
  if (segmentos.length === 0) return null

  return (
    <div style={{ borderTop: '1px solid var(--lin)', paddingTop: 12 }}>
      <h3
        style={{
          margin: '0 0 8px',
          fontSize: 10,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        Sensibilidad de precio por segmento
      </h3>
      <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
        {segmentos.map((s) => (
          <li
            key={s.segmento}
            style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}
          >
            <span style={{ color: 'var(--tx)' }}>{nombreSegmento(s.segmento)}</span>
            <span className="mono" style={{ color: 'var(--dim)', whiteSpace: 'nowrap' }}>
              {s.duracionPond !== null ? `${fmtNumero(s.duracionPond, 1)} años` : SIN_DATO} ·{' '}
              {fmtPct(s.pctCartera, 1)}
              {s.posicionesExcluidas > 0 && (
                <span style={{ color: 'var(--ac2)' }}> · {s.posicionesExcluidas} s/dato</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
