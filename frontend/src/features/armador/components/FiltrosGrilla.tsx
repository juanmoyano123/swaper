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
 *
 * Los filtros se leen de dos lados a propósito (facetado, 14/08/2026): las dimensiones que el
 * facetado acota —sector, emisor, ley, calificación, pagos— se muestran desde `efectivos`, para
 * que una selección que se quedó sin respaldo aparezca en "todos" y no como algo elegido que no
 * filtra. Los umbrales y la pestaña de segmento se leen del store, porque siempre aplican. Los
 * `onChange` escriben siempre el store crudo: nadie corrige a nadie, todo se deriva
 * (`facetarFiltros` en `lib/filtros.ts`).
 *
 * El orden de la barra va de lo general a lo específico, como se arma el perfil de una ON: la
 * pestaña de naturaleza de tasa, después ley → sector → calificación → cashflow → emisor, y en una
 * segunda fila los umbrales que afinan. Emisor va último porque es la dimensión más larga y la que
 * más gana con lo que las anteriores ya descartaron.
 *
 * Ley, Sector, Pagos, Emisor y Liquidez usan `@/components/CampoSelect` (F-079, Fase 4): el select
 * compartido que reemplazó la copia local de `estiloInput` para estos cinco. Calificación queda
 * afuera —es un multiselect con `<details>`, no un `<select>`— y los umbrales numéricos (Duración,
 * TIR) siguen con `Campo`/`estiloInput` porque son `<input type="number">`, no selects.
 */

import type { ReactNode } from 'react'

import { CampoSelect } from '@/components/CampoSelect'
import { unidadDeNaturaleza, SelectorSegmento } from '@/components/SelectorSegmento'

import {
  CALIFICACION_NO_INFORMADA,
  LEY_NO_INFORMADA,
  type DimensionFacetada,
  type FiltrosArmador,
  type OpcionesFacetadas,
  type SeleccionApagada,
} from '../lib/filtros'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

/** Cómo se nombra cada dimensión en el aviso de selecciones apagadas — el mismo rótulo que lleva
 *  su control en la barra. */
const ROTULO_DIMENSION: Record<DimensionFacetada, string> = {
  sector: 'Sector',
  emisor: 'Emisor',
  ley: 'Ley',
  calificaciones: 'Calificación',
  pagos: 'Pagos de renta',
}

