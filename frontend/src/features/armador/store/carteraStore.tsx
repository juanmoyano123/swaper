/**
 * El store del armador — F-016, extendido por F-018 (ponderación) y por F-017 (filtros de A7).
 *
 * Contexto de React + `useReducer`, sin dependencia nueva: lo que esta pantalla necesita recordar
 * —qué papeles están adentro, qué mes está abierto, cuánto pesa cada uno, qué filtros de la grilla
 * están activos— es chico y vive sólo mientras dura la sesión de armado, así que no justifica una
 * librería de estado global.
 */

import { createContext, type ReactNode, useContext, useMemo, useReducer } from 'react'

import { FILTROS_ARMADOR_VACIOS, type FiltrosArmador } from '../lib/filtros'

/** Una posición del armador. */
export interface PosicionArmador {
  ticker: string
  /** Ponderación pedida, en puntos porcentuales (16.5 = 16,5%). Al agregar un papel nuevo se
   *  asigna 100/(n+1) redondeado a un decimal; los pesos de los demás NO se tocan — por eso la
   *  suma puede no dar 100, y eso se muestra, no se corrige solo. */
  peso: number
  /** true para una línea de FCI: tiene peso pero no precio, y queda fuera de todo cálculo de
   *  renta o rendimiento (GWT-4 de F-018). Se agrega con `agregarFci`, no con `alternarPapel`. */
  esFci: boolean
}

interface EstadoArmador {
  /** En el orden en que se fueron agregando: es el orden en que se lee la cartera armada. */
  pos: PosicionArmador[]
  /** Índice 0–11 dentro de la ventana de la grilla, no el mes calendario. `null` sin mes abierto. */
  selMes: number | null
  /** Capital total a invertir, en dólares. 0 hasta que el asesor lo carga; con 0 no hay objetivo
   *  que repartir y `resolver` no calcula nominales (ver `lib/resolver.ts`). */
  montoTotal: number
  /** Filtros de la barra de F-017 (A7): filtran la oferta que se ve en la grilla, nunca `pos`. */
  filtros: FiltrosArmador
}

type AccionArmador =
  | { tipo: 'alternarPapel'; ticker: string }
  | { tipo: 'alternarMes'; indice: number }
  | { tipo: 'fijarPeso'; ticker: string; peso: number }
  | { tipo: 'fijarMontoTotal'; monto: number }
  | { tipo: 'equiponderar' }
  | { tipo: 'vaciar' }
  | { tipo: 'agregarFci'; nombre: string; peso: number }
  | { tipo: 'fijarFiltros'; filtros: FiltrosArmador }
  | { tipo: 'limpiarFiltros' }

const ESTADO_INICIAL: EstadoArmador = {
  pos: [],
  selMes: null,
  montoTotal: 0,
  filtros: FILTROS_ARMADOR_VACIOS,
}

/** 100/n a un decimal — el mismo redondeo que usan `alternarPapel` y `equiponderar`. */
function pesoIgualitario(n: number): number {
  return Math.round((100 / n) * 10) / 10
}

function reducer(estado: EstadoArmador, accion: AccionArmador): EstadoArmador {
  switch (accion.tipo) {
    case 'alternarPapel': {
      const yaEsta = estado.pos.some((p) => p.ticker === accion.ticker)
      if (yaEsta) {
        return { ...estado, pos: estado.pos.filter((p) => p.ticker !== accion.ticker) }
      }
      // `n` es la cantidad de posiciones ANTES de agregar; los pesos existentes no se recalculan.
      const pesoNuevo = pesoIgualitario(estado.pos.length + 1)
      return { ...estado, pos: [...estado.pos, { ticker: accion.ticker, peso: pesoNuevo, esFci: false }] }
    }
    case 'alternarMes':
      // Clic sobre el mes ya activo lo cierra: es la misma mecánica de des-selección que
      // `alternarPapel`, aplicada al mes en vez de al papel.
      return { ...estado, selMes: estado.selMes === accion.indice ? null : accion.indice }
    case 'fijarPeso':
      return {
        ...estado,
        pos: estado.pos.map((p) => (p.ticker === accion.ticker ? { ...p, peso: accion.peso } : p)),
      }
    case 'fijarMontoTotal':
      return { ...estado, montoTotal: accion.monto }
    case 'equiponderar': {
      if (estado.pos.length === 0) return estado
      const pesoParejo = pesoIgualitario(estado.pos.length)
      return { ...estado, pos: estado.pos.map((p) => ({ ...p, peso: pesoParejo })) }
    }
    case 'vaciar':
      return { ...estado, pos: [] }
    case 'agregarFci':
      return { ...estado, pos: [...estado.pos, { ticker: accion.nombre, peso: accion.peso, esFci: true }] }
    // Los filtros filtran la oferta, no la cartera: estas dos acciones nunca tocan `pos`,
    // `selMes` ni `montoTotal` — un papel ya seleccionado sigue en la cartera aunque un filtro
    // le tape el renglón en la grilla.
    case 'fijarFiltros':
      return { ...estado, filtros: accion.filtros }
    case 'limpiarFiltros':
      return { ...estado, filtros: FILTROS_ARMADOR_VACIOS }
  }
}

