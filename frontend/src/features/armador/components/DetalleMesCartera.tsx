/**
 * El detalle del mes al que se le hace clic en la cordillera — qué papel paga, cuándo exactamente y
 * cuánto, abierto por moneda de cobro. Recibe los mismos `meses` que `PanelRenta` ya tiene de
 * `useCalendarioCartera`: cache-hit garantizado, no dispara ningún request propio.
 *
 * Un papel que paga dos veces en el mismo mes muestra el total del mes con las dos fechas listadas
 * — `desgloseDelMes` no reparte ese total entre las fechas porque el contrato no lo informa (regla 1
 * del dominio: no se inventa el reparto). Renta y amortización nunca comparten barra ni se suman
 * entre monedas (regla 3).
 */
import { desgloseDelMes, type FilaDelDesglose, type GrupoDelMes } from '@/lib/cartera/renta'
import type { MesDelCalendario } from '@/lib/cartera/esquemaCalendario'
import { fmtCompacto, fmtFecha, fmtMonto, SIN_DATO } from '@/lib/fmt'

import { useArmador, useArmadorAcciones } from '../store/carteraStore'

const NOMBRE_MONEDA: Record<string, string> = {
  usd: 'Cobros en dólares (USD)',
  ars: 'Cobros en pesos (ARS)',
}

const COLOR_MONEDA: Record<string, string> = {
  usd: 'var(--pos)',
  ars: 'var(--ac2)',
}

function formatoDeMoneda(moneda: string): (valor: number) => string {
  return moneda === 'usd' ? (valor) => fmtMonto(valor, 'usd', 0) : (valor) => `$ ${fmtCompacto(valor)}`
}

export function DetalleMesCartera({ meses }: { meses: MesDelCalendario[] }) {
  const { selMes } = useArmador()
  const { alternarMes } = useArmadorAcciones()

  if (selMes === null) return null
  const mes = meses[selMes]
  if (!mes) return null

  const grupos = desgloseDelMes(mes)
  const algunaFechaMultiple = grupos.some((g) => g.filas.some((f) => f.fechas.length > 1))

  return (
    <section
      role="region"
      aria-label={`Detalle de ${mes.nombre}`}
      style={{
        background: 'var(--pan)',
        border: '1px solid var(--ac)',
        borderRadius: 4,
        padding: '12px 16px',
        display: 'grid',
        gap: 14,
      }}
    >
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <div className="rotulo">Detalle del mes</div>
          <h3 style={{ font: '600 14px/1.3 inherit', margin: '2px 0 0', color: 'var(--tx)' }}>{mes.nombre}</h3>
        </div>
        <button
          type="button"
          onClick={() => alternarMes(selMes)}
          aria-label="cerrar detalle del mes"
          style={{
            font: 'inherit',
            fontSize: 15,
            border: 'none',
            background: 'transparent',
            color: 'var(--dim)',
            cursor: 'pointer',
          }}
        >
          ×
        </button>
      </header>

      {grupos.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Ningún papel de la cartera cobra en {mes.nombre}.
        </p>
      ) : (
        grupos.map((grupo) => <GrupoDeMoneda key={grupo.moneda} grupo={grupo} />)
      )}

      {algunaFechaMultiple && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
          Un papel con más de una fecha muestra el total del mes: la fuente no informa el reparto por
          fecha.
        </p>
      )}
    </section>
  )
}

function GrupoDeMoneda({ grupo }: { grupo: GrupoDelMes }) {
  const color = COLOR_MONEDA[grupo.moneda] ?? 'var(--pos)'
  const formato = formatoDeMoneda(grupo.moneda)
  const titulo = NOMBRE_MONEDA[grupo.moneda] ?? `Cobros en ${grupo.moneda}`

  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <h4
        style={{
          margin: 0,
          fontSize: 10,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        {titulo}
      </h4>
      <div style={{ display: 'grid', gap: 8 }}>
        {grupo.filas.map((fila) => (
          <FilaDelPapel key={fila.ticker} fila={fila} pico={grupo.pico} color={color} formato={formato} />
        ))}
      </div>
    </div>
  )
}

function FilaDelPapel({
  fila,
  pico,
  color,
  formato,
}: {
  fila: FilaDelDesglose
  pico: number
  color: string
  formato: (valor: number) => string
}) {
  const fraccionRenta = fila.renta !== null && pico > 0 ? Math.min(100, (fila.renta / pico) * 100) : 0
  const fraccionAmort = fila.amortizacion !== null && pico > 0 ? Math.min(100, (fila.amortizacion / pico) * 100) : 0

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(64px,90px) 1fr max-content',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <div>
        <div className="mono" style={{ fontSize: 12.5, color: 'var(--tx)' }}>
          {fila.ticker}
        </div>
        <div style={{ fontSize: 9.5, color: 'var(--dim)' }}>
          {fila.fechas.map((fecha) => fmtFecha(fecha)).join(' · ')}
        </div>
      </div>

      <div style={{ display: 'grid', gap: 3 }}>
        <div aria-hidden style={{ height: 8, background: 'var(--pan2)', borderRadius: 4, overflow: 'hidden' }}>
          <div style={{ width: `${fraccionRenta}%`, height: '100%', background: color, borderRadius: 4 }} />
        </div>
        {fila.amortizacion !== null && fila.amortizacion > 0 && (
          <div
            title={`Amortización: ${formato(fila.amortizacion)} — no es renta, nunca se suma`}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}
          >
            <div
              aria-hidden
              style={{ flex: 1, height: 6, border: `1px solid ${color}`, borderRadius: 3, overflow: 'hidden' }}
            >
              <div style={{ width: `${fraccionAmort}%`, height: '100%', background: color, opacity: 0.4 }} />
            </div>
            <span style={{ fontSize: 9, color: 'var(--dim)', whiteSpace: 'nowrap' }}>◆ amortización</span>
          </div>
        )}
      </div>

      <span className="mono" style={{ fontSize: 11, color: 'var(--dim)', textAlign: 'right' }}>
        {fila.renta !== null ? formato(fila.renta) : SIN_DATO}
      </span>
    </div>
  )
}
