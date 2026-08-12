/**
 * F-034 — modo "subir la TIR declarando la contrapartida": de las rotaciones candidatas de F-032,
 * las que el motor marcó como mejora de rendimiento (`tipo: 'mejora_rendimiento'`, d_rend ≥ 0,5pp),
 * cada una acompañada por **todos los ejes que empeoran y en cuánto**.
 *
 * Es la regla 8 del dominio hecha código: *nunca se propone una mejora de TIR sin nombrar qué
 * riesgo se asume a cambio*. Por eso la unidad de salida no es "la propuesta y opcionalmente sus
 * deltas", sino la propuesta **con los seis ejes evaluados siempre** — no hay dónde poner una fila
 * sin contrapartida aunque alguien quisiera. Y por eso, cuando un delta no se puede calcular, la
 * propuesta no se muestra: mostrarla sería afirmar que no hay contrapartida sobre ese eje, que es
 * distinto de no saberla.
 *
 * **Complementa a F-033, no la duplica.** Los dos modos parten del mismo conjunto de candidatas y
 * lo particionan sin solaparse: F-033 se queda con las que mueven el rendimiento dentro de ±0,5pp
 * (mantener la TIR), F-034 con las que lo suben más que eso. Pero deciden distinto — F-033
 * **filtra** por no-empeoramiento, F-034 **declara** lo que empeora. Acá nada se descarta por
 * empeorar un eje: empeorar es, precisamente, lo que hay para mostrar.
 *
 * El vocabulario común (signos por eje, cartera simulada, motivos de descarte) vive en `ejes.ts`.
 * Como en F-033, la evaluación va en dos etapas porque concentración es el único eje que necesita
 * un POST; esta lib no sabe de TanStack Query y recibe las concentraciones ya resueltas.
 */

import type { Concentracion } from '../cartera/esquemaConcentracion'
import { vectorDeRiesgo, type CoberturaDeEje, type EjeDeRiesgo, type EspecieRiesgo, type IdDeEje, type PosicionConPeso } from '../cartera/riesgo'

import {
  carteraSimuladaDeCandidata,
  claveCandidata,
  estadoPorValor,
  indexarPorId,
  TODOS_LOS_EJES,
  type DescarteCandidata,
  type EjeMedible,
} from './ejes'
import type { Candidata } from './esquemaRotaciones'

/** Los cuatro ejes con métrica escalar: los únicos sobre los que existe un delta que mostrar. */
const EJES_MEDIBLES: readonly EjeMedible[] = ['duracion', 'legislacion', 'liquidez', 'concentracion']

/** Los tres medibles que se resuelven sin red (concentración necesita el POST de la etapa 2). */
const MEDIBLES_LOCALES: readonly ('duracion' | 'legislacion' | 'liquidez')[] = ['duracion', 'legislacion', 'liquidez']

export interface CoberturaContrapartida {
  /** Porcentaje del peso con dato en la cartera actual; `null` si no hay peso que medir. */
  pctActual: number | null
  pctSimulada: number | null
  /** `true` si alguna de las dos mediciones no cubre la cartera entera. */
  parcial: boolean
}

export interface EvaluacionEje {
  eje: IdDeEje
  /**
   * Los medibles nunca llegan acá en `sin_dato`: un delta que no se pudo calcular descarta la
   * propuesta entera antes. Crédito y moneda son siempre `cualitativo` — son compositivos
   * (`valor: null` en `riesgo.ts`) y forzarles un número sería inventar un orden que no existe
   * (regla 7).
   */
  estado: 'mejora' | 'no_empeora' | 'empeora' | 'cualitativo'
  valorActual: number | null
  valorSimulado: number | null
  unidad: EjeDeRiesgo['unidad']
  cobertura: CoberturaContrapartida | null
  /** Declaración literal del cambio, cuando hay uno que nombrar: leyes, emisor, naturaleza. */
  nota: string | null
}

export interface PropuestaSubirTir {
  candidata: Candidata
  /** Siempre los seis, en el orden fijo de `ORDEN_EJES` — regla 7: viaja el vector entero. */
  ejes: EvaluacionEje[]
  /**
   * `true` sólo si ningún eje medible empeora **y** no cambia el emisor. Un cambio de emisor es
   * contrapartida aunque ningún número se mueva: el riesgo de crédito no tiene métrica escalar,
   * así que "no empeoró" no se puede afirmar. GWT-3: la UI declara esto explícito en vez de dejar
   * la columna vacía.
   */
  ningunEjeEmpeora: boolean
}

