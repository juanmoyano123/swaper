/**
 * Monitor de mercado — F-038.
 *
 * La entrada diaria: el universo por segmento, para consultar sin armar nada. Un solo segmento
 * activo por vez (regla 2 del dominio): la barra de estado del dato (F-013) ya está montada en
 * `AppLayout` para las seis pantallas, así que GWT-3 —hora del snapshot, demora, descartes,
 * cobertura— ya está cumplido acá sin que esta pantalla haga nada.
 */

import { useEffect, useState } from 'react'

import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { CLAVES_RENTA_VARIABLE, SelectorSegmento, nombreSegmento, ordenarSegmentos } from '@/components/SelectorSegmento'
import { TablaRentaVariable } from '@/components/TablaRentaVariable'
import { fmtNumero } from '@/lib/fmt'
import { useRentaVariable } from '@/lib/rentaVariable'

import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'

import { CurvaSegmento } from './components/CurvaSegmento'
import { FILTROS_VACIOS, FiltrosNumericos, type FiltrosUniverso } from './components/FiltrosNumericos'
import { TablaUniverso } from './components/TablaUniverso'
import { useSegmentos } from './hooks/useSegmentos'
import { useUniversoSegmento } from './hooks/useUniversoSegmento'

export function MonitorPage() {
  const segmentos = useSegmentos()
  const [activo, setActivo] = useState<string | null>(null)
  const [filtros, setFiltros] = useState<FiltrosUniverso>(FILTROS_VACIOS)

  // El default es el primero en el orden del design system, no el primero que llegó de la API:
  // el orden de pestañas es fijo, y `ordenarSegmentos` es la misma función que ordena la barra.
  useEffect(() => {
    if (activo !== null || !segmentos.data) return
    const [primero] = ordenarSegmentos(segmentos.data.segmentos.map((s) => s.clave))
    if (primero) setActivo(primero)
  }, [activo, segmentos.data])

  return (
    <Pantalla titulo="Monitor de mercado" bajada="El universo por segmento, con filtros y orden, para consultar sin armar una cartera.">
      <Panel rotulo="Universo">
        {segmentos.isPending && <p style={{ color: 'var(--dim)', fontSize: 12.5 }}>consultando el universo…</p>}

        {segmentos.isError && (
          <EstadoVacio
            titulo="No se pudo leer el universo de hoy."
            detalle={
              <>
                No hay forma de saber qué instrumentos tiene el mercado en este momento.{' '}
                <button
                  type="button"
                  onClick={() => void segmentos.refetch()}
                  style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
                >
                  reintentar
                </button>
              </>
            }
          />
        )}

        {segmentos.data && segmentos.data.segmentos.length === 0 && (
          <EstadoVacio
            titulo="Todavía no hay instrumentos para mostrar."
            detalle="La grilla del universo la construye F-038, y los datos llegan cuando corra la primera ingesta de mercado (F-004 a F-007)."
          />
        )}

        {segmentos.data && segmentos.data.segmentos.length > 0 && activo && (
          <>
            <SelectorSegmento
              segmentos={
                segmentos.data.renta_variable > 0
                  ? [...segmentos.data.segmentos.map((s) => s.clave), ...CLAVES_RENTA_VARIABLE]
                  : segmentos.data.segmentos.map((s) => s.clave)
              }
              activo={activo}
              onCambio={(clave) => {
                setActivo(clave)
                setFiltros(FILTROS_VACIOS) // el rendimiento de un segmento distinto no es comparable con el filtro anterior
              }}
            />
            <p className="mono" style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--dim)' }}>
              {fmtNumero(segmentos.data.sin_segmento, 0)} sin segmento no se muestran acá.
            </p>

            {(CLAVES_RENTA_VARIABLE as readonly string[]).includes(activo) ? (
              <RentaVariableDelMonitor clase={activo} />
            ) : (
              <UniversoDelSegmento
                segmento={activo}
                naturaleza={segmentos.data.segmentos.find((s) => s.clave === activo)?.naturaleza ?? ''}
                filtros={filtros}
                onCambioFiltros={setFiltros}
              />
            )}
          </>
        )}
      </Panel>
    </Pantalla>
  )
}

function UniversoDelSegmento({
  segmento,
  naturaleza,
  filtros,
  onCambioFiltros,
}: {
  segmento: string
  /** La naturaleza del segmento activo, tal como la declara `/segmentos`. No se infiere de la
   * primera fila del universo: si el universo todavía no llegó, igual hay que saber la unidad
   * para dibujar los filtros. */
  naturaleza: string
  filtros: FiltrosUniverso
  onCambioFiltros: (filtros: FiltrosUniverso) => void
}) {
  const universo = useUniversoSegmento(segmento)

  if (universo.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando el segmento…</p>
  }

  if (universo.isError) {
    return (
      <EstadoVacio
        titulo="No se pudo traer este segmento."
        detalle={
          <button
            type="button"
            onClick={() => void universo.refetch()}
            style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          >
            reintentar
          </button>
        }
      />
    )
  }

  return (
    <>
      <FiltrosNumericos naturaleza={naturaleza} valores={filtros} onCambio={onCambioFiltros} />
      <TablaUniverso especies={universo.data} naturaleza={naturaleza} filtros={filtros} />
      <div style={{ marginTop: 16 }}>
        <CurvaSegmento especies={universo.data} naturaleza={naturaleza} />
      </div>
    </>
  )
}

/**
 * Las pestañas de acciones y CEDEARs — F-052. Sin `FiltrosNumericos` (sus tres campos son
 * rendimiento mín/máx y duración máx, magnitudes que la renta variable no tiene) y sin
 * `CurvaSegmento` (es rendimiento vs duración: no hay ejes que dibujar).
 */
function RentaVariableDelMonitor({ clase }: { clase: string }) {
  const rentaVariable = useRentaVariable(clase)
  const abrirInstrumento = useAbrirInstrumento()

  if (rentaVariable.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando el segmento…</p>
  }

  if (rentaVariable.isError) {
    return (
      <EstadoVacio
        titulo="No se pudo traer este segmento."
        detalle={
          <button
            type="button"
            onClick={() => void rentaVariable.refetch()}
            style={{ color: 'var(--ac)', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
          >
            reintentar
          </button>
        }
      />
    )
  }

  return (
    <TablaRentaVariable
      especies={rentaVariable.data}
      etiqueta={nombreSegmento(clase)}
      onAbrirTicker={abrirInstrumento}
    />
  )
}
