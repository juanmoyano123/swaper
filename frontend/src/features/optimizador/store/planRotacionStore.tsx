/**
 * El store del plan de rotaciones — F-036.
 *
 * Mismo patrón que `features/armador/store/carteraStore.tsx`: Context + `useReducer`, sin
 * dependencia nueva, con el estado y las acciones en dos contexts separados para que un componente
 * que sólo dispara acciones (un botón "Aceptar") no vuelva a renderizar cuando cambia el plan.
 *
 * **El estado guarda decisiones, nunca carteras derivadas.** `aceptadas` es la pila de `Candidata`
 * en el orden en que el asesor las fue aceptando; `descartadas` son claves de candidatas que no
 * vuelven a proponerse en la sesión (GWT-4). Todo lo demás —la cartera resultante, qué rotaciones
 * quedan excluidas del próximo recálculo— se deriva acá con la lib pura de `lib/rotaciones/plan.ts`,
 * así que **deshacer es sacar el último elemento de la pila** (GWT-3): no hay un snapshot de "estado
 * anterior" que guardar ni que pueda desincronizarse, todo vuelve exacto porque se recalcula desde
 * las posiciones originales.
 *
 * "Sesión" = la vida de este provider. Se monta en `CarteraConfirmada.tsx` con
 * `key={firmaDePesos(posicionesConPeso)}`: confirmar otra cartera desmonta el provider viejo y
 * arranca uno nuevo, vacío.
 */

import { createContext, type ReactNode, useContext, useMemo, useReducer } from 'react'

import type { PosicionConPeso } from '../../../lib/cartera/riesgo'
import { claveCandidata } from '../../../lib/rotaciones/ejes'
import type { Candidata } from '../../../lib/rotaciones/esquemaRotaciones'
import { clavesInversas, posicionesAcumuladas } from '../../../lib/rotaciones/plan'

interface EstadoPlan {
  /** Pila en orden de aceptación. Se guarda la `Candidata` entera —no sólo la clave— porque el
   *  panel de rotaciones aceptadas necesita su delta, su `riesgo_nota` y su `costo` (F-035) para
   *  re-declararse, y F-037 va a necesitar el mismo detalle para el costo acumulado. */
  aceptadas: Candidata[]
  /** Claves (`claveCandidata`) descartadas en esta sesión — GWT-4. */
  descartadas: string[]
}

type AccionPlan =
  | { tipo: 'aceptar'; candidata: Candidata }
  | { tipo: 'deshacerUltima' }
  | { tipo: 'descartar'; clave: string }

const ESTADO_INICIAL: EstadoPlan = { aceptadas: [], descartadas: [] }

function reducer(estado: EstadoPlan, accion: AccionPlan): EstadoPlan {
  switch (accion.tipo) {
    case 'aceptar': {
      const clave = claveCandidata(accion.candidata)
      if (estado.aceptadas.some((c) => claveCandidata(c) === clave)) return estado
      return { ...estado, aceptadas: [...estado.aceptadas, accion.candidata] }
    }
    // LIFO puro: sólo la última aceptada se deshace (ver docstring del módulo). Con la pila vacía,
    // no-op.
    case 'deshacerUltima':
      if (estado.aceptadas.length === 0) return estado
      return { ...estado, aceptadas: estado.aceptadas.slice(0, -1) }
    case 'descartar':
      if (estado.descartadas.includes(accion.clave)) return estado
      return { ...estado, descartadas: [...estado.descartadas, accion.clave] }
  }
}

export interface PlanRotacion extends EstadoPlan {
  posicionesOriginales: PosicionConPeso[]
  /** La cartera resultante de aplicar, en orden, cada rotación aceptada. */
  posicionesAcumuladas: PosicionConPeso[]
  /** `descartadas` ∪ las inversas de `aceptadas`: lo que los hooks de F-033/F-034 excluyen del
   *  próximo recálculo — una rotación descartada no vuelve, y la inversa de una aceptada es
   *  "deshacer" disfrazado de mejora, no una propuesta nueva. */
  clavesExcluidas: ReadonlySet<string>
}

interface AccionesPlan {
  /** No-op si la clave ya está aceptada. */
  aceptar: (candidata: Candidata) => void
  /** Saca la última aceptada. No-op con la pila vacía. */
  deshacerUltima: () => void
  /** No-op si la clave ya estaba descartada. Sobrevive a aceptar/deshacer. */
  descartar: (clave: string) => void
}

const EstadoContext = createContext<PlanRotacion | null>(null)
const AccionesContext = createContext<AccionesPlan | null>(null)

export function PlanRotacionProvider({
  posiciones,
  children,
}: {
  posiciones: PosicionConPeso[]
  children: ReactNode
}) {
  const [estado, dispatch] = useReducer(reducer, ESTADO_INICIAL)

  const plan = useMemo<PlanRotacion>(() => {
    const clavesExcluidas = new Set([...estado.descartadas, ...clavesInversas(estado.aceptadas)])
    return {
      ...estado,
      posicionesOriginales: posiciones,
      posicionesAcumuladas: posicionesAcumuladas(posiciones, estado.aceptadas),
      clavesExcluidas,
    }
  }, [estado, posiciones])

  const acciones = useMemo<AccionesPlan>(
    () => ({
      aceptar: (candidata: Candidata) => dispatch({ tipo: 'aceptar', candidata }),
      deshacerUltima: () => dispatch({ tipo: 'deshacerUltima' }),
      descartar: (clave: string) => dispatch({ tipo: 'descartar', clave }),
    }),
    [],
  )

  return (
    <EstadoContext.Provider value={plan}>
      <AccionesContext.Provider value={acciones}>{children}</AccionesContext.Provider>
    </EstadoContext.Provider>
  )
}

export function usePlanRotacion(): PlanRotacion {
  const plan = useContext(EstadoContext)
  if (plan === null) throw new Error('usePlanRotacion se tiene que usar dentro de <PlanRotacionProvider>')
  return plan
}

export function usePlanRotacionAcciones(): AccionesPlan {
  const acciones = useContext(AccionesContext)
  if (acciones === null) {
    throw new Error('usePlanRotacionAcciones se tiene que usar dentro de <PlanRotacionProvider>')
  }
  return acciones
}
