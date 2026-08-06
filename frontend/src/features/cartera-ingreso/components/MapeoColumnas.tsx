/**
 * El paso "en vez de asumir el orden": el asesor confirma o corrige a qué campo corresponde cada
 * columna, con una muestra de los valores reales para no tener que adivinar qué es cada una.
 *
 * Se muestra tanto cuando no se reconoció ningún encabezado como cuando sí se reconoció pero la
 * vía fue un archivo: la Fase 2 pide que un archivo nunca imponga su orden sin que alguien lo
 * mire.
 */

import { useState } from 'react'

import { mapeoCompleto } from '../lib/mapeoColumnas'
import type { CampoPosicion, MapeoColumnas as TipoMapeo } from '../types'

import { BotonAccion } from './BotonAccion'

const ETIQUETAS: Record<CampoPosicion, string> = {
  ticker: 'Ticker',
  nominal: 'Nominal',
  monto: 'Monto',
  ignorar: 'Ignorar',
}

const CANTIDAD_FILAS_DE_MUESTRA = 3

export function MapeoColumnas({
  encabezados,
  filas,
  mapeoInicial,
  onConfirmar,
  onVolver,
}: {
  encabezados: string[] | null
  filas: string[][]
  mapeoInicial: TipoMapeo
  onConfirmar: (mapeo: TipoMapeo) => void
  onVolver: () => void
}) {
  const [mapeo, setMapeo] = useState<TipoMapeo>(mapeoInicial)

  function cambiarColumna(indice: number, campo: CampoPosicion) {
    setMapeo((actual) => actual.map((c, i) => (i === indice ? campo : c)))
  }

  const completo = mapeoCompleto(mapeo)

  return (
    <div>
      <p style={{ margin: '0 0 10px', fontSize: 12.5, color: 'var(--dim)' }}>
        {encabezados
          ? 'Se reconocieron algunas columnas por su nombre. Revisá el mapeo antes de continuar.'
          : 'No se pudo reconocer un encabezado. Decile a cada columna qué campo es.'}
      </p>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', minWidth: '100%' }}>
          <thead>
            <tr>
              {mapeo.map((_, i) => (
                <th
                  key={i}
                  style={{
                    textAlign: 'left',
                    padding: '4px 8px',
                    fontSize: 10.5,
                    color: 'var(--dim)',
                    fontWeight: 400,
                    borderBottom: '1px solid var(--lin)',
                  }}
                >
                  {encabezados?.[i] || `Columna ${i + 1}`}
                </th>
              ))}
            </tr>
            <tr>
              {mapeo.map((campo, i) => (
                <th key={i} style={{ padding: '4px 8px', borderBottom: '1px solid var(--lin)' }}>
                  <select
                    aria-label={`Campo de la columna ${i + 1}`}
                    value={campo}
                    onChange={(e) => cambiarColumna(i, e.target.value as CampoPosicion)}
                    style={{
                      font: 'inherit',
                      fontSize: 11.5,
                      padding: '3px 4px',
                      borderRadius: 3,
                      border: '1px solid var(--lin)',
                      background: 'var(--pan2)',
                      color: 'var(--tx)',
                    }}
                  >
                    {(Object.keys(ETIQUETAS) as CampoPosicion[]).map((valor) => (
                      <option key={valor} value={valor}>
                        {ETIQUETAS[valor]}
                      </option>
                    ))}
                  </select>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.slice(0, CANTIDAD_FILAS_DE_MUESTRA).map((fila, i) => (
              <tr key={i}>
                {mapeo.map((_, j) => (
                  <td
                    key={j}
                    className="mono"
                    style={{ padding: '4px 8px', fontSize: 11.5, color: 'var(--tx)' }}
                  >
                    {fila[j] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {!completo && (
        <p style={{ margin: '10px 0 0', fontSize: 11.5, color: 'var(--ac2)' }}>
          Falta asignar una columna de ticker y una de nominal o monto.
        </p>
      )}

      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <BotonAccion variante="primario" onClick={() => onConfirmar(mapeo)} disabled={!completo}>
          Confirmar mapeo
        </BotonAccion>
        <BotonAccion onClick={onVolver}>Volver</BotonAccion>
      </div>
    </div>
  )
}
