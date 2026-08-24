/**
 * La barra de filtros de los fondos comunes — 23/08/2026.
 *
 * Mismo contrato que `FiltrosPerfil`: `value` de cada control lee de `efectivos` (la selección que
 * el facetado confirmó, no la cruda), así una selección sin respaldo aparece como "todos" en vez de
 * un valor fantasma que ya no filtra nada; `onChange` escribe el filtro crudo y todo se deriva en
 * cada render (ver `facetarFci`).
 *
 * Va en un solo componente —categóricos y rangos— porque acá no hay la historia que mantiene
 * separados a `FiltrosPerfil` y `FiltrosNumericos`. Los rangos quedan **siempre visibles**, sin
 * colapsable: un umbral activo escondido detrás de un `<details>` sería un filtro silencioso, justo
 * lo que el resto de la pantalla se ocupa de declarar.
 *
 * Los códigos propietarios de CAFCI se ofrecen verbatim (regla 11): `Cor`/`Lar`/`Flex` no se
 * traducen a corto/largo/flexible —CAFCI no publica ese diccionario— y `"NA"` y `"N/A"` aparecen
 * como dos calificaciones distintas porque la fuente las escribe distinto.
 */

import type { ReactNode } from 'react'

import {
  CALIFICACION_NO_INFORMADA,
  FILTROS_FCI_VACIOS,
  GERENTE_NO_INFORMADA,
  HORIZONTE_NO_INFORMADO,
  REGION_NO_INFORMADA,
  TIPO_DINERO_NO_INFORMADO,
  type DimensionFacetadaFci,
  type FiltrosFci,
  type OpcionesFacetadasFci,
  type SeleccionApagadaFci,
} from '../lib/filtrosFci'

const ROTULO_DIMENSION: Record<DimensionFacetadaFci, string> = {
  moneda: 'Moneda',
  seccion: 'Sección',
  tipoDinero: 'Tipo de dinero',
  region: 'Región',
  horizonte: 'Horizonte',
  calificaciones: 'Calificación',
  gerente: 'Gerente',
}

const ETIQUETA_CENTINELA: Record<string, string> = {
  [CALIFICACION_NO_INFORMADA]: 'sin calificación',
  [GERENTE_NO_INFORMADA]: 'gerente no informada',
  [REGION_NO_INFORMADA]: 'región no informada',
  [HORIZONTE_NO_INFORMADO]: 'horizonte no informado',
  [TIPO_DINERO_NO_INFORMADO]: 'tipo de dinero no informado',
}

function etiquetaDe(valor: string): string {
  return ETIQUETA_CENTINELA[valor] ?? valor
}