export interface ResultadoSubirTir {
  hayPropuesta: boolean
  /** En el orden que las mandó el motor (banda de rendimiento, frecuencia de cupón, rendimiento). */
  propuestas: PropuestaSubirTir[]
  descartes: DescarteCandidata[]
  /** Cuántas candidatas de mejora de rendimiento traía la respuesta: mostradas + descartadas. */
  evaluadas: number
}

/** Qué porcentaje del peso llegó con dato, para declarar la cobertura al lado del delta (GWT-4). */
function pctCobertura(cobertura: CoberturaDeEje): number | null {
  if (cobertura.pesoTotal <= 0) return null
  return Math.round((cobertura.pesoConDato / cobertura.pesoTotal) * 100)
}

function coberturaDe(actual: CoberturaDeEje, simulada: CoberturaDeEje): CoberturaContrapartida {
  const pctActual = pctCobertura(actual)
  const pctSimulada = pctCobertura(simulada)
  return {
    pctActual,
    pctSimulada,
    parcial: (pctActual !== null && pctActual < 100) || (pctSimulada !== null && pctSimulada < 100),
  }
}

/**
 * El primer eje medible local cuyo delta no se puede calcular para esta candidata, o `null` si
 * están todos.
 *
 * El criterio distingue dos faltantes que se parecen y no son lo mismo: **sin dato en las puntas**
 * de la rotación el delta no es atribuible a la rotación y la propuesta no se puede mostrar (GWT-2);
 * **sin dato en el resto de la cartera** el delta agregado sí existe, y lo que corresponde es
 * declarar la cobertura parcial junto al número (GWT-4). Es más estricto que F-033 en duración a
 * propósito: acá la fila ES el delta, y un promedio simulado que excluyera en silencio la duración
 * del destino afirmaría un cambio que no se midió (regla 1).
 */
function primerEjeSinDelta(
  candidata: Candidata,
  actual: Record<IdDeEje, EjeDeRiesgo>,
  simulado: Record<IdDeEje, EjeDeRiesgo>,
): IdDeEje | null {
  if (candidata.delta.duracion === null) return 'duracion'
  if (candidata.origen.ley === null || candidata.destino.ley === null) return 'legislacion'
  if (candidata.destino.volumen_usd === null) return 'liquidez'
  for (const eje of MEDIBLES_LOCALES) {
    if (actual[eje].valor === null || simulado[eje].valor === null) return eje
  }
  return null
}

/** La contrapartida de crédito, en palabras: no tiene métrica escalar que restar (regla 7). */
function notaCredito(candidata: Candidata): string {
  if (candidata.flags.mismo_emisor) return 'mismo emisor: el riesgo de crédito no cambia'
  const califica = (valor: string | null) => valor ?? 'sin calificación'
  return (
    `cambia de emisor: ${candidata.origen.emisor} → ${candidata.destino.emisor} ` +
    `(calificación ${califica(candidata.origen.calificacion)} → ${califica(candidata.destino.calificacion)})`
  )
}

function evaluarEje(
  eje: IdDeEje,
  candidata: Candidata,
  actual: Record<IdDeEje, EjeDeRiesgo>,
  simulado: Record<IdDeEje, EjeDeRiesgo>,
): EvaluacionEje {
  if (eje === 'credito' || eje === 'moneda') {
    return {
      eje,
      estado: 'cualitativo',
      valorActual: null,
      valorSimulado: null,
      unidad: null,
      cobertura: null,
      nota:
        eje === 'credito'
          ? notaCredito(candidata)
          : // Una rotación es siempre intra-segmento (`motor.py`), así que la naturaleza de la tasa
            // no cambia: el eje no puede empeorar por construcción, y se declara sin calcularlo
            // (regla 2 — dos naturalezas distintas ni siquiera serían comparables).
            'mismo segmento: la naturaleza de la tasa no cambia',
    }
  }

  const medible = eje as EjeMedible
  // Los non-null son seguros: `primerEjeSinDelta` y la etapa de concentración ya descartaron toda
  // candidata a la que le faltara alguno de estos valores.
  const estado = estadoPorValor(medible, actual[eje].valor!, simulado[eje].valor!)
  const cambiaLaLey = eje === 'legislacion' && candidata.origen.ley !== candidata.destino.ley

  return {
    eje,
    estado,
    valorActual: actual[eje].valor,
    valorSimulado: simulado[eje].valor,
    unidad: actual[eje].unidad,
    cobertura: coberturaDe(actual[eje].cobertura, simulado[eje].cobertura),
    // Las leyes se muestran como las declara la fuente, sin normalizar ni traducir: una ley que el
    // vector no reconoce como local ni extranjera queda fuera del número, pero acá se nombra
    // igual (regla 11).
    nota: cambiaLaLey ? `${candidata.origen.ley} → ${candidata.destino.ley}` : null,
  }
}

