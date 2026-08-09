/**
 * F-022 — rendimientos por naturaleza de tasa, plazo promedio y sensibilidad por segmento.
 *
 * Porta el algoritmo de `tools/armar_cartera.py::resumir()` (líneas 346–398) a los datos que
 * `useCarteraResuelta` ya trae, sobre renta fija (`PosicionResuelta` viene filtrada por el hook).
 *
 * **Regla 2 del dominio, hecha código**: las cuatro naturalezas nunca se combinan en un número.
 * El plazo promedio sí se agrega (años es unidad comparable entre naturalezas), la sensibilidad
 * no se agrega entre segmentos (cada uno es una curva distinta, aunque comparta unidad temporal).
 *
 * Se pondera sobre `pesoReal ?? peso` (mismo criterio que `PanelConcentracion`): el peso real
 * cuando la posición se pudo resolver, el pedido si no. Una posición sin `peso`/`pesoReal` (según
 * ese criterio, imposible: `peso` siempre está) no aporta a ningún `pctCartera` — pero acá el caso
 * real es `pesoReal` null, que cae al `peso` pedido, así que "sin con qué ponderar" no ocurre en la
 * práctica salvo que se documente distinto: se deja el criterio explícito por si el llamador un día
 * pasa un peso null real.
 */

import type { Especie } from './schema'
import type { PosicionResuelta } from './resolver'

const ORDEN_NATURALEZA = ['tir_usd', 'tir_dolar_linked', 'tasa_real_cer', 'tna_nominal_ars'] as const

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
  tna_nominal_ars: 'TNA nominal en pesos',
}

function pesoDe(pos: PosicionResuelta): number | null {
  return pos.pesoReal ?? pos.peso ?? null
}

function filas(resueltas: PosicionResuelta[], porTicker: Map<string, Especie>): Fila[] {
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
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
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
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): { anios: number | null; posicionesExcluidas: number } {
  const todas = filas(resueltas, porTicker)
  const conDato = todas.filter((f) => f.duracion !== null)
  const posicionesExcluidas = todas.length - conDato.length

  if (conDato.length === 0) return { anios: null, posicionesExcluidas }

  const anios = conDato.reduce((acumulado, f) => acumulado + (f.duracion! * f.peso) / 100, 0)
  return { anios, posicionesExcluidas }
}

export function sensibilidadPorSegmento(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
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
