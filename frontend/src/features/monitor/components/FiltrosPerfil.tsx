/**
 * La fila del perfil — Ley, Sector, Calificación, Emisor — con facetado en cascada (14/08/2026).
 *
 * Portado (no importado — `features/monitor/**` y `features/armador/**` no se importan entre sí)
 * del mismo markup que `armador/components/FiltrosGrilla.tsx`, sobre el motor común de
 * `@/lib/facetado`. `value` de cada select lee de `efectivos` (la selección que el facetado
 * confirmó, no la cruda): así una selección sin respaldo aparece como "todos" en vez de un valor
 * fantasma que ya no filtra nada. `onChange` sigue escribiendo el filtro crudo — nada se sincroniza
 * con `setState`, todo se deriva en cada render (ver `facetarUniverso`).
 *
 * Ley, Sector y Emisor usan `@/components/CampoSelect` (F-079, Fase 4): es el select compartido
 * que reemplazó la copia local de `estiloInput` para estos tres. Calificación queda afuera —es un
 * multiselect con `<details>`, no un `<select>`— y sigue usando `estiloInput` directamente.
 */

import { CampoSelect } from '@/components/CampoSelect'

import {
  CALIFICACION_NO_INFORMADA,
  LEY_NO_INFORMADA,
  type DimensionFacetadaUniverso,
  type FiltrosUniverso,
  type OpcionesFacetadasUniverso,
  type SeleccionApagadaUniverso,
} from '../lib/filtros'

const ROTULO_DIMENSION: Partial<Record<DimensionFacetadaUniverso, string>> = {
  credito: 'Crédito',
  moneda: 'Moneda',
  ley: 'Ley',
  sector: 'Sector',
  calificaciones: 'Calificación',
  emisor: 'Emisor',
}

function etiquetaDe(valor: string): string {
  if (valor === LEY_NO_INFORMADA) return 'ley no informada'
  if (valor === CALIFICACION_NO_INFORMADA) return 'sin calificación'
  return valor
}

export function FiltrosPerfil({
  filtros,
  efectivos,
  opciones,
  apagadas,
  onCambio,
}: {
  filtros: FiltrosUniverso
  efectivos: FiltrosUniverso
  opciones: OpcionesFacetadasUniverso
  apagadas: SeleccionApagadaUniverso[]
  onCambio: (filtros: FiltrosUniverso) => void
}) {
  function cambiar(parcial: Partial<FiltrosUniverso>) {
    onCambio({ ...filtros, ...parcial })
  }

  function alternarCalificacion(valor: string) {
    const activa = filtros.calificaciones.includes(valor)
    cambiar({
      calificaciones: activa
        ? filtros.calificaciones.filter((c) => c !== valor)
        : [...filtros.calificaciones, valor],
    })
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={estiloFila}>
        <CampoSelect
          etiqueta="Ley"
          valor={efectivos.ley ?? ''}
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
              style={{ ...estiloInput, display: 'inline-block', cursor: 'pointer', listStyle: 'none' }}
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
                    onChange={() => alternarCalificacion(CALIFICACION_NO_INFORMADA)}
                  />
                  sin calificación
                </label>
              )}
              {opciones.calificaciones.length === 0 && !opciones.tieneCalificacionNoInformada && (
                <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>sin especies en el segmento</span>
              )}
            </div>
          </details>
        </div>

        <CampoSelect
          etiqueta="Emisor"
          valor={efectivos.emisor ?? ''}
          onChange={(valor) => cambiar({ emisor: valor === '' ? null : valor })}
          opciones={[
            { valor: '', texto: 'todos' },
            ...[...opciones.emisores].sort().map((emisor) => ({ valor: emisor, texto: emisor })),
          ]}
        />
      </div>

      {apagadas.length > 0 && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--tx)' }}>
          Sin especies en el segmento bajo el resto de los filtros, así que no se{' '}
          {apagadas.length === 1 ? 'aplica' : 'aplican'}:{' '}
          {apagadas
            .map(({ dimension, valor }) => `${ROTULO_DIMENSION[dimension]} «${etiquetaDe(valor)}»`)
            .join(', ')}
          .
        </p>
      )}
    </div>
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
  minWidth: 108,
  font: 'inherit',
  fontSize: 12.5,
  padding: '5px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const
