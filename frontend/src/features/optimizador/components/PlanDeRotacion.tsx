/**
 * F-036 — el panel "en vivo" de la cartera propuesta: qué se aceptó y Deshacer.
 *
 * GWT-2 y GWT-3 de la spec (`plan.md:1708`). El calendario y los seis ejes de la cartera resultante
 * se mudaron a `ComparacionCarteras` (F-037): mostrarlos acá y en la comparación sería el mismo
 * dato dos veces — este panel queda con su identidad real, la lista de lo aceptado.
 *
 * **Deshacer es LIFO puro**: sólo la última aceptada tiene botón. Las aceptaciones se encadenan (el
 * destino de una puede ser el origen de la siguiente), así que deshacer una del medio dejaría a las
 * posteriores con un origen que ya no está en la cartera — el store documenta la misma decisión.
 */

import { fmtPct } from '@/lib/fmt'
import { claveCandidata } from '@/lib/rotaciones/ejes'
import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import { NotaCosto } from './compartidos'
import { usePlanRotacion, usePlanRotacionAcciones } from '../store/planRotacionStore'

export function PlanDeRotacion() {
  const plan = usePlanRotacion()
  const acciones = usePlanRotacionAcciones()

  if (plan.aceptadas.length === 0) return null

  return (
    <section
      style={{ marginTop: 16, background: 'var(--pan)', border: '1px solid var(--ac)', borderRadius: 4, padding: '12px 16px', display: 'grid', gap: 14 }}
      aria-label="Cartera propuesta"
    >
      <header>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Cartera propuesta — {plan.aceptadas.length} {plan.aceptadas.length === 1 ? 'rotación aceptada' : 'rotaciones aceptadas'}
        </div>
      </header>

      <ListaAceptadas aceptadas={plan.aceptadas} onDeshacerUltima={acciones.deshacerUltima} />
    </section>
  )
}

function ListaAceptadas({
  aceptadas,
  onDeshacerUltima,
}: {
  aceptadas: Candidata[]
  onDeshacerUltima: () => void
}) {
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <ul role="list" aria-label="Rotaciones aceptadas" style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
        {aceptadas.map((candidata, indice) => {
          const esUltima = indice === aceptadas.length - 1
          return (
            <li
              key={claveCandidata(candidata)}
              role="listitem"
              style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '8px 10px', display: 'grid', gap: 3 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', fontSize: 12 }}>
                <span className="mono" style={{ color: 'var(--tx)' }}>
                  {candidata.origen.ticker} → {candidata.destino.ticker}
                </span>
                <span className="mono" style={{ color: 'var(--ac)' }}>
                  Δ rendimiento {fmtPct(candidata.delta.rendimiento_pp, 2)}
                </span>
              </div>
              <NotaCosto costo={candidata.costo} />
              {esUltima && (
                <button
                  type="button"
                  onClick={onDeshacerUltima}
                  style={{ font: 'inherit', fontSize: 11, padding: '4px 10px', borderRadius: 3, cursor: 'pointer', border: '1px solid var(--lin)', background: 'transparent', color: 'var(--dim)', justifySelf: 'start' }}
                >
                  Deshacer
                </button>
              )}
            </li>
          )
        })}
      </ul>
      {aceptadas.length > 1 && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
          Se deshace en orden, de la última a la primera.
        </p>
      )}
    </div>
  )
}
