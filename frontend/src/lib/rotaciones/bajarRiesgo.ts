/**
 * F-033 — modo "mantener la TIR y bajar el riesgo": para el eje que el asesor elige, propone
 * rotaciones candidatas (F-032) que mejoran ese eje ESTRICTAMENTE, no empeoran ninguno de los
 * otros cinco (no-empeoramiento, no compensación — regla 7 del dominio) y mantienen el rendimiento
 * dentro de la banda de ±0,5pp que ya usa el motor para ordenar destinos parejos
 * (`backend/app/rotaciones/constantes.py:23`, `BANDA_RENDIMIENTO_PP`).
 *
 * Lib pura, sin red: reusa `vectorDeRiesgo()` de F-031 en vez de reimplementar su aritmética (así
 * una futura F-03X que cambie cómo se pondera un eje no tiene una segunda fórmula que actualizar
 * acá). Se evalúa en dos etapas porque concentración es la única de las seis que necesita un POST:
 *
 * - **Etapa local** (`evaluarEtapaLocal`): duración, legislación, liquidez, crédito y la banda de
 *   rendimiento se resuelven sin red. Para duración/legislación/liquidez se llama a
 *   `vectorDeRiesgo()` con la cartera simulada y `concentracion: null` — el eje concentración de
 *   esa llamada nunca se lee, se vuelve a calcular bien en la etapa 2.
 * - **Etapa concentración** (`evaluarEtapaConcentracion`): sólo corre sobre lo que sobrevivió a la
 *   etapa local, con la concentración simulada real ya pedida por el llamador (el hook la resuelve
 *   con `useQueries`, esta lib no sabe de TanStack Query).
 *
 * `evaluarBajarRiesgo()` encadena las dos etapas para el caso en que ya se tienen todas las
 * concentraciones simuladas — es lo que usan los tests y lo que el hook llama una vez que sus
 * queries resolvieron.
 */

import type { Concentracion } from '../cartera/esquemaConcentracion'
import { vectorDeRiesgo, type EjeDeRiesgo, type EspecieRiesgo, type IdDeEje, type PosicionConPeso } from '../cartera/riesgo'

import type { Candidata } from './esquemaRotaciones'

export const EJE_PRIMARIO_DEFAULT: IdDeEje = 'duracion'

// Misma banda que usa el motor para ordenar destinos parejos — ver
// `backend/app/rotaciones/constantes.py:23` (`BANDA_RENDIMIENTO_PP = 0.5`).
export const BANDA_RENDIMIENTO_PP = 0.5

/** Crédito y moneda son compositivos (`valor: null` siempre en `riesgo.ts`): no tienen una
 *  métrica escalar sobre la que exigir una mejora estricta, así que no son elegibles como eje
 *  primario de este modo (regla 7 del dominio: no se inventa un orden para lo que no lo tiene). */
export const EJES_NO_MEDIBLES_COMO_PRIMARIO: ReadonlySet<IdDeEje> = new Set(['credito', 'moneda'])

export const TODOS_LOS_EJES: IdDeEje[] = ['duracion', 'credito', 'legislacion', 'liquidez', 'concentracion', 'moneda']

export const NOMBRES_EJE: Record<IdDeEje, string> = {
  duracion: 'Duración',
  credito: 'Crédito',
  legislacion: 'Legislación',
  liquidez: 'Liquidez',
  concentracion: 'Concentración',
  moneda: 'Moneda',
}

export type MotivoDescarte = 'empeora' | 'sin_dato' | 'sin_criterio_medible' | 'fuera_de_banda'

export interface DescarteCandidata {
  candidata: Candidata
  eje: IdDeEje
  motivo: MotivoDescarte
}

export interface PropuestaBajarRiesgo {
  candidata: Candidata
  /** Valor del eje primario, cartera actual vs. simulada, en la unidad de `EjeDeRiesgo.unidad`. */
  valorActual: number | null
  valorSimulado: number | null
  unidad: EjeDeRiesgo['unidad']
}

export interface ResultadoBajarRiesgo {
  hayPropuesta: boolean
  /** `true` cuando `ejePrimario` es crédito o moneda: no se evaluó nada, se declara por qué. */
  noMedible: boolean
  motivo: string | null
  propuestas: PropuestaBajarRiesgo[]
  descartes: DescarteCandidata[]
}

export function resultadoNoMedible(ejePrimario: IdDeEje): ResultadoBajarRiesgo {
  return {
    hayPropuesta: false,
    noMedible: true,
    motivo:
      `El eje "${NOMBRES_EJE[ejePrimario]}" es compositivo (regla 7 del dominio: no se ordena en ` +
      'un score) y no tiene una métrica escalar propia — no se puede usar como eje primario de ' +
      'este modo. Elegí otro eje.',
    propuestas: [],
    descartes: [],
  }
}

/** Identifica una candidata por su par de tickers, para cachear/mapear su concentración simulada. */
export function claveCandidata(candidata: Candidata): string {
  return `${candidata.origen.ticker}->${candidata.destino.ticker}`
}

