/**
 * F-022 — rendimientos por naturaleza de tasa, plazo promedio y sensibilidad por segmento.
 *
 * Porta el algoritmo de `tools/armar_cartera.py::resumir()` (líneas 346–398) a datos ya resueltos
 * de una cartera, sobre renta fija. Movido acá en la Tanda 11 desde
 * `features/armador/lib/rendimientos.ts` para que el diagnóstico de cartera (F-030) calcule con
 * exactamente las mismas funciones que el armador — es el criterio de aceptación del riesgo R12
 * de `plan.md:2774` ("la misma composición cargada y armada produce los mismos números").
 *
 * **Tipos de entrada estructurales, no importados de ninguna feature.** `PosicionPonderada` y
 * `EspecieMetricas` son subconjuntos de `PosicionResuelta` (armador) y de `Especie` (universo):
 * TypeScript acepta pasar el tipo más específico donde se pide el más genérico, así que ni el
 * armador ni el diagnóstico necesitan adaptar sus datos para llamar a estas funciones.
 *
 * **Regla 2 del dominio, hecha código**: las cinco naturalezas nunca se combinan en un número.
 * Son cinco desde la Tanda 2 (26/08/2026), cuando `tasa_fija` pasó a declarar su TIR efectiva anual
 * (`tir_ea_ars`) y dejó de compartir la `tna_nominal_ars` de badlar y tamar: una TIR EA en pesos y
 * una TNA en pesos no son promediables entre sí, aunque las dos cobren en la misma moneda.
 *
 * El plazo promedio sí se agrega (años es unidad comparable entre naturalezas), la sensibilidad
 * no se agrega entre segmentos (cada uno es una curva distinta, aunque comparta unidad temporal).
 *
 * Se pondera sobre `pesoReal ?? peso` (mismo criterio que `PanelConcentracion`): el peso real
 * cuando la posición se pudo resolver, el pedido si no.
 */

const ORDEN_NATURALEZA = [
  'tir_usd',
  'tir_dolar_linked',
  'tasa_real_cer',
  'tir_ea_ars',
  'tna_nominal_ars',
] as const

/** Lo que estas funciones necesitan de una posición resuelta, sin importar de dónde salió. */
export interface PosicionPonderada {
  ticker: string
  /** `number | null` porque `PosicionValuada` (diagnóstico) no tiene un "peso pedido" propio y
   *  mirrorea `pesoReal` acá: si no hay con qué ponderar, no hay ninguno de los dos. En el armador
   *  siempre es un número (el pedido nunca falta). */
  peso: number | null
  pesoReal: number | null
}

/** Lo que estas funciones necesitan de una especie del universo, sin importar de dónde salió. */
export interface EspecieMetricas {
  rendimiento: number | null
  duracion: number | null
  naturaleza: string
  naturaleza_nombre: string
  segmento: string
}

export interface RendimientoPorNaturaleza {
  naturaleza: string
  nombre: string
  pctCartera: number
  rendimientoPond: number | null
  posiciones: number
  posicionesExcluidas: number
  pctExcluido: number
}

export interface SensibilidadPorSegmento {
  segmento: string
  pctCartera: number
  duracionPond: number | null
  posiciones: number
  posicionesExcluidas: number
}

interface Fila {
  peso: number
  rendimiento: number | null
  duracion: number | null
  naturaleza: string
  naturalezaNombre: string
  segmento: string
}

/** Espeja `NOMBRE_NATURALEZA` del backend (`app/universo/segmentacion.py`): rótulo fijo para una
 *  naturaleza sin ninguna posición en la cartera, donde no hay especie de la que tomarlo. */
const NOMBRE_FIJO_NATURALEZA: Record<string, string> = {
  tir_usd: 'TIR en dólares (hard dollar)',
  tir_dolar_linked: 'Rendimiento dólar linked',
  tasa_real_cer: 'Tasa real sobre CER (por encima de inflación)',
  tir_ea_ars: 'TIR efectiva anual en pesos',
  tna_nominal_ars: 'TNA nominal en pesos',
}

function pesoDe(pos: PosicionPonderada): number | null {
  return pos.pesoReal ?? pos.peso ?? null
}

