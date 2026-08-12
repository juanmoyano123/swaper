/**
 * Composición de la cartera de renta fija — F-023: por clase de activo, por segmento y por
 * emisor. `PanelConcentracion` (F-020) ya reporta sector, ley y naturaleza desde `/concentracion`;
 * estos tres cortes son los que ese panel no cubre y no se recalculan del mismo dato dos veces
 * (riesgo R12 de `plan.md:2774`).
 *
 * Mismo criterio que `lib/rendimientos.ts` en todo lo demás: funciones puras sobre
 * `(resueltas, porTicker)`, ponderadas por `pesoReal ?? peso` (el peso real cuando `resolver` lo
 * pudo calcular, el pedido cuando no — el panel declara sobre cuál se midió, igual que
 * `PanelConcentracion`), y una posición sin `porTicker.get(ticker)` —fuera del universo— se
 * excluye de los tres cortes, igual que `filas()` en `metricas.ts`.
 *
 * **Por clase de activo colapsa el soberano en un único tramo por construcción, no por caso
 * especial**: `clase_activo === 'bono_soberano'` es el mismo valor para GD30, AE38, DIC, TZX y
 * TY3 — agrupar por ese campo ya cumple la regla 4 del dominio sin lógica adicional.
 *
 * **Por emisor nunca reparte lo no informado**: `emisor: string | null` va a un tramo propio
 * ("emisor no informado", `sinDato: true`), nunca a los emisores conocidos (regla 1).
 */

import { etiquetaClase } from '@/lib/claseActivo'
import { nombreSegmento } from '@/components/SelectorSegmento'

import type { PosicionResuelta } from './resolver'
import type { Especie } from './schema'

export interface TramoComposicion {
  nombre: string
  peso: number
  sinDato?: boolean
}

const EMISOR_NO_INFORMADO = 'emisor no informado'

interface FilaComposicion {
  especie: Especie
  peso: number
}

function filas(resueltas: PosicionResuelta[], porTicker: Map<string, Especie>): FilaComposicion[] {
  const salida: FilaComposicion[] = []
  for (const r of resueltas) {
    const especie = porTicker.get(r.ticker)
    if (!especie) continue
    salida.push({ especie, peso: r.pesoReal ?? r.peso })
  }
  return salida
}

/** Agrupa por la clave que devuelve `claveDe`, ordenado por peso descendente (así el consumidor
 *  puede tomar `[0]` como "el tramo más pesado" sin volver a ordenar). */
function agrupar(
  filas: FilaComposicion[],
  claveDe: (especie: Especie) => string,
  nombreDe: (clave: string) => string,
  sinDato: (clave: string) => boolean,
): TramoComposicion[] {
  const pesos = new Map<string, number>()
  for (const fila of filas) {
    const clave = claveDe(fila.especie)
    pesos.set(clave, (pesos.get(clave) ?? 0) + fila.peso)
  }
  return [...pesos.entries()]
    .map(([clave, peso]) => ({ nombre: nombreDe(clave), peso, sinDato: sinDato(clave) || undefined }))
    .sort((a, b) => b.peso - a.peso)
}

export function composicionPorClase(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): TramoComposicion[] {
  return agrupar(
    filas(resueltas, porTicker),
    (especie) => especie.clase_activo,
    etiquetaClase,
    () => false,
  )
}

export function composicionPorSegmento(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): TramoComposicion[] {
  return agrupar(
    filas(resueltas, porTicker),
    (especie) => especie.segmento,
    nombreSegmento,
    () => false,
  )
}

export function composicionPorEmisor(
  resueltas: PosicionResuelta[],
  porTicker: Map<string, Especie>,
): TramoComposicion[] {
  return agrupar(
    filas(resueltas, porTicker),
    (especie) => especie.emisor ?? EMISOR_NO_INFORMADO,
    (clave) => clave,
    (clave) => clave === EMISOR_NO_INFORMADO,
  )
}

/** Qué peso se midió, dicho antes de mostrar cualquier número — mismo texto que
 *  `PanelConcentracion.tsx`, portado acá para que los dos paneles no puedan desalinearse. */
export function leyendaDelPeso(conPesoReal: number, total: number): string {
  if (conPesoReal === total)
    return `Medido sobre el peso real de las ${total} posiciones (invertido sobre el total invertido), no sobre la ponderación pedida.`
  if (conPesoReal === 0)
    return `Medido sobre la ponderación pedida de las ${total} posiciones: ninguna se pudo resolver a peso real por falta de precio o de tipo de cambio.`
  return `Medido sobre el peso real en ${conPesoReal} de ${total} posiciones; en las otras ${total - conPesoReal}, sobre la ponderación pedida (sin precio o sin tipo de cambio).`
}
