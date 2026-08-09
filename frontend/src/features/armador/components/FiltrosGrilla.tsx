/**
 * Barra de filtros de la grilla, siempre visible — F-017 (A7).
 *
 * Lee `filtros` con `useArmador()` y escribe con `fijarFiltros`/`limpiarFiltros` de
 * `useArmadorAcciones()`. Todo lo derivado del universo (opciones de los selects, conteo de
 * sobrevivientes) se lo pasa el contenedor (`GrillaFiltrada`), que es quien hace el cruce.
 *
 * El select de sector no ofrece "sector no informado" como opción propia — a diferencia de ley
 * (GWT-4 lo exige explícito) el plan no lo pide para sector, y `pasaFiltros` ya trata un
 * `sector: null` contra un filtro de sector concreto como "no pasa", nunca asignándolo a un
 * sector real (mismo criterio no-elegible que emisor).
 */

import type { ReactNode } from 'react'

import { unidadDeNaturaleza, SelectorSegmento } from '@/components/SelectorSegmento'

import { LEY_NO_INFORMADA, type FiltrosArmador } from '../lib/filtros'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

export function FiltrosGrilla({
  opciones,
  conteo,
  deshabilitado,
  motivoDeshabilitado,
}: {
  opciones: {
    segmentos: Array<{ clave: string; naturaleza: string }>
    sectores: string[]
    emisores: string[]
    leyes: string[]
    /** true si hay especies del cruce con `ley: null` — habilita la opción "ley no informada". */
    tieneLeyNoInformada: boolean
    pagos: number[]
  }
  conteo: { visibles: number; total: number; sinCruce: number }
  /** true mientras el universo carga o si falló: los filtros se declaran no disponibles. */
  deshabilitado: boolean
  /** Por qué está deshabilitado — el contenedor sabe si es carga o error; acá sólo se rotula. */
  motivoDeshabilitado?: 'cargando' | 'error'
}) {
  const { filtros } = useArmador()
  const { fijarFiltros, limpiarFiltros } = useArmadorAcciones()

  const segmentoActivo = opciones.segmentos.find((s) => s.clave === filtros.segmento)

  function cambiar(parcial: Partial<FiltrosArmador>) {
    fijarFiltros({ ...filtros, ...parcial })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, margin: '10px 0' }}>
      {deshabilitado && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
          {motivoDeshabilitado === 'error'
            ? 'el universo no cargó: filtros no disponibles'
            : 'cargando el universo para poder filtrar'}
        </p>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            type="button"
            onClick={() => cambiar({ segmento: null })}
            aria-pressed={filtros.segmento === null}
            disabled={deshabilitado}
            title="unidad declarada por renglón"
            style={estiloBotonTodos(filtros.segmento === null)}
          >
            Todos
          </button>
          <SelectorSegmento
            segmentos={opciones.segmentos.map((s) => s.clave)}
            activo={filtros.segmento ?? ''}
            onCambio={(segmento) => cambiar({ segmento: segmento === filtros.segmento ? null : segmento })}
          />
        </div>
        {filtros.segmento === null ? (
          <span style={{ fontSize: 11, color: 'var(--dim)' }}>unidad declarada por renglón</span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--dim)' }}>
            unidad: {unidadDeNaturaleza(segmentoActivo?.naturaleza ?? '')}
          </span>
        )}
      </div>

      <div style={estiloFila}>
        <Campo etiqueta="Duración máx. (años)">
          <input
            type="number"
            inputMode="decimal"
            value={filtros.duracionMax}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ duracionMax: e.target.value })}
            style={estiloInput}
          />
        </Campo>

        <Campo etiqueta="Liquidez mín. (percentil de volumen USD, sobre el universo a la vista)">
          <select
            value={filtros.liquidezMin}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ liquidezMin: e.target.value as FiltrosArmador['liquidezMin'] })}
            style={estiloInput}
          >
            <option value="">todos</option>
            <option value="25">≥ p25</option>
            <option value="50">≥ p50</option>
            <option value="75">≥ p75</option>
          </select>
        </Campo>

        <Campo etiqueta="Sector">
          <select
            value={filtros.sector ?? ''}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ sector: e.target.value === '' ? null : e.target.value })}
            style={estiloInput}
          >
            <option value="">todos</option>
            {[...opciones.sectores].sort().map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Emisor">
          <select
            value={filtros.emisor ?? ''}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ emisor: e.target.value === '' ? null : e.target.value })}
            style={estiloInput}
          >
            <option value="">todos</option>
            {[...opciones.emisores].sort().map((emisor) => (
              <option key={emisor} value={emisor}>
                {emisor}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="Ley">
          <select
            value={filtros.ley ?? ''}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ ley: e.target.value === '' ? null : e.target.value })}
            style={estiloInput}
          >
            <option value="">todos</option>
            {[...opciones.leyes].sort().map((ley) => (
              <option key={ley} value={ley}>
                {ley}
              </option>
            ))}
            {opciones.tieneLeyNoInformada && (
              <option value={LEY_NO_INFORMADA}>ley no informada</option>
            )}
          </select>
        </Campo>

        <Campo etiqueta="Pagos de renta (ventana 12 m)">
          <select
            value={filtros.pagos}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ pagos: e.target.value })}
            style={estiloInput}
          >
            <option value="">todos</option>
            {[...opciones.pagos].sort((a, b) => a - b).map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </Campo>

        <Campo etiqueta="TIR mín. (%, sólo TIR USD / TIR DL)">
          <input
            type="number"
            inputMode="decimal"
            value={filtros.tirMin}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ tirMin: e.target.value })}
            style={estiloInput}
          />
        </Campo>

        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            fontSize: 11,
            color: 'var(--dim)',
            cursor: deshabilitado ? 'default' : 'pointer',
          }}
        >
          <input
            type="checkbox"
            checked={filtros.soloConCupones}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ soloConCupones: e.target.checked })}
          />
          Sólo con cupones
        </label>

        <button type="button" onClick={() => limpiarFiltros()} style={estiloBoton}>
          limpiar filtros
        </button>
      </div>

      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
        {conteo.visibles} de {conteo.total} papeles pasan los filtros
        {conteo.sinCruce > 0 && (
          <span style={{ marginLeft: 8 }}>
            {conteo.sinCruce} sin ficha en el universo: no filtrables
          </span>
        )}
      </p>
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
      {etiqueta}
      {children}
    </label>
  )
}

function estiloBotonTodos(activo: boolean) {
  return {
    font: `${activo ? 600 : 400} 12.5px/1 inherit`,
    color: activo ? 'var(--tx)' : 'var(--dim)',
    background: 'none',
    border: 'none',
    borderBottom: activo ? '2px solid var(--ac)' : '2px solid transparent',
    padding: '8px 12px 7px',
    cursor: 'pointer',
    whiteSpace: 'nowrap' as const,
  }
}

const estiloFila = {
  display: 'flex',
  gap: 12,
  alignItems: 'flex-end',
  flexWrap: 'wrap',
} as const

const estiloInput = {
  minWidth: 108,
  font: 'inherit',
  fontSize: 12.5,
  padding: '5px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

const estiloBoton = {
  font: 'inherit',
  fontSize: 11,
  padding: '6px 10px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'transparent',
  color: 'var(--dim)',
  cursor: 'pointer',
} as const