/** La cartera con el peso del origen movido al destino (sumado si el destino ya estaba). */
export function carteraSimuladaDeCandidata(
  posicionesActuales: PosicionConPeso[],
  candidata: Candidata,
): PosicionConPeso[] {
  const pesoOrigen = posicionesActuales
    .filter((p) => p.ticker === candidata.origen.ticker)
    .reduce((acumulado, p) => acumulado + p.peso, 0)
  const sinOrigen = posicionesActuales.filter((p) => p.ticker !== candidata.origen.ticker)
  return sumarPorTicker([...sinOrigen, { ticker: candidata.destino.ticker, peso: pesoOrigen }])
}

function sumarPorTicker(posiciones: PosicionConPeso[]): PosicionConPeso[] {
  const pesos = new Map<string, number>()
  const orden: string[] = []
  for (const p of posiciones) {
    if (!pesos.has(p.ticker)) orden.push(p.ticker)
    pesos.set(p.ticker, (pesos.get(p.ticker) ?? 0) + p.peso)
  }
  return orden.map((ticker) => ({ ticker, peso: pesos.get(ticker)! }))
}

function indexarPorId(ejes: EjeDeRiesgo[]): Record<IdDeEje, EjeDeRiesgo> {
  const mapa = {} as Record<IdDeEje, EjeDeRiesgo>
  for (const eje of ejes) mapa[eje.id] = eje
  return mapa
}

type EstadoEje = 'mejora' | 'no_empeora' | 'empeora' | 'sin_dato'

/**
 * Duración: menos años es mejor. Legislación: más peso bajo ley extranjera es mejor — la Ley N.Y.
 * reduce el riesgo jurisdiccional frente a la Ley Argentina (mismo sentido que `mejora_ley` en
 * `backend/app/rotaciones/motor.py`: pasar de ley local a extranjera es la mejora, no al revés).
 * Liquidez: más percentil es mejor. Concentración: menos peso máximo por crédito es mejor.
 */
function estadoPorValor(eje: 'duracion' | 'legislacion' | 'liquidez' | 'concentracion', actual: number, simulado: number): EstadoEje {
  const mejorSiMenor = eje === 'duracion' || eje === 'concentracion'
  if (simulado === actual) return 'no_empeora'
  const mejora = mejorSiMenor ? simulado < actual : simulado > actual
  return mejora ? 'mejora' : 'empeora'
}

function estadoLocal(
  eje: 'duracion' | 'legislacion' | 'liquidez',
  candidata: Candidata,
  ejeActual: EjeDeRiesgo,
  ejeSimulado: EjeDeRiesgo,
): EstadoEje {
  if (eje === 'legislacion' && (candidata.origen.ley === null || candidata.destino.ley === null)) return 'sin_dato'
  if (eje === 'liquidez' && candidata.destino.volumen_usd === null) return 'sin_dato'
  if (ejeActual.valor === null || ejeSimulado.valor === null) return 'sin_dato'
  return estadoPorValor(eje, ejeActual.valor, ejeSimulado.valor)
}

const EJES_LOCALES: readonly ('duracion' | 'legislacion' | 'liquidez')[] = ['duracion', 'legislacion', 'liquidez']

function evaluarCandidataLocal(
  candidata: Candidata,
  ejePrimario: IdDeEje,
  vectorActualPorId: Record<IdDeEje, EjeDeRiesgo>,
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
): DescarteCandidata | null {
  if (Math.abs(candidata.delta.rendimiento_pp) > BANDA_RENDIMIENTO_PP) {
    return { candidata, eje: ejePrimario, motivo: 'fuera_de_banda' }
  }

  const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
  // `concentracion: null` a propósito: el eje concentración de este vector no se lee acá, se
  // recalcula con la concentración simulada real en `evaluarEtapaConcentracion`.
  const vectorSimuladoPorId = indexarPorId(vectorDeRiesgo(posicionesSimuladas, porTicker, null))

  for (const eje of EJES_LOCALES) {
    const estado = estadoLocal(eje, candidata, vectorActualPorId[eje], vectorSimuladoPorId[eje])
    const esPrimario = eje === ejePrimario
    if (esPrimario) {
      if (estado !== 'mejora') return { candidata, eje, motivo: estado === 'sin_dato' ? 'sin_dato' : 'empeora' }
    } else if (estado === 'sin_dato') {
      return { candidata, eje, motivo: 'sin_dato' }
    } else if (estado === 'empeora') {
      return { candidata, eje, motivo: 'empeora' }
    }
  }

  // Crédito nunca es primario acá (bloqueado antes de llegar a esta función): sólo se mide como
  // no-empeoramiento, vía `mismo_emisor` — regla 7, la calificación no se ordena.
  if (!candidata.flags.mismo_emisor) {
    return { candidata, eje: 'credito', motivo: 'sin_criterio_medible' }
  }

  // Moneda: siempre "no empeora" por construcción (rotaciones intra-segmento no cambian la
  // naturaleza de tasa) — no genera descarte nunca, se declara en la UI, no acá (regla 8).
  // Concentración: se difiere siempre a la etapa 2, sea o no el eje primario.
  return null
}

export interface ResultadoEtapaLocal {
  sobrevivientes: Candidata[]
  descartes: DescarteCandidata[]
}

