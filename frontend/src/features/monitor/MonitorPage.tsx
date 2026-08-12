/**
 * Monitor de mercado — F-038.
 *
 * La entrada diaria: el universo por segmento, para consultar sin armar nada. Un solo segmento
 * activo por vez (regla 2 del dominio): la barra de estado del dato (F-013) ya está montada en
 * `AppLayout` para las seis pantallas, así que GWT-3 —hora del snapshot, demora, descartes,
 * cobertura— ya está cumplido acá sin que esta pantalla haga nada.
 *
 * ## Dos ejes más de segmentación, agregados el 08/08/2026
 *
 * La grilla mostraba las tres especies de cada emisión como filas sueltas y el dólar hard entero
 * —764 de las 942 de renta fija— en una sola pestaña. Las dos cosas se arreglan repartiendo, sin
 * pedirle nada nuevo al backend y sin ocultar una fila:
 *
 * 1. **La moneda es un modo, no una columna** (`SelectorMoneda`). Con una sola moneda en pantalla
 *    hay una fila por emisión, el precio no necesita decir su unidad en cada celda y el volumen se
 *    muestra crudo sin convertir nada — que es lo que la regla 11 exige para las especies `EXT`.
 * 2. **El dólar hard se abre por crédito** (`SEGMENTO_POR_CREDITO`): Soberanos, Subsoberanos y ONs.
 *    Es la regla 4 del dominio en la navegación.
 *
 * Las dos particiones son **client-side sobre la misma query cacheada**: el segmento que se le pide
 * al backend sigue siendo `usd_hard`, así que moverse entre las tres pestañas o entre monedas no
 * dispara un pedido. Por eso `useUniversoSegmento` recibe `segmentoDeClave(activo)` y no `activo`.
 */

import { useEffect, useMemo, useState } from 'react'

