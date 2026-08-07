/**
 * Los filtros numéricos del universo — F-038.
 *
 * Inputs controlados y vacío significa "sin filtro": no hay un valor por defecto que discrimine
 * filas, porque eso sería decidir en silencio qué es "razonable" sin que el asesor lo haya pedido.
 * El rótulo del rendimiento lleva la unidad del segmento activo (regla 2 del dominio): un filtro
 * sin unidad invitaría a escribir un número pensando en TIR dólar y filtrar sobre una TNA en pesos.
 */

import type { ReactNode } from 'react'

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'

export interface FiltrosUniverso {
  rendimientoMin: string
  rendimientoMax: string
  duracionMax: string
}

export const FILTROS_VACIOS: FiltrosUniverso = {
  rendimientoMin: '',
  rendimientoMax: '',
  duracionMax: '',
}

/**
 * Si una fila pasa los filtros activos.
 *
 * Una fila con `rendimiento: null` no puede pasar un filtro de rendimiento —no se puede afirmar
 * que un dato que no existe cumple un umbral— pero sin filtros activos se muestra igual: el
 * faltante no es un motivo para esconder la fila, sólo para no poder filtrarla por ese campo.
 * Mismo criterio para duración: sin dato no hay cómo saber si cumple un máximo.
 *
 * `especie.rendimiento` es una fracción (0.13 = 13%, igual que en el esquema), pero el input de
 * filtro está rotulado en la unidad de columna —puntos porcentuales, lo que se ve en la celda— así
 * que lo que el asesor escribe se divide por 100 antes de comparar. Filtrar contra la fracción cruda
 * obligaría a escribir "0.13" para encontrar un 13%, que no es lo que el rótulo promete.
 */
export function pasaFiltros(especie: { rendimiento: number | null; duracion: number | null }, filtros: FiltrosUniverso): boolean {
  const min = filtros.rendimientoMin === '' ? null : Number(filtros.rendimientoMin) / 100
  const max = filtros.rendimientoMax === '' ? null : Number(filtros.rendimientoMax) / 100
  const duracionMax = filtros.duracionMax === '' ? null : Number(filtros.duracionMax)

  if ((min !== null || max !== null) && especie.rendimiento === null) return false
  if (min !== null && especie.rendimiento !== null && especie.rendimiento < min) return false
  if (max !== null && especie.rendimiento !== null && especie.rendimiento > max) return false

  if (duracionMax !== null && especie.duracion === null) return false
  if (duracionMax !== null && especie.duracion !== null && especie.duracion > duracionMax) return false

  return true
}

export function FiltrosNumericos({
  naturaleza,
  valores,
  onCambio,
}: {
  /** Naturaleza de tasa del segmento activo: fija la unidad de los dos campos de rendimiento. */
  naturaleza: string
  valores: FiltrosUniverso
  onCambio: (valores: FiltrosUniverso) => void
}) {
  const unidad = unidadDeNaturaleza(naturaleza)

  return (
    <div style={estiloFila}>
      <Campo etiqueta={`Rendimiento mín. (${unidad})`}>
        <input
          type="number"
          inputMode="decimal"
          value={valores.rendimientoMin}
          onChange={(e) => onCambio({ ...valores, rendimientoMin: e.target.value })}
          style={estiloInput}
        />
      </Campo>
      <Campo etiqueta={`Rendimiento máx. (${unidad})`}>
        <input
          type="number"
          inputMode="decimal"
          value={valores.rendimientoMax}
          onChange={(e) => onCambio({ ...valores, rendimientoMax: e.target.value })}
          style={estiloInput}
        />
      </Campo>
      <Campo etiqueta="Duración máx. (años)">
        <input
          type="number"
          inputMode="decimal"
          value={valores.duracionMax}
          onChange={(e) => onCambio({ ...valores, duracionMax: e.target.value })}
          style={estiloInput}
        />
      </Campo>
      <button type="button" onClick={() => onCambio(FILTROS_VACIOS)} style={estiloBoton}>
        limpiar filtros
      </button>
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

const estiloFila = {
  display: 'flex',
  gap: 12,
  alignItems: 'flex-end',
  flexWrap: 'wrap',
  margin: '10px 0',
} as const

const estiloInput = {
  width: 108,
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
