/**
 * Rendimiento vs. duración del segmento activo, con la cartera marcada — F-023.
 *
 * Misma base que `features/monitor/components/CurvaSegmento.tsx` (F-038, no se importa: está
 * fuera de alcance tocarlo), extendida a dos series porque acá hace falta distinguir la nube del
 * universo de las posiciones que el asesor ya tiene. Un solo segmento por gráfico, siempre — es la
 * regla 2 del dominio, y por eso `candidatos` y `cartera` llegan ya filtrados a un único segmento
 * por quien arma el panel, no el universo entero.
 *
 * Sólo entran los puntos con rendimiento y duración a la vez, en cada serie por separado: sin
 * duración no hay dónde ubicarlo en el eje x, sin rendimiento no hay qué mostrar en el y. Lo que
 * queda afuera de cada serie se cuenta al pie — la nube y la cartera no pueden leerse como si
 * fueran completas cuando no lo son.
 */

import {
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { fmtNumero, fmtPct } from '@/lib/fmt'

import type { Especie } from '../lib/schema'

type Origen = 'candidato' | 'cartera'

interface Punto {
  ticker: string
  duracion: number
  /** Ya en puntos porcentuales (×100), como se muestra en toda la pantalla. */
  rendimientoPct: number
  origen: Origen
}

function puntosDe(especies: Especie[], origen: Origen): Punto[] {
  return especies
    .filter(
      (e): e is Especie & { rendimiento: number; duracion: number } =>
        e.rendimiento !== null && e.duracion !== null,
    )
    .map((e) => ({ ticker: e.ticker, duracion: e.duracion, rendimientoPct: e.rendimiento * 100, origen }))
}

export function CurvaTirDuracion({
  candidatos,
  cartera,
  naturaleza,
}: {
  /** Universo del segmento activo, ya filtrado por quien arma el panel. */
  candidatos: Especie[]
  /** Posiciones de la cartera en ese mismo segmento. */
  cartera: Especie[]
  naturaleza: string
}) {
  const unidad = unidadDeNaturaleza(naturaleza)

  if (candidatos.length === 0) {
    return (
      <p style={{ fontSize: 12.5, color: 'var(--dim)' }}>
        No hay especies de este segmento en el universo de hoy: no hay curva que dibujar.
      </p>
    )
  }

  const puntosCandidatos = puntosDe(candidatos, 'candidato')
  const puntosCartera = puntosDe(cartera, 'cartera')
  const excluidosCandidatos = candidatos.length - puntosCandidatos.length
  const excluidosCartera = cartera.length - puntosCartera.length

  if (puntosCandidatos.length === 0) {
    return (
      <p style={{ fontSize: 12.5, color: 'var(--dim)' }}>
        Ninguna especie de este segmento tiene rendimiento y duración a la vez: no hay curva que
        dibujar.
      </p>
    )
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart margin={{ top: 8, right: 20, bottom: 20, left: 8 }}>
          <CartesianGrid stroke="var(--lin)" strokeDasharray="2 4" />
          <XAxis
            type="number"
            dataKey="duracion"
            name="duración"
            tick={{ fill: 'var(--dim)', fontSize: 10.5 }}
            stroke="var(--lin)"
            label={{
              value: 'duración (años)',
              position: 'insideBottom',
              offset: -12,
              fill: 'var(--dim)',
              fontSize: 10.5,
            }}
          />
          <YAxis
            type="number"
            dataKey="rendimientoPct"
            name={unidad}
            tick={{ fill: 'var(--dim)', fontSize: 10.5 }}
            stroke="var(--lin)"
            label={{
              value: unidad,
              angle: -90,
              position: 'insideLeft',
              fill: 'var(--dim)',
              fontSize: 10.5,
            }}
          />
          <Tooltip
            cursor={{ stroke: 'var(--ac)', strokeDasharray: '3 3' }}
            content={<TooltipPunto unidad={unidad} />}
          />
          {/* La nube va apagada — es el fondo. La cartera se marca con el color de acento y se
              rotula por ticker; la nube no, sería ilegible con cientos de puntos.
              `isAnimationActive={false}`: recharts sólo pinta el `<LabelList>` una vez termina la
              animación de entrada — sin apagarla, el rótulo tarda un instante en aparecer. */}
          <Scatter
            name="Universo del segmento"
            data={puntosCandidatos}
            fill="var(--dim)"
            isAnimationActive={false}
          />
          <Scatter name="Cartera" data={puntosCartera} fill="var(--ac)" isAnimationActive={false}>
            <LabelList dataKey="ticker" position="top" style={{ fill: 'var(--ac)', fontSize: 10 }} />
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      {(excluidosCandidatos > 0 || excluidosCartera > 0) && (
        <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--dim)' }}>
          {excluidosCandidatos > 0 && (
            <>{fmtNumero(excluidosCandidatos, 0)} candidatos sin dato de rendimiento o duración. </>
          )}
          {excluidosCartera > 0 && (
            <>
              {fmtNumero(excluidosCartera, 0)} posición(es) de la cartera sin dato de rendimiento o
              duración.
            </>
          )}
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
  const { ticker, duracion, rendimientoPct, origen } = payload[0].payload

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
      <div>
        {ticker}
        {origen === 'cartera' && <span style={{ color: 'var(--ac)' }}> · en la cartera</span>}
      </div>
      <div>
        {fmtPct(rendimientoPct)} {unidad}
      </div>
      <div>{fmtNumero(duracion)} años</div>
    </div>
  )
}
