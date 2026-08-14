/**
 * Los filtros del universo — F-038, extendido con facetado en cascada el 14/08/2026.
 *
 * Nace de `components/FiltrosNumericos.tsx` (rendimiento/duración/precio/operado), que sigue
 * viviendo acá para no romper sus imports; se le suman las dimensiones discretas que ya tiene la
 * barra del armador — crédito, moneda, ley, sector, calificación, emisor — sobre el mismo motor
 * genérico de `@/lib/facetado` que usa `features/armador/lib/filtros.ts`. Los dos se **portan**
 * cada uno su propia lógica sobre ese motor común en vez de importarse entre sí: `features/
 * monitor/**` y `features/armador/**` tienen prohibido importarse (precedente F-017/F-018/F-038).
 *
 * Vacío significa "sin filtro": no hay un valor por defecto que discrimine filas, porque eso sería
 * decidir en silencio qué es "razonable" sin que el asesor lo haya pedido (mismo criterio que ya
 * declaraba `FiltrosNumericos`, ahora extendido a las dimensiones nuevas).
 */

import { facetar, type Faceta } from '@/lib/facetado'
import { SIN_MONEDA_DECLARADA } from '@/components/SelectorMoneda'

import type { Especie } from './schema'

export interface FiltrosUniverso {
  rendimientoMin: string
  rendimientoMax: string
  duracionMax: string
  /** Sólo especies con precio publicado. Apagado por defecto: un faltante se muestra y se cuenta. */
  soloConPrecio: boolean
  /** Sólo especies con volumen operado mayor a cero en la rueda. */
  soloOperadoHoy: boolean
  /** `clase_activo`, o `null` = Todos. */
  credito: string | null
  /** `moneda_cotizacion` (o `SIN_MONEDA_DECLARADA`), o `null` = sin elegir a mano. `null` **no**
   *  significa "mostrar todas mezcladas": eso violaría la regla 3 del dominio (nunca comparar
   *  entre monedas sin normalizar). Antes de filtrar la tabla se resuelve a una concreta con
   *  `monedaInicial` — ver `MonitorPage.tsx`. */
  moneda: string | null
  /** Clave de ley del universo, o LEY_NO_INFORMADA. `null` = sin filtro. */
  ley: string | null
  sector: string | null
  /** Multiselect de valores literales de `calificacion`, más CALIFICACION_NO_INFORMADA. Array
   *  vacío = sin filtro. */
  calificaciones: string[]
  emisor: string | null
}

export const FILTROS_VACIOS: FiltrosUniverso = {
  rendimientoMin: '',
  rendimientoMax: '',
  duracionMax: '',
  soloConPrecio: false,
  soloOperadoHoy: false,
  credito: null,
  moneda: null,
  ley: null,
  sector: null,
  calificaciones: [],
  emisor: null,
}

export const LEY_NO_INFORMADA = 'ley_no_informada'
export const CALIFICACION_NO_INFORMADA = 'calificacion_no_informada'

/**
 * Los umbrales y los dos interruptores: la parte de siempre, ajena al facetado. Una fila con
 * `rendimiento: null` no puede pasar un filtro de rendimiento activo —no se puede afirmar que un
 * dato que no existe cumple un umbral— pero sin filtros activos se muestra igual.
 *
 * `especie.rendimiento` es una fracción (0.13 = 13%), pero el input está rotulado en la unidad de
 * columna, así que lo que el asesor escribe se divide por 100 antes de comparar.
 */
