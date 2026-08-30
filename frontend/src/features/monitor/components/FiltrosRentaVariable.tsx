/**
 * Los filtros de diversificación de la renta variable — F-078 (fase 2) rediseñado por F-079
 * (fase 5, 29/08/2026).
 *
 * El pedido del dueño: la pared de chips ocupaba ~400-450px verticales antes de la tabla y quería
 * que alguien **sin idea de mercado** pudiera escribir "oro" o "farmacéuticas" y encontrar los
 * CEDEARs relevantes. Dos cambios de fondo respecto de F-078:
 *
 * 1. **Buscador de texto arriba de todo**, con sugerencias de preset cuando el texto matchea uno
 *    (`presetsQueCoinciden`) — la vía "no sé la jerga, pero sé lo que quiero" que los chips solos no
 *    resolvían.
 * 2. **Las seis dimensiones pasan de chips (`radiogroup`) a `CampoSelect`** (el `<select>` compacto
 *    compartido de F-079/D4): un chip por valor posible es lo que hacía crecer la pared a cientos de
 *    píxeles cuando un eje —país, sector— tiene decenas de opciones; un `<select>` con el conteo en
 *    el texto de cada opción cabe en una fila de ~40px sin importar cuántos valores tenga. Los
 *    presets siguen siendo píldoras (son pocos y se usan de un vistazo, así que el chip sigue siendo
 *    la forma correcta ahí — ver la spec de "chips temáticos" en `design-system.md`).
 *
 * El resultado apunta a ~90-100px de alto total: fila de búsqueda + presets, sugerencias (sólo si
 * hay), fila de hasta seis selects (autoocultado con <2 opciones, igual criterio que F-078), y el
 * párrafo de selecciones apagadas por el facetado.
 *
 * **Lo que el facetado apagó se declara.** Una selección sin respaldo bajo el resto de los filtros
 * no se aplica en fantasma ni desaparece en silencio: se nombra al pie, igual que antes.
 */

import type { CSSProperties } from 'react'

import { CampoSelect } from '@/components/CampoSelect'
import { PRESETS_RV } from '@/lib/presetsRv'

import {
  DIMENSIONES_RV,
  DETALLE_DIMENSION_RV,
  ROTULO_DIMENSION_RV,
  etiquetaDeValorRv,
  foldTexto,
  presetsQueCoinciden,
  tituloOpcionRv,
  type DimensionRv,
  type EtiquetasRv,
  type FiltrosRentaVariable,
  type OpcionesFacetadasRv,
  type SeleccionApagadaRv,
} from '../lib/filtrosRentaVariable'

function estiloPildora(activo: boolean): CSSProperties {
  return {
    font: 'inherit',
    fontSize: 11.5,
    padding: '4px 11px',
    borderRadius: 12,
    border: `1px solid ${activo ? 'var(--ac)' : 'var(--lin)'}`,
    background: activo ? 'var(--ac)' : 'transparent',
    color: activo ? 'var(--bg)' : 'var(--dim)',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  }
}

const ESTILO_ROTULO_FILA: CSSProperties = {
  fontSize: 10,
  color: 'var(--dim)',
  textTransform: 'uppercase',
  letterSpacing: '0.06em',
  whiteSpace: 'nowrap',
}

