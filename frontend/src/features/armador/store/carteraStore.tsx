/**
 * El store del armador — F-016, heredado por F-017 y F-018.
 *
 * Contexto de React + `useReducer`, sin dependencia nueva: lo que esta pantalla necesita recordar
 * —qué papeles están adentro, qué mes está abierto— es chico y vive sólo mientras dura la sesión de
 * armado, así que no justifica una librería de estado global.
 *
 * **F-017 y F-018 extienden esta misma forma, y por eso el plan la serializa así:** F-017 agrega
 * los filtros de segmento/rendimiento/duración de A7 a `EstadoArmador`, y F-018 agrega peso pedido
 * y nominales a `PosicionArmador`. Los dos amplían este shape en vez de armar un store paralelo —
 * los comentarios de abajo marcan dónde va cada cosa.
 */

import { createContext, type ReactNode, useContext, useMemo, useReducer } from 'react'

/** Una posición del armador. F-018 agrega acá peso pedido y nominales — no se agrega todavía. */
export interface PosicionArmador {
  ticker: string
}

interface EstadoArmador {
  /** En el orden en que se fueron agregando: es el orden en que se lee la cartera armada. */
  pos: PosicionArmador[]
  /** Índice 0–11 dentro de la ventana de la grilla, no el mes calendario. `null` sin mes abierto. */
  selMes: number | null
  // F-017 agrega acá los filtros de A7 (segmento, rendimiento mín/máx, duración máxima). No se
  // agrega todavía.
}

type AccionArmador =
  | { tipo: 'alternarPapel'; ticker: string }
  | { tipo: 'alternarMes'; indice: number }

const ESTADO_INICIAL: EstadoArmador = { pos: [], selMes: null }

function reducer(estado: EstadoArmador, accion: AccionArmador): EstadoArmador {
  switch (accion.tipo) {
    case 'alternarPapel': {
      const yaEsta = estado.pos.some((p) => p.ticker === accion.ticker)
      return {
        ...estado,
        pos: yaEsta
          ? estado.pos.filter((p) => p.ticker !== accion.ticker)
          : [...estado.pos, { ticker: accion.ticker }],
      }
    }
    case 'alternarMes':
      // Clic sobre el mes ya activo lo cierra: es la misma mecánica de des-selección que
      // `alternarPapel`, aplicada al mes en vez de al papel.
      return { ...estado, selMes: estado.selMes === accion.indice ? null : accion.indice }
  }
}

interface AccionesArmador {
  /** Agrega el papel si no está en la cartera; lo saca si ya estaba. */
  alternarPapel: (ticker: string) => void
  /** Abre el mes si no era el activo; lo cierra si ya lo era. */
  alternarMes: (indice: number) => void
}

const EstadoContext = createContext<EstadoArmador | null>(null)
const AccionesContext = createContext<AccionesArmador | null>(null)

export function ArmadorProvider({ children }: { children: ReactNode }) {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL)

  // Memoizado aparte del estado: las identidades de `alternarPapel`/`alternarMes` no cambian
  // nunca, así que un componente que sólo lee acciones (por ejemplo, un botón "agregar") no vuelve
  // a renderizar cuando cambia `pos` o `selMes`.
  const acciones = useMemo<AccionesArmador>(
    () => ({
      alternarPapel: (ticker: string) => dispatch({ tipo: 'alternarPapel', ticker }),
      alternarMes: (indice: number) => dispatch({ tipo: 'alternarMes', indice }),
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