function pasaFiltrosNumericos(
  especie: {
    rendimiento: number | null
    duracion: number | null
    precio: number | null
    volumen: number | null
  },
  filtros: FiltrosUniverso,
): boolean {
  const min = filtros.rendimientoMin === '' ? null : Number(filtros.rendimientoMin) / 100
  const max = filtros.rendimientoMax === '' ? null : Number(filtros.rendimientoMax) / 100
  const duracionMax = filtros.duracionMax === '' ? null : Number(filtros.duracionMax)

  if ((min !== null || max !== null) && especie.rendimiento === null) return false
  if (min !== null && especie.rendimiento !== null && especie.rendimiento < min) return false
  if (max !== null && especie.rendimiento !== null && especie.rendimiento > max) return false

  if (duracionMax !== null && especie.duracion === null) return false
  if (duracionMax !== null && especie.duracion !== null && especie.duracion > duracionMax) return false

  if (filtros.soloConPrecio && especie.precio === null) return false
  // Volumen cero y volumen sin publicar son cosas distintas y las dos quedan fuera de "operado hoy":
  // de la primera consta que no operó, de la segunda no consta que sí.
  if (filtros.soloOperadoHoy && !(especie.volumen !== null && especie.volumen > 0)) return false

  return true
}

/**
 * Si una especie pasa todos los filtros activos, discretos y numéricos.
 *
 * Campo null contra filtro activo: no pasa; sin ese filtro, se muestra igual (regla 1 del dominio,
 * mismo criterio que la barra del armador).
 */
export function pasaFiltros(especie: Especie, filtros: FiltrosUniverso): boolean {
  if (!pasaFiltrosNumericos(especie, filtros)) return false

  if (filtros.credito !== null && especie.clase_activo !== filtros.credito) return false

  if (filtros.moneda !== null) {
    if ((especie.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) !== filtros.moneda) return false
  }

  if (filtros.ley !== null) {
    if (filtros.ley === LEY_NO_INFORMADA) {
      if (especie.ley !== null) return false
    } else if (especie.ley !== filtros.ley) {
      return false
    }
  }

  if (filtros.sector !== null && especie.sector !== filtros.sector) return false

  if (filtros.calificaciones.length > 0) {
    if (especie.calificacion === null) {
      if (!filtros.calificaciones.includes(CALIFICACION_NO_INFORMADA)) return false
    } else if (!filtros.calificaciones.includes(especie.calificacion)) {
      return false
    }
  }

  if (filtros.emisor !== null && especie.emisor !== filtros.emisor) return false

  return true
}

/** Las seis dimensiones que el facetado acota. Los umbrales y los dos interruptores quedan afuera:
 *  son fuentes que siempre aplican (`pasaFiltrosNumericos`), no un select que pueda quedar
 *  apagado. */
export type DimensionFacetadaUniverso = 'credito' | 'moneda' | 'ley' | 'sector' | 'calificaciones' | 'emisor'

export interface SeleccionApagadaUniverso {
  dimension: DimensionFacetadaUniverso
  valor: string
}

/** Las opciones que la pantalla ofrece por dimensión, ya acotadas por el facetado. Crédito y
 *  moneda no están: sus chips muestran conteos (no sólo una lista de valores) y se calculan aparte
 *  con `contarPorCredito`/`contarPorMoneda` sobre el subconjunto que deja el resto de los filtros —
 *  ver `MonitorPage.tsx`. */
export interface OpcionesFacetadasUniverso {
  leyes: string[]
  tieneLeyNoInformada: boolean
  sectores: string[]
  calificaciones: string[]
  tieneCalificacionNoInformada: boolean
  emisores: string[]
}

/** Las seis dimensiones, como `Faceta<Especie>` para el motor genérico. El orden del array **es**
 *  el orden de validación: crédito y moneda primero —los dos chips, el corte más grueso— y después
 *  ley → sector → calificación → emisor, el mismo orden general→específico que ya usa la barra del
 *  armador. */