export function FiltrosFci({
  filtros,
  efectivos,
  opciones,
  apagadas,
  onCambio,
}: {
  filtros: FiltrosFci
  efectivos: FiltrosFci
  opciones: OpcionesFacetadasFci
  apagadas: SeleccionApagadaFci[]
  onCambio: (filtros: FiltrosFci) => void
}) {
  function cambiar(parcial: Partial<FiltrosFci>) {
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
        <Select
          etiqueta="Sección"
          valor={efectivos.seccion}
          opciones={opciones.secciones}
          onCambio={(seccion) => cambiar({ seccion })}
        />
        <Select
          etiqueta="Tipo de dinero"
          valor={efectivos.tipoDinero}
          opciones={opciones.tiposDinero}
          centinela={opciones.tieneTipoDineroNoInformado ? TIPO_DINERO_NO_INFORMADO : null}
          onCambio={(tipoDinero) => cambiar({ tipoDinero })}
        />
        <Select
          etiqueta="Región"
          valor={efectivos.region}
          opciones={opciones.regiones}
          centinela={opciones.tieneRegionNoInformada ? REGION_NO_INFORMADA : null}
          onCambio={(region) => cambiar({ region })}
        />
        <Select
          etiqueta="Horizonte"
          valor={efectivos.horizonte}
          opciones={opciones.horizontes}
          centinela={opciones.tieneHorizonteNoInformado ? HORIZONTE_NO_INFORMADO : null}
          onCambio={(horizonte) => cambiar({ horizonte })}
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
                <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>sin fondos en el segmento</span>
              )}
            </div>
          </details>
        </div>

        <Select
          etiqueta="Gerente"
          valor={efectivos.gerente}
          opciones={opciones.gerentes}
          centinela={opciones.tieneGerenteNoInformada ? GERENTE_NO_INFORMADA : null}
          onCambio={(gerente) => cambiar({ gerente })}
        />
      </div>

      <div style={estiloFila}>
        {RANGOS.map(({ rotulo, min, max }) => (
          <Rango
            key={rotulo}
            rotulo={rotulo}
            valorMin={filtros[min]}
            valorMax={filtros[max]}
            onCambioMin={(valor) => cambiar({ [min]: valor } as Partial<FiltrosFci>)}
            onCambioMax={(valor) => cambiar({ [max]: valor } as Partial<FiltrosFci>)}
          />
        ))}
        <button type="button" onClick={() => onCambio(FILTROS_FCI_VACIOS)} style={estiloBoton}>
          limpiar filtros
        </button>
      </div>

      {apagadas.length > 0 && (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--tx)' }}>
          Sin fondos en el segmento bajo el resto de los filtros, así que no se{' '}
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

/** Los cuatro períodos que CAFCI publica. No hay semanal ni semestral: la fuente no los publica y
 *  no queda serie histórica para derivarlos. */
const RANGOS: Array<{
  rotulo: string
  min: 'varDiariaMin' | 'varMesMin' | 'varAnioMin' | 'var12mMin'
  max: 'varDiariaMax' | 'varMesMax' | 'varAnioMax' | 'var12mMax'
}> = [
  { rotulo: 'Var. día', min: 'varDiariaMin', max: 'varDiariaMax' },
  { rotulo: 'Var. mes', min: 'varMesMin', max: 'varMesMax' },
  { rotulo: 'Var. año', min: 'varAnioMin', max: 'varAnioMax' },
  { rotulo: 'Var. 12m', min: 'var12mMin', max: 'var12mMax' },
]

function Rango({
  rotulo,
  valorMin,
  valorMax,
  onCambioMin,
  onCambioMax,
}: {
  rotulo: string
  valorMin: string
  valorMax: string
  onCambioMin: (valor: string) => void
  onCambioMax: (valor: string) => void
}) {
  return (
    <>
      <Campo etiqueta={`${rotulo} mín. (%)`}>
        <input
          type="number"
          inputMode="decimal"
          value={valorMin}
          onChange={(e) => onCambioMin(e.target.value)}
          style={estiloInputNumero}
        />
      </Campo>
      <Campo etiqueta={`${rotulo} máx. (%)`}>
        <input
          type="number"
          inputMode="decimal"
          value={valorMax}
          onChange={(e) => onCambioMax(e.target.value)}
          style={estiloInputNumero}
        />
      </Campo>
    </>
  )
}

function Select({
  etiqueta,
  valor,
  opciones,
  centinela,
  onCambio,
}: {
  etiqueta: string
  valor: string | null
  opciones: string[]
  /** El valor centinela de "dato no informado" si la dimensión lo tiene y hay fondos que lo usan. */
  centinela?: string | null
  onCambio: (valor: string | null) => void
}) {
  return (
    <Campo etiqueta={etiqueta}>
      <select
        value={valor ?? ''}
        onChange={(e) => onCambio(e.target.value === '' ? null : e.target.value)}
        style={estiloInput}
      >
        <option value="">todos</option>
        {opciones.map((opcion) => (
          <option key={opcion} value={opcion}>
            {opcion}
          </option>
        ))}
        {centinela != null && <option value={centinela}>{etiquetaDe(centinela)}</option>}
      </select>
    </Campo>
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
  minWidth: 108,
  font: 'inherit',
  fontSize: 12.5,
  padding: '5px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

const estiloInputNumero = { ...estiloInput, width: 96, minWidth: 96 } as const

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
