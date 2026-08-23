/**
 * Agregado de FCI por sociedad gerente — F-067.
 *
 * `gerente` viaja tal cual lo declaró la planilla (regla 11: es una llave textual, no un dato
 * curado — no se normalizan grafías distintas a la misma gestora). El flujo neto a 30 días y en
 * el año no se calcula porque el producto no acumula planillas históricas: se muestra declarado,
 * nunca se omite ni se oculta la fila.
 */

import { EstadoVacio } from '@/components/EstadoVacio'
import { useGestorasFci, type GestoraFci } from '@/lib/fciAgregados'
import { fmtCompacto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

export function TablaGestoras() {
  const gestoras = useGestorasFci()

  if (gestoras.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando las gestoras…</p>
  }

  if (gestoras.isError) {
    return (
      <EstadoVacio
        titulo="No se pudieron traer las gestoras de FCI."
        detalle={
          <button
            type="button"
            onClick={() => void gestoras.refetch()}
            style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          >
            reintentar
          </button>
        }
      />
    )
  }

  const lista = gestoras.data?.gestoras ?? []

  if (lista.length === 0) {
    return (
      <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
        No hay fondos comunes en la planilla de hoy.
      </p>
    )
  }

  return (
    <div>
      {lista.map((gestora) => (
        <BloqueGestora key={gestora.gerente ?? '__sin_gestora__'} gestora={gestora} />
      ))}
    </div>
  )
}

function BloqueGestora({ gestora }: { gestora: GestoraFci }) {
  return (
    <section style={{ margin: '0 0 14px', paddingBottom: 10, borderBottom: '1px solid var(--lin)' }}>
      <h3 style={{ font: '600 13px/1.3 inherit', margin: '0 0 4px' }}>
        {gestora.gerente ?? 'sin gestora informada'}
        <span style={{ fontWeight: 400, color: 'var(--dim)', marginLeft: 8, fontSize: 12 }}>
          {fmtNumero(gestora.cantidad_fondos, 0)} fondos
          {gestora.market_share !== null ? ` · market share ${fmtPct(gestora.market_share)}` : ''}
        </span>
      </h3>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', margin: '4px 0 6px' }}>
        {gestora.por_moneda.map((bloque) => (
          <span key={bloque.moneda} className="mono" style={{ fontSize: 12, color: 'var(--dim)' }}>
            {bloque.moneda}: {bloque.aum === null ? SIN_DATO : fmtCompacto(bloque.aum)} ({fmtNumero(bloque.cantidad_fondos, 0)})
          </span>
        ))}
      </div>

      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        Flujo neto: no disponible — {gestora.flujo_neto.motivo}
      </p>
    </section>
  )
}