import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { SelectorMoneda, contarPorMoneda, monedaInicial, SIN_MONEDA_DECLARADA } from '@/components/SelectorMoneda'
import {
  CLAVES_RENTA_VARIABLE,
  SEGMENTO_POR_CREDITO,
  SelectorSegmento,
  claseDeClave,
  expandirSegmentos,
  nombreSegmento,
  ordenarSegmentos,
  segmentoDeClave,
} from '@/components/SelectorSegmento'
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
  // Se expande primero para que el default sea una pestaña real y no `usd_hard`, que ya no existe
  // como pestaña del monitor.
  useEffect(() => {
    if (activo !== null || !segmentos.data) return
    const [primero] = ordenarSegmentos(expandirSegmentos(segmentos.data.segmentos.map((s) => s.clave)))
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
                  ? [...expandirSegmentos(segmentos.data.segmentos.map((s) => s.clave)), ...CLAVES_RENTA_VARIABLE]
                  : expandirSegmentos(segmentos.data.segmentos.map((s) => s.clave))
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
                key={activo}
                clave={activo}
                naturaleza={
                  segmentos.data.segmentos.find((s) => s.clave === segmentoDeClave(activo))?.naturaleza ?? ''
                }
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

/**
 * Qué moneda conviene mostrar al abrir cada segmento, cuando el segmento la tiene.
 *
 * No es una regla del dominio, es dónde está la liquidez: el hard dollar se opera en dólares y las
 * curvas en pesos, en pesos. `monedaInicial` se encarga de no imponerla sobre un segmento que no
 * la tenga — preferir una moneda vacía dejaría la tabla en blanco sobre un universo con datos.
 */
const MONEDA_PREFERIDA: Record<string, string> = {
  usd_hard: 'USD',
}
const MONEDA_PREFERIDA_POR_DEFECTO = 'ARS'

function UniversoDelSegmento({
  clave,
  naturaleza,
  filtros,
  onCambioFiltros,
}: {
  /** La clave de la pestaña, que puede ser un segmento (`cer`) o una de crédito
   * (`usd_hard/bono_soberano`). El pedido al backend usa sólo la primera parte. */
  clave: string
  /** La naturaleza del segmento activo, tal como la declara `/segmentos`. No se infiere de la
   * primera fila del universo: si el universo todavía no llegó, igual hay que saber la unidad
   * para dibujar los filtros. */
  naturaleza: string
  filtros: FiltrosUniverso
  onCambioFiltros: (filtros: FiltrosUniverso) => void
}) {
  const segmento = segmentoDeClave(clave)
  const clase = claseDeClave(clave)
  const universo = useUniversoSegmento(segmento)
  const [moneda, setMoneda] = useState<string | null>(null)

  // Las especies de esta pestaña: el segmento entero, o sólo una clase de activo si la pestaña es
  // de crédito. Es un filtro sobre `clase_activo`, que es dato declarado por la fuente.
  const deLaPestania = useMemo(() => {
    const filas = universo.data ?? []
    return clase === null ? filas : filas.filter((e) => e.clase_activo === clase)
  }, [universo.data, clase])

  // Un segmento partido en pestañas puede perder filas si la fuente empieza a declarar una clase de
  // activo que ninguna pestaña cubre: no entrarían en ninguna y desaparecerían sin que nada avise.
  // Hoy da cero —las tres pestañas cubren las tres clases de renta fija de `SUBMARKET_MAP`— y por
  // eso se cuenta: el día que no dé cero, el número aparece en pantalla en vez de esconderse.
  const sinPestania = useMemo(() => {
    const clases = SEGMENTO_POR_CREDITO[segmento]
    if (!clases) return 0
    return (universo.data ?? []).filter((e) => !clases.includes(e.clase_activo)).length
  }, [universo.data, segmento])

  const monedas = useMemo(() => contarPorMoneda(deLaPestania), [deLaPestania])
  const activa =
    moneda ?? monedaInicial(monedas, MONEDA_PREFERIDA[segmento] ?? MONEDA_PREFERIDA_POR_DEFECTO)

  const deLaMoneda = useMemo(
    () =>
      deLaPestania.filter((e) => (e.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) === activa),
    [deLaPestania, activa],
  )

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

  // Va antes del early-return de "no hay especies" a propósito: el caso en que este número no es
  // cero es exactamente el caso en que la pestaña puede quedar vacía, y el aviso tiene que verse
  // sobre todo ahí — si no, la pantalla diría "no hay nada" sobre un segmento que sí tiene filas.
  const avisoSinPestania = sinPestania > 0 && (
    <p className="mono" style={{ margin: '10px 0 0', fontSize: 11, color: 'var(--neg)' }}>
      {fmtNumero(sinPestania, 0)} de este segmento no entran en ninguna de estas pestañas: su clase
      de activo no es ninguna de las que reparten el segmento.
    </p>
  )

  if (activa === null) {
    return (
      <>
        {avisoSinPestania}
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          No hay especies de {nombreSegmento(clave)} en el universo de hoy.
        </p>
      </>
    )
  }

  return (
    <>
      <SelectorMoneda disponibles={monedas} activa={activa} onCambio={setMoneda} />
      {avisoSinPestania}
      <FiltrosNumericos naturaleza={naturaleza} valores={filtros} onCambio={onCambioFiltros} />
      <TablaUniverso especies={deLaMoneda} naturaleza={naturaleza} filtros={filtros} moneda={activa} />
      <div style={{ marginTop: 16 }}>
        {/* La curva también sale de una sola moneda: es rendimiento contra duración, y aunque el
            rendimiento sea comparable entre hermanas, mezclarlas dibujaba tres puntos por emisión
            sobre las mismas coordenadas. */}
        <CurvaSegmento especies={deLaMoneda} naturaleza={naturaleza} />
      </div>
    </>
  )
}

/**
 * Las pestañas de acciones y CEDEARs — F-052. Sin `FiltrosNumericos` (sus campos de rendimiento y
 * duración son magnitudes que la renta variable no tiene) y sin `CurvaSegmento` (es rendimiento vs
 * duración: no hay ejes que dibujar).
 *
 * **El selector de moneda sí aplica** (08/08/2026): un CEDEAR cotiza en las mismas tres
 * denominaciones que un bono —hoy 659 acciones en `ARS`, 417 en `USD` y 341 en `EXT`— y mezclarlas
 * hacía lo mismo de siempre, ordenar por volumen poniendo arriba a las de pesos por el tipo de
 * cambio. Es el único de los cambios de esta pantalla que cruza a esta rama.
 */
function RentaVariableDelMonitor({ clase }: { clase: string }) {
  const rentaVariable = useRentaVariable(clase)
  const abrirInstrumento = useAbrirInstrumento()
  const [moneda, setMoneda] = useState<string | null>(null)

  const monedas = useMemo(() => contarPorMoneda(rentaVariable.data ?? []), [rentaVariable.data])
  const activa = moneda ?? monedaInicial(monedas, MONEDA_PREFERIDA_POR_DEFECTO)
  const deLaMoneda = useMemo(
    () =>
      (rentaVariable.data ?? []).filter(
        (e) => (e.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) === activa,
      ),
    [rentaVariable.data, activa],
  )

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
    <>
      {activa !== null && (
        <SelectorMoneda disponibles={monedas} activa={activa} onCambio={setMoneda} />
      )}
      <TablaRentaVariable
        especies={deLaMoneda}
        etiqueta={nombreSegmento(clase)}
        moneda={activa}
        onAbrirTicker={abrirInstrumento}
      />
    </>
  )
}
