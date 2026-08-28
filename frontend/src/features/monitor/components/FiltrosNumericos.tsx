/**
 * La fila de umbrales del universo — F-038. `FiltrosUniverso`, `FILTROS_VACIOS` y `pasaFiltros` se
 * mudaron a `../lib/filtros.ts` (14/08/2026, facetado en cascada) y se re-exportan acá para no
 * romper a quien ya los importaba de este archivo.
 *
 * Inputs controlados y vacío significa "sin filtro": no hay un valor por defecto que discrimine
 * filas, porque eso sería decidir en silencio qué es "razonable" sin que el asesor lo haya pedido.
 * El rótulo del rendimiento lleva la unidad del segmento activo (regla 2 del dominio): un filtro
 * sin unidad invitaría a escribir un número pensando en TIR dólar y filtrar sobre una TNA en pesos.
 *
 * Los tres interruptores son de otra clase que los tres numéricos: no comparan contra un umbral que
 * el asesor eligió, sacan de la vista lo que no operó. Vienen apagados a propósito —una especie sin
 * precio es un dato del mercado, no ruido— pero la grilla del universo trae muchas que no tuvieron
 * rueda, y poder taparlas de un clic es lo que las hace mirables. Es lo que hace Balanz con sus dos
 * casillas "Mostrar con precio" y "Operado hoy".
 *
 * El tercero, "con emisor identificado" (28/08/2026), tapa lo que no se puede analizar en vez de lo
 * que no operó: sin emisor escrito no hay riesgo de crédito que nombrar. Sigue apagado por defecto
 * —esas especies se muestran con `s/d`— y no es una whitelist de bróker (regla 9): el universo
 * negociable no se recorta, se elige mirar el subconjunto que tiene el dato.
 */

import type { ReactNode } from 'react'

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'

import { FILTROS_VACIOS, pasaFiltros, type FiltrosUniverso } from '../lib/filtros'

export { FILTROS_VACIOS, pasaFiltros, type FiltrosUniverso }

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
      <Interruptor
        etiqueta="sólo con precio"
        marcado={valores.soloConPrecio}
        onCambio={(soloConPrecio) => onCambio({ ...valores, soloConPrecio })}
      />
      <Interruptor
        etiqueta="operado hoy"
        marcado={valores.soloOperadoHoy}
        onCambio={(soloOperadoHoy) => onCambio({ ...valores, soloOperadoHoy })}
      />
      <Interruptor
        etiqueta="con emisor identificado"
        marcado={valores.soloConEmisor}
        onCambio={(soloConEmisor) => onCambio({ ...valores, soloConEmisor })}
      />
      <button type="button" onClick={() => onCambio(FILTROS_VACIOS)} style={estiloBoton}>
        limpiar filtros
      </button>
    </div>
  )
}

function Interruptor({
  etiqueta,
  marcado,
  onCambio,
}: {
  etiqueta: string
  marcado: boolean
  onCambio: (marcado: boolean) => void
}) {
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 5,
        fontSize: 11.5,
        color: marcado ? 'var(--tx)' : 'var(--dim)',
        cursor: 'pointer',
        paddingBottom: 6,
      }}
    >
      <input type="checkbox" checked={marcado} onChange={(e) => onCambio(e.target.checked)} />
      {etiqueta}
    </label>
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