export function evaluarEtapaLocal(
  candidatas: Candidata[],
  ejePrimario: IdDeEje,
  vectorActual: EjeDeRiesgo[],
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
): ResultadoEtapaLocal {
  const vectorActualPorId = indexarPorId(vectorActual)
  const sobrevivientes: Candidata[] = []
  const descartes: DescarteCandidata[] = []
  for (const candidata of candidatas) {
    const descarte = evaluarCandidataLocal(candidata, ejePrimario, vectorActualPorId, posicionesActuales, porTicker)
    if (descarte) descartes.push(descarte)
    else sobrevivientes.push(candidata)
  }
  return { sobrevivientes, descartes }
}

export interface ResultadoEtapaConcentracion {
  sobrevivientes: Candidata[]
  descartes: DescarteCandidata[]
}

export function evaluarEtapaConcentracion(
  candidatas: Candidata[],
  ejePrimario: IdDeEje,
  vectorActual: EjeDeRiesgo[],
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracionesSimuladas: ReadonlyMap<string, Concentracion | null>,
): ResultadoEtapaConcentracion {
  const actualValor = indexarPorId(vectorActual).concentracion.valor
  const sobrevivientes: Candidata[] = []
  const descartes: DescarteCandidata[] = []

  for (const candidata of candidatas) {
    const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
    const concentracionSimulada = concentracionesSimuladas.get(claveCandidata(candidata)) ?? null
    const simuladoValor = indexarPorId(vectorDeRiesgo(posicionesSimuladas, porTicker, concentracionSimulada)).concentracion.valor

    if (actualValor === null || simuladoValor === null) {
      descartes.push({ candidata, eje: 'concentracion', motivo: 'sin_dato' })
      continue
    }

    const estado = estadoPorValor('concentracion', actualValor, simuladoValor)
    const esPrimario = ejePrimario === 'concentracion'
    if (esPrimario ? estado === 'mejora' : estado !== 'empeora') {
      sobrevivientes.push(candidata)
    } else {
      descartes.push({ candidata, eje: 'concentracion', motivo: 'empeora' })
    }
  }

  return { sobrevivientes, descartes }
}

function valorEjePrimario(
  candidata: Candidata,
  ejePrimario: IdDeEje,
  vectorActualPorId: Record<IdDeEje, EjeDeRiesgo>,
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracionSimulada: Concentracion | null,
): { valorActual: number | null; valorSimulado: number | null; unidad: EjeDeRiesgo['unidad'] } {
  const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
  // Sólo se pasa la concentración simulada real cuando el eje primario ES concentración: para los
  // otros tres ejes medibles, el eje concentración de este vector no se usa.
  const concentracionParaVector = ejePrimario === 'concentracion' ? concentracionSimulada : null
  const vectorSimuladoPorId = indexarPorId(vectorDeRiesgo(posicionesSimuladas, porTicker, concentracionParaVector))
  const actual = vectorActualPorId[ejePrimario]
  const simulado = vectorSimuladoPorId[ejePrimario]
  return { valorActual: actual.valor, valorSimulado: simulado.valor, unidad: actual.unidad }
}

/**
 * Encadena las dos etapas para el caso en que ya se tienen todas las concentraciones simuladas
 * necesarias (el hook las resuelve con `useQueries` antes de llamar acá; los tests las arman a
 * mano). Vuelve a correr la etapa local sobre `candidatas` completo: es barato (candidatas de a
 * lo sumo `TOP_N` por origen) y evita que el llamador tenga que separar "sobrevivientes locales"
 * de "candidatas completas" para dos funciones distintas.
 */
export function evaluarBajarRiesgo(
  candidatas: Candidata[],
  ejePrimario: IdDeEje,
  vectorActual: EjeDeRiesgo[],
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracionesSimuladas: ReadonlyMap<string, Concentracion | null>,
): ResultadoBajarRiesgo {
  if (EJES_NO_MEDIBLES_COMO_PRIMARIO.has(ejePrimario)) return resultadoNoMedible(ejePrimario)

  const vectorActualPorId = indexarPorId(vectorActual)
  const etapaLocal = evaluarEtapaLocal(candidatas, ejePrimario, vectorActual, posicionesActuales, porTicker)
  const etapaConcentracion = evaluarEtapaConcentracion(
    etapaLocal.sobrevivientes,
    ejePrimario,
    vectorActual,
    posicionesActuales,
    porTicker,
    concentracionesSimuladas,
  )

  const propuestas: PropuestaBajarRiesgo[] = etapaConcentracion.sobrevivientes.map((candidata) => {
    const concentracionSimulada = concentracionesSimuladas.get(claveCandidata(candidata)) ?? null
    const valores = valorEjePrimario(candidata, ejePrimario, vectorActualPorId, posicionesActuales, porTicker, concentracionSimulada)
    return { candidata, ...valores }
  })

  return {
    hayPropuesta: propuestas.length > 0,
    noMedible: false,
    motivo: null,
    propuestas,
    descartes: [...etapaLocal.descartes, ...etapaConcentracion.descartes],
  }
}
