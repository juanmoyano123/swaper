/**
 * Rendimiento vs. duración del segmento activo — F-038.
 *
 * Un solo segmento por gráfico, siempre: mezclar dos naturalezas de tasa en el mismo eje es
 * exactamente lo que la regla 2 del dominio prohíbe, y por eso el componente recibe ya filtrado el
 * segmento activo y no el universo entero. Sólo entran los puntos con los dos números —sin
 * duración no hay dónde ubicarlo en el eje x, sin rendimiento no hay qué mostrar en el y— y las
 * filas que quedan afuera se cuentan al pie: la curva no puede leerse como si fuera el segmento
 * entero cuando no lo es.
 */

import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtNumero, fmtPct } from '@/lib/fmt'

import type { Especie } from '../lib/schema'

interface Punto {
  ticker: string
  duracion: number
  /** Ya en puntos porcentuales (×100), como se muestra en toda la pantalla. */
  rendimientoPct: number
}

export function CurvaSegmento({ especies, naturaleza }: { especies: Especie[]; naturaleza: string }) {
  const unidad = unidadDeNaturaleza(naturaleza)
  const puntos: Punto[] = especies
    .filter((e): e is Especie & { rendimiento: number; duracion: number } => e.rendimiento !== null && e.duracion !== null)
    .map((e) => ({ ticker: e.ticker, duracion: e.duracion, rendimientoPct: e.rendimiento * 100 }))
  const excluidas = especies.length - puntos.length

  if (puntos.length === 0) {
    return (
      <p style={{ fontSize: 12.5, color: 'var(--dim)' }}>
        Ninguna especie de este segmento tiene rendimiento y duración a la vez: no hay curva que dibujar.
      </p>
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 8, right: 20, bottom: 20, left: 8 }}>
          <CartesianGrid stroke="var(--lin)" strokeDasharray="2 4" />
          <XAxis
            type="number"
            dataKey="duracion"
            name="duración"
            tick={{ fill: 'var(--dim)', fontSize: 10.5 }}
            stroke="var(--lin)"
            label={{ value: 'duración (años)', position: 'insideBottom', offset: -12, fill: 'var(--dim)', fontSize: 10.5 }}
          />
          <YAxis
            type="number"
            dataKey="rendimientoPct"
            name={unidad}
            tick={{ fill: 'var(--dim)', fontSize: 10.5 }}
            stroke="var(--lin)"
            label={{ value: unidad, angle: -90, position: 'insideLeft', fill: 'var(--dim)', fontSize: 10.5 }}
          />
          <Tooltip cursor={{ stroke: 'var(--ac)', strokeDasharray: '3 3' }} content={<TooltipPunto unidad={unidad} />} />
          <Scatter data={puntos} fill="var(--ac)" />
        </ScatterChart>
      </ResponsiveContainer>
      {excluidas > 0 && (
        <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--dim)' }}>
          {fmtNumero(excluidas, 0)} especies sin rendimiento o duración no están en la curva.
        </p>
      )}
    </div>
  )
}

function TooltipPunto({
  active,
  payload,
  unidad,
}: {
  active?: boolean
  payload?: Array<{ payload: Punto }>
  unidad: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const { ticker, duracion, rendimientoPct } = payload[0].payload

  return (
    <div
      className="mono"
      style={{
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 3,
        padding: '5px 8px',
        fontSize: 11,
      }}
    >
      <div>{ticker}</div>
      <div>
        {fmtPct(rendimientoPct)} {unidad}
      </div>
      <div>{fmtNumero(duracion)} años</div>
    </div>
  )
}
