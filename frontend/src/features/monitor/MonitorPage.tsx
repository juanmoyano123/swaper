/**
 * Monitor de mercado — F-038.
 *
 * La entrada diaria: el universo por segmento, para consultar sin armar nada. Un solo segmento
 * activo por vez (regla 2 del dominio): la barra de estado del dato (F-013) ya está montada en
 * `AppLayout` para las seis pantallas, así que GWT-3 —hora del snapshot, demora, descartes,
 * cobertura— ya está cumplido acá sin que esta pantalla haga nada.
 *
 * ## Jerarquía de dos niveles + chips, reordenada el 14/08/2026
 *
 * La barra de pestañas mezclaba tres clasificaciones sin decirlo: tipo de tasa (Dólar hard, CER,
 * Tasa fija $...), crédito (Soberanos/Subsoberanos/ONs, que sólo existía para el dólar hard) y
 * renta variable (CEDEARs). Cada especie caía en una sola pestaña, pero la barra plana lo hacía ver
 * como si el mismo papel apareciera repetido en varias. Se ordena en dos niveles y dos chips:
 *
 * 1. **Familia** (`SelectorFamilia`): Renta fija / Renta variable. El corte más grueso.
 * 2. **Segmento** (`SelectorSegmento`, con las claves del backend sin partir): tipo de tasa, dentro
 *    de renta fija. Es la regla 2 hecha pestaña — nunca dos naturalezas de rendimiento a la vista.
 * 3. **Crédito** (`SelectorCredito`, chip): Todos / Soberanos / Subsoberanos / ONs, dentro del
 *    segmento activo. Generaliza a los seis segmentos lo que antes sólo existía para el dólar hard.
 *    "Todos" es válido porque el crédito no cambia la unidad del rendimiento (regla 2); lo que
 *    separa es el riesgo emisor (regla 4).
 * 4. **Moneda** (`SelectorMoneda`, chip): un eje más abajo, sin cambios respecto de antes.
 *
 * Las tres particiones de abajo de la familia son **client-side sobre la misma query cacheada por
 * segmento**: moverse entre segmento/crédito/moneda no dispara un pedido nuevo salvo al cambiar de
 * segmento, porque ahí sí cambia el `?segmento=` que se le pide al backend.
 *
 * Renta variable no tiene segundo nivel propio hoy: `CLAVES_RENTA_VARIABLE` sólo tiene `cedear`, así
 * que la pestaña de familia va directo a la tabla, sin una sub-barra de una sola opción. Si mañana
 * vuelve una segunda clase, la sub-barra reaparece sola (ver `RamaRentaVariable`).
 *
 * **FCI (F-057, 23/08/2026) es la tercera familia.** Sí tiene segundo nivel — el tipo de renta del
 * fondo (Renta Fija, Mercado de Dinero…) — con las mismas claves prefijadas `fci_` de
 * `SelectorSegmento`, y un chip de moneda (ARS/USD/USB) igual que renta fija. Sin chip de crédito:
 * un fondo no tiene emisor con crédito comparable. Ver `RamaFci` más abajo.
 */

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'
import { SelectorCredito, contarPorCredito } from '@/components/SelectorCredito'
import { SelectorMoneda, contarPorMoneda, monedaInicial, SIN_MONEDA_DECLARADA } from '@/components/SelectorMoneda'
import { CLAVES_RENTA_VARIABLE, SelectorSegmento, nombreSegmento, ordenarSegmentos } from '@/components/SelectorSegmento'
import { TablaFci } from '@/components/TablaFci'
import { TablaRentaVariable } from '@/components/TablaRentaVariable'
import { claveTipoRenta, tipoRentaDeClave, useFondosFci, useSegmentosFci, type PlanillaFci } from '@/lib/fci'
import { fmtNumero } from '@/lib/fmt'
import { useRentaVariable } from '@/lib/rentaVariable'

import { useAbrirFondoFci } from '@/features/instrumento/useAbrirFondoFci'
import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'

import { CurvaSegmento } from './components/CurvaSegmento'
import { FiltrosNumericos } from './components/FiltrosNumericos'
import { FiltrosPerfil } from './components/FiltrosPerfil'
import { SelectorFamilia, type Familia } from './components/SelectorFamilia'
import { TablaUniverso } from './components/TablaUniverso'
import { useSegmentos } from './hooks/useSegmentos'
import { useUniversoSegmento } from './hooks/useUniversoSegmento'
import { FILTROS_VACIOS, facetarUniverso, pasaFiltros, type FiltrosUniverso } from './lib/filtros'