export function FiltrosGrilla({
  opciones,
  efectivos,
  apagadas,
  conteo,
  deshabilitado,
  motivoDeshabilitado,
}: {
  opciones: OpcionesFacetadas & { segmentos: Array<{ clave: string; naturaleza: string }> }
  /** Los filtros que realmente se están aplicando: los del store con las selecciones que el
   *  facetado dejó sin respaldo apagadas. */
  efectivos: FiltrosArmador
  /** Lo que el facetado apagó, para declararlo: sin esto la grilla mostraría la ventana entera con
   *  un filtro elegido a la vista, y esos papeles se leerían como si lo cumplieran. */
  apagadas: SeleccionApagada[]
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

  // Alterna sobre las del store, no sobre las efectivas: una calificación que hoy no tiene
  // respaldo sigue guardada y vuelve sola si se aflojan los otros filtros. Para las que están a la
  // vista —las únicas que se pueden tildar— store y efectivas dicen lo mismo.
  function alternarCalificacion(valor: string) {
    const activa = filtros.calificaciones.includes(valor)
    cambiar({
      calificaciones: activa
        ? filtros.calificaciones.filter((c) => c !== valor)
        : [...filtros.calificaciones, valor],
    })
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

      {/* El perfil del papel, de lo general a lo específico. Cada uno de estos acota las opciones
          de los demás: lo que queda a la vista es lo que existe bajo lo ya elegido. */}
      <div style={estiloFila}>
        <CampoSelect
          etiqueta="Ley"
          valor={efectivos.ley ?? ''}
          disabled={deshabilitado}
          onChange={(valor) => cambiar({ ley: valor === '' ? null : valor })}
          opciones={[
            { valor: '', texto: 'todos' },
            ...[...opciones.leyes].sort().map((ley) => ({ valor: ley, texto: ley })),
            ...(opciones.tieneLeyNoInformada
              ? [{ valor: LEY_NO_INFORMADA, texto: 'ley no informada' }]
              : []),
          ]}
        />

        <CampoSelect
          etiqueta="Sector"
          valor={efectivos.sector ?? ''}
          disabled={deshabilitado}
          onChange={(valor) => cambiar({ sector: valor === '' ? null : valor })}
          opciones={[
            { valor: '', texto: 'todos' },
            ...[...opciones.sectores].sort().map((sector) => ({ valor: sector, texto: sector })),
          ]}
        />

        {/* No usa `Campo`: su `<label>` envolvería el `<details>` entero y le rompería el nombre
            accesible a cada checkbox de adentro (un `<label>` implícito se asocia con TODOS los
            controles que envuelve, no sólo el primero). El rótulo va en el `<summary>` como texto
            visible más `aria-label` propio, sin envolver nada. */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
          Calificación
          <details style={{ position: 'relative' }}>
            <summary
              aria-label="Calificación"
              style={{
                ...estiloInput,
                display: 'inline-block',
                cursor: deshabilitado ? 'default' : 'pointer',
                listStyle: 'none',
              }}
            >
              {efectivos.calificaciones.length === 0
                ? 'todas'
                : `${efectivos.calificaciones.length} elegida${efectivos.calificaciones.length === 1 ? '' : 's'}`}
            </summary>
            <div
              role="group"
              aria-label="Calificación"
              style={{
                position: 'absolute',
                zIndex: 1,
                top: '100%',
                marginTop: 4,
                display: 'grid',
                gap: 4,
                maxHeight: 220,
                overflowY: 'auto',
                padding: 8,
                background: 'var(--pan)',
                border: '1px solid var(--lin)',
                borderRadius: 4,
                minWidth: 200,
              }}
            >
              {opciones.calificaciones.map((calificacion) => (
                <label
                  key={calificacion}
                  style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--tx)' }}
                >
                  <input
                    type="checkbox"
                    checked={efectivos.calificaciones.includes(calificacion)}
                    disabled={deshabilitado}
                    onChange={() => alternarCalificacion(calificacion)}
                  />
                  {calificacion}
                </label>
              ))}
              {opciones.tieneCalificacionNoInformada && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--dim)' }}>
                  <input
                    type="checkbox"
                    checked={efectivos.calificaciones.includes(CALIFICACION_NO_INFORMADA)}
                    disabled={deshabilitado}
                    onChange={() => alternarCalificacion(CALIFICACION_NO_INFORMADA)}
                  />
                  sin calificación
                </label>
              )}
              {opciones.calificaciones.length === 0 && !opciones.tieneCalificacionNoInformada && (
                <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>sin especies en la ventana</span>
              )}
            </div>
          </details>
        </div>

        <CampoSelect
          etiqueta="Pagos de renta (ventana 12 m)"
          valor={efectivos.pagos}
          disabled={deshabilitado}
          onChange={(valor) => cambiar({ pagos: valor })}
          opciones={[
            { valor: '', texto: 'todos' },
            ...[...opciones.pagos]
              .sort((a, b) => a - b)
              .map((n) => ({ valor: String(n), texto: String(n) })),
          ]}
        />

        <CampoSelect
          etiqueta="Emisor"
          valor={efectivos.emisor ?? ''}
          disabled={deshabilitado}
          onChange={(valor) => cambiar({ emisor: valor === '' ? null : valor })}
          opciones={[
            { valor: '', texto: 'todos' },
            ...[...opciones.emisores].sort().map((emisor) => ({ valor: emisor, texto: emisor })),
          ]}
        />
      </div>

      {/* Los umbrales no son categorías del perfil, pero sí acotan sus opciones: subir la TIR
          mínima depura los cinco selects de arriba. */}
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

        <CampoSelect
          etiqueta="Liquidez mín. (percentil de volumen USD, sobre el universo a la vista)"
          valor={filtros.liquidezMin}
          disabled={deshabilitado}
          onChange={(valor) => cambiar({ liquidezMin: valor as FiltrosArmador['liquidezMin'] })}
          opciones={[
            { valor: '', texto: 'todos' },
            { valor: '25', texto: '≥ p25' },
            { valor: '50', texto: '≥ p50' },
            { valor: '75', texto: '≥ p75' },
          ]}
        />

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

      {apagadas.length > 0 && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--tx)' }}>
          Sin papeles en la ventana bajo el resto de los filtros, así que no se{' '}
          {apagadas.length === 1 ? 'aplica' : 'aplican'}:{' '}
          {apagadas
            .map(({ dimension, valor }) => `${ROTULO_DIMENSION[dimension]} «${etiquetaDe(valor)}»`)
            .join(', ')}
          .{/* La advertencia sólo tiene sentido si hay algo abajo que se pueda leer mal. */}
          {conteo.visibles > 0 && ' Lo que se ve abajo no cumple ese criterio.'}
        </p>
      )}

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

/** Los dos valores centinela se nombran como en su control, no con su clave interna. */
function etiquetaDe(valor: string): string {
  if (valor === LEY_NO_INFORMADA) return 'ley no informada'
  if (valor === CALIFICACION_NO_INFORMADA) return 'sin calificación'
  return valor
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