function facetasDeUniverso(filtros: FiltrosUniverso): Array<Faceta<Especie>> {
  return [
    {
      id: 'credito',
      seleccion: filtros.credito === null ? [] : [filtros.credito],
      coincide: (especie, valor) => especie.clase_activo === valor,
      valores: (especie) => [especie.clase_activo],
    },
    {
      id: 'moneda',
      seleccion: filtros.moneda === null ? [] : [filtros.moneda],
      coincide: (especie, valor) => (especie.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) === valor,
      valores: (especie) => [especie.moneda_cotizacion ?? SIN_MONEDA_DECLARADA],
    },
    {
      id: 'ley',
      seleccion: filtros.ley === null ? [] : [filtros.ley],
      coincide: (especie, valor) =>
        valor === LEY_NO_INFORMADA ? especie.ley === null : especie.ley === valor,
      valores: (especie) => [especie.ley ?? LEY_NO_INFORMADA],
    },
    {
      id: 'sector',
      seleccion: filtros.sector === null ? [] : [filtros.sector],
      coincide: (especie, valor) => especie.sector === valor,
      valores: (especie) => (especie.sector !== null ? [especie.sector] : []),
    },
    {
      id: 'calificaciones',
      seleccion: filtros.calificaciones,
      coincide: (especie, valor) =>
        valor === CALIFICACION_NO_INFORMADA ? especie.calificacion === null : especie.calificacion === valor,
      valores: (especie) => [especie.calificacion ?? CALIFICACION_NO_INFORMADA],
    },
    {
      id: 'emisor',
      seleccion: filtros.emisor === null ? [] : [filtros.emisor],
      coincide: (especie, valor) => especie.emisor === valor,
      valores: (especie) => (especie.emisor !== null ? [especie.emisor] : []),
    },
  ]
}

/**
 * Facetado en cascada del universo (14/08/2026), sobre el motor genérico de `@/lib/facetado` — ver
 * ese módulo para la semántica completa (validación por orden, opciones leave-one-out, selecciones
 * sin respaldo declaradas). Acá sólo se arman los descriptores por dimensión y se traduce el
 * resultado genérico a la forma que ya conoce la pantalla.
 *
 * `efectivos.moneda` puede seguir en `null` a la salida —sin elegir a mano, o apagada por no tener
 * especies bajo el resto de los filtros—: quien llama tiene que resolverla a una concreta con
 * `monedaInicial` antes de filtrar la tabla, nunca dejarla en `null` (regla 3).
 */
export function facetarUniverso(
  especies: Especie[],
  filtros: FiltrosUniverso,
): {
  opciones: OpcionesFacetadasUniverso
  efectivos: FiltrosUniverso
  apagadas: SeleccionApagadaUniverso[]
} {
  const resultado = facetar(especies, facetasDeUniverso(filtros), (especie) =>
    pasaFiltrosNumericos(especie, filtros),
  )

  const leyes = resultado.opciones.get('ley') ?? []
  const calificaciones = resultado.opciones.get('calificaciones') ?? []

  const opciones: OpcionesFacetadasUniverso = {
    leyes: leyes.filter((valor) => valor !== LEY_NO_INFORMADA),
    tieneLeyNoInformada: leyes.includes(LEY_NO_INFORMADA),
    sectores: resultado.opciones.get('sector') ?? [],
    calificaciones: calificaciones.filter((valor) => valor !== CALIFICACION_NO_INFORMADA).sort(),
    tieneCalificacionNoInformada: calificaciones.includes(CALIFICACION_NO_INFORMADA),
    emisores: resultado.opciones.get('emisor') ?? [],
  }

  const efectivos: FiltrosUniverso = {
    ...filtros,
    credito: resultado.efectivas.get('credito')?.[0] ?? null,
    moneda: resultado.efectivas.get('moneda')?.[0] ?? null,
    ley: resultado.efectivas.get('ley')?.[0] ?? null,
    sector: resultado.efectivas.get('sector')?.[0] ?? null,
    calificaciones: resultado.efectivas.get('calificaciones') ?? [],
    emisor: resultado.efectivas.get('emisor')?.[0] ?? null,
  }

  return {
    opciones,
    efectivos,
    apagadas: resultado.apagadas.map(({ dimension, valor }) => ({
      dimension: dimension as DimensionFacetadaUniverso,
      valor,
    })),
  }
}