export function MonitorPage() {
  const segmentos = useSegmentos()
  const segmentosFci = useSegmentosFci()
  const [familia, setFamilia] = useState<Familia>('renta_fija')
  const [activo, setActivo] = useState<string | null>(null)
  const [filtros, setFiltros] = useState<FiltrosUniverso>(FILTROS_VACIOS)

  const familiasDisponibles = useMemo((): Familia[] => {
    if (!segmentos.data) return []
    const familias: Familia[] = []
    if (segmentos.data.segmentos.length > 0) familias.push('renta_fija')
    if (segmentos.data.renta_variable > 0) familias.push('renta_variable')
    if ((segmentosFci.data?.segmentos.length ?? 0) > 0) familias.push('fci')
    return familias
  }, [segmentos.data, segmentosFci.data])

  // El default es el primero en el orden del design system, no el primero que llegó de la API.
  useEffect(() => {
    if (activo !== null || !segmentos.data) return
    const [primero] = ordenarSegmentos(segmentos.data.segmentos.map((s) => s.clave))
    if (primero) setActivo(primero)
  }, [activo, segmentos.data])

  // Si la familia elegida se queda sin datos (o todavía no se eligió ninguna), cae en la primera
  // disponible. Cubre el arranque y el caso —hoy hipotético— de un universo sin renta fija.
  useEffect(() => {
    if (familiasDisponibles.length === 0 || familiasDisponibles.includes(familia)) return
    setFamilia(familiasDisponibles[0])
  }, [familia, familiasDisponibles])

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

        {segmentos.data && familiasDisponibles.length === 0 && (
          <EstadoVacio
            titulo="Todavía no hay instrumentos para mostrar."
            detalle="La grilla del universo la construye F-038, y los datos llegan cuando corra la primera ingesta de mercado (F-004 a F-007)."
          />
        )}

        {segmentos.data && familiasDisponibles.length > 0 && (
          <>
            <SelectorFamilia activa={familia} onCambio={setFamilia} disponibles={familiasDisponibles} />
            <p className="mono" style={{ margin: '8px 0 0', fontSize: 11, color: 'var(--dim)' }}>
              {fmtNumero(segmentos.data.sin_segmento, 0)} sin segmento no se muestran acá.
            </p>

            {familia === 'renta_variable' ? (
              <RamaRentaVariable />
            ) : familia === 'fci' ? (
              <RamaFci segmentos={segmentosFci.data?.segmentos ?? []} planilla={segmentosFci.data?.planilla ?? null} />
            ) : (
              activo && (
                <>
                  <SelectorSegmento
                    segmentos={segmentos.data.segmentos.map((s) => s.clave)}
                    activo={activo}
                    onCambio={(clave) => {
                      setActivo(clave)
                      setFiltros(FILTROS_VACIOS) // el rendimiento de un segmento distinto no es comparable con el filtro anterior
                    }}
                  />
                  <UniversoDelSegmento
                    key={activo}
                    segmento={activo}
                    naturaleza={segmentos.data.segmentos.find((s) => s.clave === activo)?.naturaleza ?? ''}
                    filtros={filtros}
                    onCambioFiltros={setFiltros}
                  />
                </>
              )
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
  const deLSegmento = useMemo(() => universo.data ?? [], [universo.data])

  // Facetado en cascada (14/08/2026): crédito, moneda, ley, sector, calificación y emisor se
  // validan juntos y las opciones de cada uno se acotan por lo que dejan los demás — ver
  // `facetarUniverso` en `lib/filtros.ts`. `efectivos` es lo que realmente filtra: una selección
  // sin respaldo (p. ej. un crédito sin especies en la ley elegida) queda en `apagadas` y se
  // declara, no se aplica en fantasma.
  const { opciones, efectivos, apagadas } = useMemo(
    () => facetarUniverso(deLSegmento, filtros),
    [deLSegmento, filtros],
  )

  // Los chips de crédito y moneda muestran conteos, no sólo una lista de valores posibles: se
  // calculan aparte, cada uno sobre el subconjunto que deja el resto de los filtros (la propia
  // dimensión neutralizada) — mismo criterio *leave-one-out* que ya aplica `facetarUniverso` para
  // sector/ley/calificación/emisor.
  const especiesParaCredito = useMemo(
    () => deLSegmento.filter((e) => pasaFiltros(e, { ...efectivos, credito: null })),
    [deLSegmento, efectivos],
  )
  const creditos = useMemo(() => contarPorCredito(especiesParaCredito), [especiesParaCredito])

  const especiesParaMoneda = useMemo(
    () => deLSegmento.filter((e) => pasaFiltros(e, { ...efectivos, moneda: null })),
    [deLSegmento, efectivos],
  )
  const monedas = useMemo(() => contarPorMoneda(especiesParaMoneda), [especiesParaMoneda])

  // La moneda nunca se filtra en "todas mezcladas" (regla 3): si no se eligió a mano, o si la
  // elegida quedó apagada por no tener especies bajo el resto de los filtros, se resuelve a una
  // concreta entre las que sí tienen especies — la preferida del segmento si está, si no la de
  // mayor volumen. `monedaInicial` devuelve `null` sólo cuando no queda ninguna.
  const activa =
    efectivos.moneda ?? monedaInicial(monedas, MONEDA_PREFERIDA[segmento] ?? MONEDA_PREFERIDA_POR_DEFECTO)

  // Filtros ya resueltos del todo, para la tabla y la curva: iguales a `efectivos` salvo que la
  // moneda queda concreta.
  const filtrosResueltos = useMemo(() => ({ ...efectivos, moneda: activa }), [efectivos, activa])

  // Filtrado por crédito y moneda solamente — el "M" del conteo "N de M" de la tabla, y también lo
  // que ve la curva. Ley/sector/calificación/emisor y los umbrales los aplica `TablaUniverso` con
  // `filtrosResueltos`: `especies` acá no baja más que crédito+moneda a propósito, porque "cuántas
  // hay bajo este crédito y esta moneda" es una pregunta distinta de "cuántas pasan todo lo demás"
  // (la curva, en particular, sólo quiere la primera — no lleva los umbrales ni las dimensiones
  // nuevas, sigue siendo rendimiento contra duración del recorte de siempre).
  const deLaMoneda = useMemo(
    () =>
      deLSegmento
        .filter((e) => efectivos.credito === null || e.clase_activo === efectivos.credito)
        .filter((e) => (e.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) === activa),
    [deLSegmento, efectivos.credito, activa],
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

  // Segmento sin una sola especie, sea cual sea el crédito: no hay filtro que ofrecer sobre nada.
  // Distinto de que los filtros elegidos dejen cero — eso sigue mostrando la barra (abajo), porque
  // ahí lo que falta es la combinación, no el dato.
  if (deLSegmento.length === 0) {
    return (
      <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
        No hay especies de {nombreSegmento(segmento)} en el universo de hoy.
      </p>
    )
  }

  return (
    <>
      <SelectorCredito
        total={especiesParaCredito.length}
        disponibles={creditos.disponibles}
        otras={creditos.otras}
        activo={efectivos.credito}
        onCambio={(c) => onCambioFiltros({ ...filtros, credito: c })}
      />
      {/* `activa` puede ser `null` de forma transitoria —p. ej. mientras se tipea un rango de
          rendimiento que por un instante queda invertido— sin que eso signifique que no hay
          monedas: `SelectorMoneda` necesita una activa concreta, así que sólo se monta cuando hay
          alguna. La barra de filtros de abajo se queda montada siempre: no hay motivo para que
          desaparezca (y con ella el input donde el asesor sigue escribiendo) por un estado de
          filtrado que se resuelve solo en el próximo tipeo. */}
      {activa !== null && (
        <SelectorMoneda disponibles={monedas} activa={activa} onCambio={(m) => onCambioFiltros({ ...filtros, moneda: m })} />
      )}
      <FiltrosPerfil filtros={filtros} efectivos={efectivos} opciones={opciones} apagadas={apagadas} onCambio={onCambioFiltros} />
      <FiltrosNumericos naturaleza={naturaleza} valores={filtros} onCambio={onCambioFiltros} />
      {activa === null ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          Ninguna especie pasa los filtros activos.
        </p>
      ) : (
        <>
          <TablaUniverso especies={deLaMoneda} naturaleza={naturaleza} filtros={filtrosResueltos} moneda={activa} />
          <div style={{ marginTop: 16 }}>
            {/* La curva también sale de una sola moneda: es rendimiento contra duración, y aunque
                el rendimiento sea comparable entre hermanas, mezclarlas dibujaba tres puntos por
                emisión sobre las mismas coordenadas. */}
            <CurvaSegmento especies={deLaMoneda} naturaleza={naturaleza} />
          </div>
        </>
      )}
    </>
  )
}

/**
 * La rama de renta variable de la pestaña de familia. Sin sub-barra mientras
 * `CLAVES_RENTA_VARIABLE` tenga una sola clase: una barra de una sola opción no deja nada por
 * elegir. Si vuelve una segunda clase, alcanza con que la lista tenga más de un elemento para que
 * la sub-barra reaparezca sola, sin más cambios acá.
 */
function RamaRentaVariable() {
  const [clase, setClase] = useState<string>(CLAVES_RENTA_VARIABLE[0])

  return (
    <>
      {CLAVES_RENTA_VARIABLE.length > 1 && (
        <SelectorSegmento segmentos={CLAVES_RENTA_VARIABLE} activo={clase} onCambio={setClase} />
      )}
      <RentaVariableDelMonitor clase={clase} />
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

/**
 * La rama de FCI de la pestaña de familia — F-057 (23/08/2026). Segundo nivel por tipo de renta
 * (`SelectorSegmento` con claves `fci_*`), un chip de moneda (sin chip de crédito: un fondo no
 * tiene emisor con crédito comparable), y la grilla de doce columnas.
 */
function RamaFci({
  segmentos,
  planilla,
}: {
  segmentos: { tipo_renta: string; cantidad: number; monedas: string[] }[]
  planilla: PlanillaFci | null
}) {
  const claves = useMemo(() => segmentos.map((s) => claveTipoRenta(s.tipo_renta)), [segmentos])
  const [claveActiva, setClaveActiva] = useState<string | null>(null)

  useEffect(() => {
    if (claveActiva !== null || claves.length === 0) return
    const [primera] = ordenarSegmentos(claves)
    if (primera) setClaveActiva(primera)
  }, [claveActiva, claves])

  useEffect(() => {
    if (claves.length === 0 || claveActiva === null || claves.includes(claveActiva)) return
    setClaveActiva(claves[0] ?? null)
  }, [claveActiva, claves])

  if (claves.length === 0 || claveActiva === null) {
    return (
      <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
        No hay fondos comunes en la planilla de hoy.
      </p>
    )
  }

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <SelectorSegmento segmentos={claves} activo={claveActiva} onCambio={setClaveActiva} />
        <Link to="/fci/analisis" style={{ fontSize: 12, color: 'var(--ac)', whiteSpace: 'nowrap' }}>
          Comparador, categorías y gestoras →
        </Link>
      </div>
      <FciDelTipoDeRenta key={claveActiva} tipoRenta={tipoRentaDeClave(claveActiva)} planilla={planilla} />
    </>
  )
}

function FciDelTipoDeRenta({
  tipoRenta,
  planilla,
}: {
  tipoRenta: string
  planilla: PlanillaFci | null
}) {
  const fci = useFondosFci(tipoRenta)
  const abrirFondo = useAbrirFondoFci()
  const [moneda, setMoneda] = useState<string | null>(null)

  const monedas = useMemo(
    () => contarPorMoneda((fci.data ?? []).map((f) => ({ moneda_cotizacion: f.moneda }))),
    [fci.data],
  )
  const activa = moneda ?? monedaInicial(monedas, MONEDA_PREFERIDA_POR_DEFECTO)
  const deLaMoneda = useMemo(
    () => (fci.data ?? []).filter((f) => (f.moneda ?? SIN_MONEDA_DECLARADA) === activa),
    [fci.data, activa],
  )

  if (fci.isPending) {
    return <p style={{ margin: '14px 0', color: 'var(--dim)', fontSize: 12.5 }}>consultando el segmento…</p>
  }

  if (fci.isError) {
    return (
      <EstadoVacio
        titulo="No se pudo traer este segmento."
        detalle={
          <button
            type="button"
            onClick={() => void fci.refetch()}
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
      <TablaFci
        fondos={deLaMoneda}
        etiqueta={nombreSegmento(claveTipoRenta(tipoRenta))}
        planilla={planilla}
        onAbrirFondo={abrirFondo}
      />
    </>
  )
}