function filas(
  resueltas: PosicionPonderada[],
  porTicker: ReadonlyMap<string, EspecieMetricas>,
): Fila[] {
  const salida: Fila[] = []
  for (const pos of resueltas) {
    const peso = pesoDe(pos)
    if (peso === null) continue
    const especie = porTicker.get(pos.ticker)
    if (!especie) continue
    salida.push({
      peso,
      rendimiento: especie.rendimiento,
      duracion: especie.duracion,
      naturaleza: especie.naturaleza,
      naturalezaNombre: especie.naturaleza_nombre,
      segmento: especie.segmento,
    })
  }
  return salida
}

export function rendimientosPorNaturaleza(
  resueltas: PosicionPonderada[],
  porTicker: ReadonlyMap<string, EspecieMetricas>,
): RendimientoPorNaturaleza[] {
  const todas = filas(resueltas, porTicker)

  return ORDEN_NATURALEZA.map((naturaleza) => {
    const grupo = todas.filter((f) => f.naturaleza === naturaleza)
    const pctCartera = grupo.reduce((acumulado, f) => acumulado + f.peso, 0)
    const conDato = grupo.filter((f) => f.rendimiento !== null)
    const posicionesExcluidas = grupo.length - conDato.length

    let rendimientoPond: number | null = null
    if (conDato.length > 0) {
      const pesoConDato = conDato.reduce((acumulado, f) => acumulado + f.peso, 0)
      rendimientoPond =
        pesoConDato > 0
          ? conDato.reduce((acumulado, f) => acumulado + f.rendimiento! * (f.peso / pesoConDato), 0)
          : null
    }

    const pesoExcluido = grupo
      .filter((f) => f.rendimiento === null)
      .reduce((acumulado, f) => acumulado + f.peso, 0)

    return {
      naturaleza,
      nombre: grupo[0]?.naturalezaNombre ?? NOMBRE_FIJO_NATURALEZA[naturaleza],
      pctCartera,
      rendimientoPond,
      posiciones: grupo.length,
      posicionesExcluidas,
      pctExcluido: pesoExcluido,
    }
  })
}

export function plazoPromedio(
  resueltas: PosicionPonderada[],
  porTicker: ReadonlyMap<string, EspecieMetricas>,
): { anios: number | null; posicionesExcluidas: number } {
  const todas = filas(resueltas, porTicker)
  const conDato = todas.filter((f) => f.duracion !== null)
  const posicionesExcluidas = todas.length - conDato.length

  if (conDato.length === 0) return { anios: null, posicionesExcluidas }

  const anios = conDato.reduce((acumulado, f) => acumulado + (f.duracion! * f.peso) / 100, 0)
  return { anios, posicionesExcluidas }
}

export function sensibilidadPorSegmento(
  resueltas: PosicionPonderada[],
  porTicker: ReadonlyMap<string, EspecieMetricas>,
): SensibilidadPorSegmento[] {
  const todas = filas(resueltas, porTicker)

  const segmentos = new Map<string, Fila[]>()
  for (const fila of todas) {
    const grupo = segmentos.get(fila.segmento) ?? []
    grupo.push(fila)
    segmentos.set(fila.segmento, grupo)
  }

  const resultado: SensibilidadPorSegmento[] = []
  for (const [segmento, grupo] of segmentos) {
    const pctCartera = grupo.reduce((acumulado, f) => acumulado + f.peso, 0)
    const conDato = grupo.filter((f) => f.duracion !== null)
    const posicionesExcluidas = grupo.length - conDato.length

    let duracionPond: number | null = null
    if (conDato.length > 0) {
      const pesoConDato = conDato.reduce((acumulado, f) => acumulado + f.peso, 0)
      duracionPond =
        pesoConDato > 0
          ? conDato.reduce((acumulado, f) => acumulado + f.duracion! * (f.peso / pesoConDato), 0)
          : null
    }

    resultado.push({ segmento, pctCartera, duracionPond, posiciones: grupo.length, posicionesExcluidas })
  }

  return resultado.sort((a, b) => b.pctCartera - a.pctCartera)
}
