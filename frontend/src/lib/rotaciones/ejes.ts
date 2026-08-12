/**
 * Vocabulario compartido por los dos modos del optimizador: F-033 ("mantener la TIR y bajar el
 * riesgo") y F-034 ("subir la TIR declarando la contrapartida").
 *
 * Los dos modos parten del mismo conjunto de candidatas de F-032 y lo particionan sin solaparse
 * —F-033 se queda con las que mueven el rendimiento dentro de ±0,5pp, F-034 con las que el motor
 * marcó `tipo: 'mejora_rendimiento'` (d_rend ≥ 0,5pp)—, pero deciden distinto: F-033 **filtra**
 * (el eje primario tiene que mejorar y ninguno de los otros cinco empeorar) y F-034 **declara**
 * (no filtra por empeorar; muestra cada contrapartida con su nombre y su unidad, regla 8).
 *
 * Lo que sí es común es el vocabulario: qué significa que un eje mejore o empeore, cómo se
 * identifica una candidata, cómo se arma la cartera simulada y con qué motivos se descarta. Vive
 * acá para que las dos políticas midan con la misma vara — y para que F-036 (aceptación rotación
 * por rotación) reciba de ambos modos los mismos nombres en vez de tener que reconciliar dos
 * formatos.
 *
 * `bajarRiesgo.ts` re-exporta lo que ya exportaba antes de esta extracción: ningún import externo
 * ni ningún test de F-033 cambió al mover este código.
 */

import type { EjeDeRiesgo, IdDeEje, PosicionConPeso } from '../cartera/riesgo'

import type { Candidata } from './esquemaRotaciones'

/** Los seis ejes de F-031, en el mismo orden fijo que `ORDEN_EJES` de `riesgo.ts` (regla 7). */
export const TODOS_LOS_EJES: IdDeEje[] = ['duracion', 'credito', 'legislacion', 'liquidez', 'concentracion', 'moneda']

export const NOMBRES_EJE: Record<IdDeEje, string> = {
  duracion: 'Duración',
  credito: 'Crédito',
  legislacion: 'Legislación',
  liquidez: 'Liquidez',
  concentracion: 'Concentración',
  moneda: 'Moneda',
}

/** Los tres ejes que se resuelven sin red, con `vectorDeRiesgo()` sobre la cartera simulada.
 *  Concentración queda afuera porque necesita un POST; crédito y moneda porque son compositivos. */
export const EJES_LOCALES: readonly ('duracion' | 'legislacion' | 'liquidez')[] = ['duracion', 'legislacion', 'liquidez']

/** Los cuatro ejes con métrica escalar, los únicos sobre los que existe un delta que mostrar. */
export type EjeMedible = 'duracion' | 'legislacion' | 'liquidez' | 'concentracion'

export type MotivoDescarte = 'empeora' | 'sin_dato' | 'sin_criterio_medible' | 'fuera_de_banda'

export interface DescarteCandidata {
  candidata: Candidata
  eje: IdDeEje
  motivo: MotivoDescarte
}

/** El resultado de comparar dos valores del mismo eje: siempre concluyente, porque hay dos números. */
export type EstadoComparado = 'mejora' | 'no_empeora' | 'empeora'

/** Lo anterior más el caso en que no hubo con qué comparar. */
export type EstadoEje = EstadoComparado | 'sin_dato'

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

export function sumarPorTicker(posiciones: PosicionConPeso[]): PosicionConPeso[] {
  const pesos = new Map<string, number>()
  const orden: string[] = []
  for (const p of posiciones) {
    if (!pesos.has(p.ticker)) orden.push(p.ticker)
    pesos.set(p.ticker, (pesos.get(p.ticker) ?? 0) + p.peso)
  }
  return orden.map((ticker) => ({ ticker, peso: pesos.get(ticker)! }))
}

export function indexarPorId(ejes: EjeDeRiesgo[]): Record<IdDeEje, EjeDeRiesgo> {
  const mapa = {} as Record<IdDeEje, EjeDeRiesgo>
  for (const eje of ejes) mapa[eje.id] = eje
  return mapa
}

/**
 * Duración: menos años es mejor. Legislación: más peso bajo ley extranjera es mejor — la Ley N.Y.
 * reduce el riesgo jurisdiccional frente a la Ley Argentina (mismo sentido que `mejora_ley` en
 * `backend/app/rotaciones/motor.py`: pasar de ley local a extranjera es la mejora, no al revés).
 * Liquidez: más percentil es mejor. Concentración: menos peso máximo por crédito es mejor.
 */
export function estadoPorValor(eje: EjeMedible, actual: number, simulado: number): EstadoComparado {
  const mejorSiMenor = eje === 'duracion' || eje === 'concentracion'
  if (simulado === actual) return 'no_empeora'
  const mejora = mejorSiMenor ? simulado < actual : simulado > actual
  return mejora ? 'mejora' : 'empeora'
}

/**
 * El estado de un eje local para una candidata, con los guardas de dato faltante en las puntas de
 * la rotación: sin ley en alguna punta no se puede afirmar nada del eje legislación, y sin volumen
 * en el destino no se puede afirmar nada del de liquidez (regla 1 — el hueco no se rellena).
 */
export function estadoEjeLocal(
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