export function FiltrosRentaVariable({
  filtros,
  efectivos,
  opciones,
  apagadas,
  etiquetas,
  onCambio,
}: {
  /** El filtro crudo: lo que se escribe al tocar un select, un preset o el buscador. */
  filtros: FiltrosRentaVariable
  /** Lo que el facetado confirmó: de acá sale qué opción se muestra elegida, para que una
   *  selección apagada no aparezca marcada sobre una tabla que ya no está filtrando por ella. */
  efectivos: FiltrosRentaVariable
  opciones: OpcionesFacetadasRv
  apagadas: SeleccionApagadaRv[]
  /** Los mapas de etiqueta de sector/rubro específico que devolvió `facetarRentaVariable`, para
   *  no recalcularlos acá y arriesgarse a divergir. */
  etiquetas: EtiquetasRv
  onCambio: (filtros: FiltrosRentaVariable) => void
}) {
  function elegirDimension(dimension: DimensionRv, valor: string) {
    onCambio({ ...filtros, [dimension]: valor === '' ? null : valor })
  }

  const textoFoldeado = foldTexto(filtros.busqueda.trim())
  // El preset ya activo no es una "sugerencia": tocarlo de nuevo no cambiaría nada.
  const sugerencias = presetsQueCoinciden(textoFoldeado).filter(
    (preset) => preset.id !== efectivos.presetId,
  )

  const filas = DIMENSIONES_RV.filter((dimension) => opciones.porDimension[dimension].length >= 2)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, margin: '10px 0 2px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
        <input
          type="text"
          value={filtros.busqueda}
          onChange={(evento) => onCambio({ ...filtros, busqueda: evento.target.value })}
          placeholder="Buscar ticker, nombre, rubro… (ej: oro, farmacéuticas)"
          aria-label="Buscar en renta variable"
          style={{
            flex: '1 1 220px',
            minWidth: 180,
            font: 'inherit',
            fontSize: 12,
            color: 'var(--tx)',
            background: 'var(--pan2)',
            border: '1px solid var(--lin)',
            borderRadius: 3,
            padding: '5px 8px',
          }}
        />
        <span style={ESTILO_ROTULO_FILA}>Temáticas</span>
        {PRESETS_RV.map((preset) => {
          const activo = efectivos.presetId === preset.id
          return (
            <button
              key={preset.id}
              type="button"
              aria-pressed={activo}
              // Segundo clic sobre el preset activo lo saca: es un atajo, no un modo del que haya
              // que salir por otra puerta.
              onClick={() => onCambio({ ...filtros, presetId: activo ? null : preset.id })}
              title={preset.nota}
              style={estiloPildora(activo)}
            >
              {preset.etiqueta}
            </button>
          )
        })}
      </div>

      {sugerencias.length > 0 && (
        <div
          role="group"
          aria-label="Sugerencias de temáticas para la búsqueda"
          style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}
        >
          <span style={{ fontSize: 11, color: 'var(--dim)' }}>¿Buscabas?</span>
          {sugerencias.map((preset) => (
            <button
              key={preset.id}
              type="button"
              // Elegir la sugerencia activa el preset y limpia el texto: el atajo ya reemplaza lo
              // que se estaba tipeando, no conviven los dos recortes a la vez.
              onClick={() => onCambio({ ...filtros, presetId: preset.id, busqueda: '' })}
              title={preset.nota}
              style={estiloPildora(false)}
            >
              {preset.etiqueta}
            </button>
          ))}
        </div>
      )}

      {filas.length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {filas.map((dimension) => {
            const total = opciones.totalPorDimension[dimension]
            const opcionesCampo = [
              { valor: '', texto: `Todos (${total})` },
              ...opciones.porDimension[dimension].map((opcion) => ({
                valor: opcion.valor,
                texto: `${etiquetaDeValorRv(dimension, opcion.valor, etiquetas)} (${opcion.especies})`,
                title: tituloOpcionRv(dimension, opcion.valor, etiquetas),
              })),
            ]
            return (
              <CampoSelect
                key={dimension}
                etiqueta={ROTULO_DIMENSION_RV[dimension]}
                valor={efectivos[dimension] ?? ''}
                onChange={(valor) => elegirDimension(dimension, valor)}
                opciones={opcionesCampo}
                title={DETALLE_DIMENSION_RV[dimension]}
              />
            )
          })}
        </div>
      )}

      {apagadas.length > 0 && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--tx)' }}>
          Sin papeles bajo el resto de los filtros, así que no se{' '}
          {apagadas.length === 1 ? 'aplica' : 'aplican'}:{' '}
          {apagadas
            .map(
              ({ dimension, valor }) =>
                `${ROTULO_DIMENSION_RV[dimension]} «${etiquetaDeValorRv(dimension, valor, etiquetas)}»`,
            )
            .join(', ')}
          .
        </p>
      )}
    </div>
  )
}