function armarPropuesta(
  candidata: Candidata,
  actual: Record<IdDeEje, EjeDeRiesgo>,
  simulado: Record<IdDeEje, EjeDeRiesgo>,
): PropuestaSubirTir {
  const ejes = TODOS_LOS_EJES.map((eje) => evaluarEje(eje, candidata, actual, simulado))
  return {
    candidata,
    ejes,
    ningunEjeEmpeora: !ejes.some((e) => e.estado === 'empeora') && candidata.flags.mismo_emisor,
  }
}

export interface ResultadoEtapaLocalSubirTir {
  sobrevivientes: Candidata[]
  descartes: DescarteCandidata[]
  evaluadas: number
}

/**
 * Primera etapa, sin red: se queda con las candidatas de mejora de rendimiento cuyos tres ejes
 * medibles locales tienen delta calculable.
 *
 * Las candidatas `mejora_perfil` no entran ni como propuesta ni como descarte: son el insumo del
 * otro modo, no algo que este haya evaluado y rechazado. Contarlas como descarte inflaría el
 * recuento con rotaciones que nunca se pidieron acá.
 */
export function evaluarEtapaLocalSubirTir(
  candidatas: Candidata[],
  vectorActual: EjeDeRiesgo[],
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
): ResultadoEtapaLocalSubirTir {
  const elegibles = candidatas.filter((c) => c.tipo === 'mejora_rendimiento')
  const actual = indexarPorId(vectorActual)
  const sobrevivientes: Candidata[] = []
  const descartes: DescarteCandidata[] = []

  for (const candidata of elegibles) {
    const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
    // `concentracion: null` a propósito: ese eje se mide en la etapa 2 con la respuesta real.
    const simulado = indexarPorId(vectorDeRiesgo(posicionesSimuladas, porTicker, null))
    const ejeSinDelta = primerEjeSinDelta(candidata, actual, simulado)
    if (ejeSinDelta !== null) descartes.push({ candidata, eje: ejeSinDelta, motivo: 'sin_dato' })
    else sobrevivientes.push(candidata)
  }

  return { sobrevivientes, descartes, evaluadas: elegibles.length }
}

/**
 * Encadena las dos etapas. La segunda **mide, no filtra**: la única causa de descarte acá es que la
 * concentración simulada no se pueda calcular. Que la concentración empeore es exactamente lo que
 * esta feature existe para mostrar.
 */
export function evaluarSubirTir(
  candidatas: Candidata[],
  vectorActual: EjeDeRiesgo[],
  posicionesActuales: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracionesSimuladas: ReadonlyMap<string, Concentracion | null>,
): ResultadoSubirTir {
  const local = evaluarEtapaLocalSubirTir(candidatas, vectorActual, posicionesActuales, porTicker)
  const actual = indexarPorId(vectorActual)
  const propuestas: PropuestaSubirTir[] = []
  const descartes: DescarteCandidata[] = [...local.descartes]

  for (const candidata of local.sobrevivientes) {
    const posicionesSimuladas = carteraSimuladaDeCandidata(posicionesActuales, candidata)
    const concentracionSimulada = concentracionesSimuladas.get(claveCandidata(candidata)) ?? null
    const simulado = indexarPorId(vectorDeRiesgo(posicionesSimuladas, porTicker, concentracionSimulada))

    if (actual.concentracion.valor === null || simulado.concentracion.valor === null) {
      descartes.push({ candidata, eje: 'concentracion', motivo: 'sin_dato' })
      continue
    }

    propuestas.push(armarPropuesta(candidata, actual, simulado))
  }

  return { hayPropuesta: propuestas.length > 0, propuestas, descartes, evaluadas: local.evaluadas }
}

/** Los ejes que hay que nombrar como contrapartida: los que empeoran, más el crédito si cambia. */
export function contrapartidasDe(propuesta: PropuestaSubirTir): EvaluacionEje[] {
  return propuesta.ejes.filter(
    (e) => e.estado === 'empeora' || (e.eje === 'credito' && !propuesta.candidata.flags.mismo_emisor),
  )
}

export { EJES_MEDIBLES }