interface AccionesArmador {
  /** Agrega el papel si no está en la cartera; lo saca si ya estaba. */
  alternarPapel: (ticker: string) => void
  /** Abre el mes si no era el activo; lo cierra si ya lo era. */
  alternarMes: (indice: number) => void
  /** Pisa el peso pedido de esa posición; no toca las demás. */
  fijarPeso: (ticker: string, peso: number) => void
  fijarMontoTotal: (monto: number) => void
  /** Pone `100 / n` a todas las posiciones, a un decimal. */
  equiponderar: () => void
  vaciar: () => void
  /** Agrega una línea de FCI: tiene peso pero no precio (GWT-4 de F-018). */
  agregarFci: (nombre: string, peso: number) => void
  /** Pisa el objeto de filtros entero: el llamador arma el objeto (mismo patrón `onCambio` del
   *  monitor). */
  fijarFiltros: (filtros: FiltrosArmador) => void
  /** Vuelve todos los filtros a `FILTROS_ARMADOR_VACIOS` de una sola vez (GWT-3). */
  limpiarFiltros: () => void
}

const EstadoContext = createContext<EstadoArmador | null>(null)
const AccionesContext = createContext<AccionesArmador | null>(null)

export function ArmadorProvider({ children }: { children: ReactNode }) {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL)

  // Memoizado aparte del estado: las identidades de las acciones no cambian nunca, así que un
  // componente que sólo lee acciones (por ejemplo, un botón "agregar") no vuelve a renderizar
  // cuando cambia `pos`, `selMes` o `montoTotal`.
  const acciones = useMemo<AccionesArmador>(
    () => ({
      alternarPapel: (ticker: string) => dispatch({ tipo: 'alternarPapel', ticker }),
      alternarMes: (indice: number) => dispatch({ tipo: 'alternarMes', indice }),
      fijarPeso: (ticker: string, peso: number) => dispatch({ tipo: 'fijarPeso', ticker, peso }),
      fijarMontoTotal: (monto: number) => dispatch({ tipo: 'fijarMontoTotal', monto }),
      equiponderar: () => dispatch({ tipo: 'equiponderar' }),
      vaciar: () => dispatch({ tipo: 'vaciar' }),
      agregarFci: (nombre: string, peso: number) => dispatch({ tipo: 'agregarFci', nombre, peso }),
      fijarFiltros: (filtros: FiltrosArmador) => dispatch({ tipo: 'fijarFiltros', filtros }),
      limpiarFiltros: () => dispatch({ tipo: 'limpiarFiltros' }),
    }),
    [],
  )

  return (
    <EstadoContext.Provider value={estado}>
      <AccionesContext.Provider value={acciones}>{children}</AccionesContext.Provider>
    </EstadoContext.Provider>
  )
}

export function useArmador(): EstadoArmador {
  const estado = useContext(EstadoContext)
  if (estado === null) throw new Error('useArmador se tiene que usar dentro de <ArmadorProvider>')
  return estado
}

export function useArmadorAcciones(): AccionesArmador {
  const acciones = useContext(AccionesContext)
  if (acciones === null) {
    throw new Error('useArmadorAcciones se tiene que usar dentro de <ArmadorProvider>')
  }
  return acciones
}
