/**
 * El detalle de una cartera guardada, por defecto (GWT-1): renderiza exclusivamente lo que hay en
 * el snapshot — nada acá dispara un pedido de mercado. "Revaluar a hoy" es un componente aparte
 * (`Revaluacion.tsx`) que recién pide precios cuando el asesor lo pide a propósito.
 *
 * `NotaCosto` se reusa de `optimizador/components/compartidos` (el mismo archivo que ya comparten
 * las dos secciones del optimizador): las tres formas de declarar el costo de una rotación son una
 * regla de negocio, no un detalle visual — duplicarla acá arriesgaría que las dos lecturas se
 * desalineen con el tiempo.
 */

import { NotaCosto } from '@/features/optimizador/components/compartidos'
import { fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import type { SnapshotArmador, SnapshotCargada, SnapshotCartera } from '../lib/esquemaSnapshot'

const ROTULO_CLASE: Record<string, string> = {
  renta_fija: 'Renta fija',
  renta_variable: 'Renta variable',
  fci: 'FCI',
}

const rotuloEstilo = {
  fontSize: 10,
  letterSpacing: '0.13em',
  color: 'var(--ac)',
  textTransform: 'uppercase' as const,
  marginBottom: 6,
}

const listaEstilo = { margin: 0, padding: 0, listStyle: 'none' as const, display: 'grid', gap: 4 }

const filaEstilo = { display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap' as const, fontSize: 11.5 }

export function VistaCongelada({ snapshot }: { snapshot: SnapshotCartera }) {
  return snapshot.origen === 'cargada' ? (
    <VistaCargada snapshot={snapshot} />
  ) : (
    <VistaArmador snapshot={snapshot} />
  )
}

function VistaCargada({ snapshot }: { snapshot: SnapshotCargada }) {
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <p className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
        Perfil para buscar rotaciones: {snapshot.perfil} · Tipo de cambio al guardar:{' '}
        {snapshot.tipoDeCambio !== null ? fmtNumero(snapshot.tipoDeCambio, 2) : SIN_DATO}
      </p>

      <div>
        <div style={rotuloEstilo}>Posiciones valuadas al guardar</div>
        <ul role="list" aria-label="Posiciones valuadas" style={listaEstilo}>
          {snapshot.valuadas.map((v) => (
            <li key={v.ticker} role="listitem" className="mono" style={filaEstilo}>
              <span style={{ color: 'var(--tx)' }}>{v.ticker}</span>
              <span style={{ color: 'var(--sd)' }}>
                {v.moneda ? fmtMonto(v.invertido, v.moneda) : SIN_DATO} · {fmtPct(v.pesoReal, 1)} de la cartera
              </span>
            </li>
          ))}
        </ul>
      </div>

      {snapshot.excluidas.length > 0 && (
        <div>
          <div style={rotuloEstilo}>Sin valuar al guardar</div>
          <ul role="list" aria-label="Posiciones sin valuar" style={listaEstilo}>
            {snapshot.excluidas.map((e) => (
              <li key={e.id} role="listitem" className="mono" style={{ ...filaEstilo, color: 'var(--dim)' }}>
                <span>{e.id}</span>
                <span>
                  {e.motivo}
                  {e.montoDeclarado !== null && ` · monto declarado ${fmtNumero(e.montoDeclarado)}`}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="mono" style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--tx)' }}>
        Total invertido: {fmtMonto(snapshot.totalInvertidoUsd, 'usd')}
      </p>

      {snapshot.plan.aceptadas.length > 0 && (
        <div>
          <div style={rotuloEstilo}>
            Rotaciones aceptadas ({snapshot.plan.aceptadas.length})
          </div>
          <ul role="list" aria-label="Rotaciones aceptadas" style={listaEstilo}>
            {snapshot.plan.aceptadas.map((c, indice) => (
              <li
                key={`${c.origen.ticker}->${c.destino.ticker}:${indice}`}
                role="listitem"
                style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '8px 10px', display: 'grid', gap: 3 }}
              >
                <div style={{ ...filaEstilo, fontSize: 12 }}>
                  <span className="mono" style={{ color: 'var(--tx)' }}>
                    {c.origen.ticker} → {c.destino.ticker}
                  </span>
                  <span className="mono" style={{ color: 'var(--ac)' }}>
                    Δ rendimiento {fmtPct(c.delta.rendimiento_pp, 2)}
                  </span>
                </div>
                <NotaCosto costo={c.costo} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {snapshot.plan.descartadas.length > 0 && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
          {snapshot.plan.descartadas.length}{' '}
          {snapshot.plan.descartadas.length === 1 ? 'candidata descartada' : 'candidatas descartadas'} en esta
          sesión.
        </p>
      )}
    </div>
  )
}

function VistaArmador({ snapshot }: { snapshot: SnapshotArmador }) {
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <p className="mono" style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
        Capital objetivo: {fmtMonto(snapshot.montoTotalUsd, 'usd')} · Tipo de cambio al guardar:{' '}
        {snapshot.tipoDeCambio !== null ? fmtNumero(snapshot.tipoDeCambio, 2) : SIN_DATO}
      </p>

      <div>
        <div style={rotuloEstilo}>Posiciones del mandato</div>
        <ul role="list" aria-label="Posiciones del mandato" style={listaEstilo}>
          {snapshot.resueltas.map((r) => (
            <li key={r.ticker} role="listitem" className="mono" style={{ ...filaEstilo, alignItems: 'baseline' }}>
              <span style={{ color: 'var(--tx)' }}>
                {r.ticker} <span style={{ color: 'var(--dim)', fontSize: 10 }}>({ROTULO_CLASE[r.clase]})</span>
              </span>
              <span style={{ color: 'var(--sd)' }}>
                {r.invertidoUsd !== null && r.moneda
                  ? `${fmtMonto(r.invertido!, r.moneda)} · ${fmtMonto(r.invertidoUsd, 'usd')} · `
                  : `${SIN_DATO} · `}
                {fmtPct(r.peso, 1)} pedido
              </span>
            </li>
          ))}
        </ul>
      </div>

      <p className="mono" style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--tx)' }}>
        Total efectivamente invertido: {fmtMonto(snapshot.totalInvertidoUsd, 'usd')}
      </p>
    </div>
  )
}
