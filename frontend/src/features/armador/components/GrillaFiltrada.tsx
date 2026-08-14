/**
 * Contenedor que cruza la grilla × universo por ticker y decide qué meses ve la grilla — F-017.
 *
 * `useEspeciesUniverso()` es la misma consulta que ya usa `CarteraEditable` (F-018): React Query
 * la cachea, así que esto no duplica el fetch. Cuando el universo está pendiente o con error, la
 * grilla se dibuja igual con los meses sin filtrar y la barra se declara no disponible — nunca se
 * filtra a medias con un universo incompleto (regla del plan).
 */

import { useMemo } from 'react'

import { CLAVES_RENTA_VARIABLE, ordenarSegmentos } from '@/components/SelectorSegmento'

import { ChipsTematicos } from './ChipsTematicos'
import { FiltrosGrilla } from './FiltrosGrilla'
import { GrillaDoceMeses } from './GrillaDoceMeses'
import { useEspeciesUniverso } from '../hooks/useEspeciesUniverso'
import {
  OPCIONES_FACETADAS_VACIAS,
  facetarFiltros,
  filtrarMeses,
  hayFiltrosActivos,
} from '../lib/filtros'
import type { Especie, MesDelCalendario } from '../lib/schema'
import { useArmador } from '../store/carteraStore'

const CLAVES_RENTA_VARIABLE_SET = new Set<string>(CLAVES_RENTA_VARIABLE)

export function GrillaFiltrada({ meses }: { meses: MesDelCalendario[] }) {
  const { filtros } = useArmador()
  const consultaUniverso = useEspeciesUniverso()
  const universoDisponible = consultaUniverso.isSuccess

  const cruce = useMemo(() => {
    const mapa = new Map<string, Especie>()
    if (!universoDisponible) return mapa
    const tickersVentana = new Set(meses.flatMap((mes) => mes.instrumentos.map((i) => i.ticker)))
    for (const especie of consultaUniverso.data) {
      if (tickersVentana.has(especie.ticker)) mapa.set(especie.ticker, especie)
    }
    return mapa
  }, [meses, universoDisponible, consultaUniverso.data])

  // Las pestañas de segmento se calculan sobre el cruce entero y **no** se facetan: son la
  // estructura del mercado a la vista, y esconder CER o Tasa fija $ porque el filtro de TIR de
  // fábrica las deja en cero le sacaría al asesor justamente la forma de pivotar hacia ellas. Que
  // una pestaña dé cero ya lo dice el mensaje de "ningún papel pasa los filtros".
  const segmentos = useMemo(() => {
    const especiesDelCruce = [...cruce.values()]
    // Sólo renta fija: la grilla del armador es de renta fija, así que las claves de renta
    // variable (F-052) nunca se ofrecen como pestaña acá, aunque estuvieran en el universo.
    const clavesSegmento = [...new Set(especiesDelCruce.map((e) => e.segmento))].filter(
      (clave) => !CLAVES_RENTA_VARIABLE_SET.has(clave),
    )
    return ordenarSegmentos(clavesSegmento).map((clave) => ({
      clave,
      naturaleza: especiesDelCruce.find((e) => e.segmento === clave)?.naturaleza ?? '',
    }))
  }, [cruce])

  // Sin universo no hay con qué facetar: las opciones quedan vacías y los filtros del store se
  // muestran tal cual (la barra está deshabilitada). Apagarlos acá haría parpadear la selección
  // del asesor mientras carga, para restaurarla un segundo después.
  const { opciones: facetas, efectivos, apagadas } = useMemo(() => {
    if (!universoDisponible) {
      return { opciones: OPCIONES_FACETADAS_VACIAS, efectivos: filtros, apagadas: [] }
    }
    return facetarFiltros(meses, cruce, filtros)
  }, [meses, cruce, filtros, universoDisponible])

  const opciones = useMemo(() => ({ segmentos, ...facetas }), [segmentos, facetas])

  // Calificación visible en cada tarjeta de la grilla, aunque no haya filtro activo — declarar el
  // dato es distinto de filtrar por él (GrillaDoceMeses → TarjetaPapel).
  const calificacionPorTicker = useMemo(() => {
    const mapa = new Map<string, string | null>()
    for (const especie of cruce.values()) mapa.set(especie.ticker, especie.calificacion)
    return mapa
  }, [cruce])

  // Lo mismo con la clase de activo: sin ella, soberano y corporativo se leen igual en la grilla.
  const clasePorTicker = useMemo(() => {
    const mapa = new Map<string, string>()
    for (const especie of cruce.values()) mapa.set(especie.ticker, especie.clase_activo)
    return mapa
  }, [cruce])

  const filtrado = useMemo(() => {
    if (!universoDisponible) {
      const tickers = new Set(meses.flatMap((mes) => mes.instrumentos.map((i) => i.ticker)))
      return { meses, total: tickers.size, visibles: tickers.size, sinCruce: 0 }
    }
    // Filtran los efectivos, no los del store: una selección que el facetado apagó no puede
    // seguir descartando papeles desde la sombra.
    return filtrarMeses(meses, cruce, efectivos)
  }, [meses, cruce, efectivos, universoDisponible])

  const deshabilitado = !universoDisponible
  const cero = universoDisponible && filtrado.visibles === 0 && hayFiltrosActivos(efectivos)

  return (
    <>
      <ChipsTematicos />
      <FiltrosGrilla
        opciones={opciones}
        efectivos={efectivos}
        apagadas={apagadas}
        conteo={filtrado}
        deshabilitado={deshabilitado}
        motivoDeshabilitado={consultaUniverso.isError ? 'error' : 'cargando'}
      />
      {cero ? (
        <p style={{ margin: '10px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          Ningún papel de la ventana pasa los filtros activos (0 de {filtrado.total}). Probá con
          &quot;limpiar filtros&quot; en la barra de arriba.
        </p>
      ) : (
        <GrillaDoceMeses
          meses={filtrado.meses}
          calificacionPorTicker={calificacionPorTicker}
          clasePorTicker={clasePorTicker}
        />
      )}
    </>
  )
}
