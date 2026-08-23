/**
 * El picker de FCI — F-046, punto 1. Reemplaza al texto libre: el asesor busca por nombre y elige
 * de la lista de `public.fci`, nunca escribe el ticker a mano. Se usa en dos lugares con el mismo
 * componente y distinto callback: agregar un FCI nuevo a la cartera, y re-identificar uno legado
 * que se cargó antes de esta feature (sin `codigoCafci`) — en los dos casos la elección sale de
 * acá, **nunca se matchea por nombre automáticamente** (regla 11 del dominio).
 *
 * `useFondosFci(null)` trae los 4.251 fondos enteros (misma llamada que el picker de F-057), así
 * que el filtro es en cliente, por substring de `fondo`, sin distinguir mayúsculas.
 */

import { useMemo, useState } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { useFondosFci, type FondoFci } from '@/lib/fci'
import { fmtFecha, fmtNumero, SIN_DATO } from '@/lib/fmt'

const TOPE_RESULTADOS = 12

export function SelectorFci({
  onElegir,
  onCancelar,
  etiqueta,
}: {
  onElegir: (fondo: FondoFci) => void
  onCancelar: () => void
  /** Para distinguir los dos usos en el `aria-label` del input (agregar vs. re-identificar). */
  etiqueta: string
}) {
  const [texto, setTexto] = useState('')
  const fondos = useFondosFci(null)

  const resultados = useMemo(() => {
    const buscado = texto.trim().toLowerCase()
    if (buscado === '') return []
    return (fondos.data ?? [])
      .filter((f) => f.fondo.toLowerCase().includes(buscado))
      .slice(0, TOPE_RESULTADOS)
  }, [fondos.data, texto])

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        background: 'var(--pan2)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: 8,
        maxWidth: 420,
      }}
    >
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <input
          type="text"
          autoFocus
          value={texto}
          onChange={(evento) => setTexto(evento.target.value)}
          placeholder="Buscar fondo por nombre…"
          aria-label={etiqueta}
          style={{
            flex: 1,
            font: 'inherit',
            fontSize: 12,
            color: 'var(--tx)',
            background: 'var(--pan)',
            border: '1px solid var(--lin)',
            borderRadius: 3,
            padding: '5px 7px',
          }}
        />
        <button
          type="button"
          onClick={onCancelar}
          aria-label="cancelar búsqueda de FCI"
          style={{
            font: 'inherit',
            fontSize: 12,
            border: 'none',
            background: 'transparent',
            color: 'var(--dim)',
            cursor: 'pointer',
          }}
        >
          ×
        </button>
      </div>

      {fondos.isPending && <EstadoCarga que="los fondos comunes de inversión" />}
      {fondos.isError && <EstadoError error={fondos.error} onRetry={() => void fondos.refetch()} />}

      {!fondos.isPending && !fondos.isError && texto.trim() !== '' && (
        <ul
          role="listbox"
          aria-label="Resultados de fondos"
          style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 2, maxHeight: 220, overflowY: 'auto' }}
        >
          {resultados.length === 0 ? (
            <li style={{ fontSize: 11.5, color: 'var(--sd)', padding: '4px 2px' }}>
              Ningún fondo coincide con &quot;{texto}&quot;.
            </li>
          ) : (
            resultados.map((fondo) => (
              <li key={fondo.codigo_cafci}>
                <button
                  type="button"
                  role="option"
                  onClick={() => onElegir(fondo)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    font: 'inherit',
                    fontSize: 11.5,
                    color: 'var(--tx)',
                    background: 'transparent',
                    border: 'none',
                    borderRadius: 3,
                    padding: '5px 6px',
                    cursor: 'pointer',
                  }}
                >
                  <span style={{ display: 'block' }}>{fondo.fondo}</span>
                  <span className="mono" style={{ display: 'block', fontSize: 10, color: 'var(--dim)' }}>
                    {fondo.moneda} · VCP{' '}
                    {fondo.vcp !== null ? fmtNumero(fondo.vcp / 1000, 2) : SIN_DATO}
                    {' · '}
                    {fondo.fecha_vcp !== null ? fmtFecha(fondo.fecha_vcp) : 'sin fecha'}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  )
}
