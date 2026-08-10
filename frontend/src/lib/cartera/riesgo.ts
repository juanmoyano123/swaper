/**
 * F-031 — el perfil de riesgo de una cartera como vector de seis ejes, nunca como un score.
 *
 * **Tipos de entrada estructurales, no importados de ninguna feature** (mismo patrón que
 * `metricas.ts`): armador, diagnóstico y una futura propuesta (F-033+) pasan su tipo más
 * específico sin adaptar nada. Es el criterio de aceptación del riesgo R12 (`plan.md:2774`): la
 * misma composición, armada de las tres formas, tiene que dar el mismo vector — se verifica en
 * `__tests__/riesgo.test.ts` con `deepEqual` de las tres llamadas.
 *
 * **Regla 7 del dominio, hecha código**: no existe en ningún tipo de acá un campo que agregue los
 * seis ejes en un número. `vectorDeRiesgo()` siempre devuelve exactamente seis `EjeDeRiesgo`, en
 * el orden fijo declarado abajo — no hay dónde poner un score aunque alguien quisiera.
 */

import type { Concentracion } from './esquemaConcentracion'
import type { Especie } from './esquemaEspecie'
import {
  rendimientosPorNaturaleza,
  type EspecieMetricas,
  type PosicionPonderada,
} from './metricas'

export type IdDeEje = 'duracion' | 'credito' | 'legislacion' | 'liquidez' | 'concentracion' | 'moneda'

/** Lo que el vector necesita de una especie del universo, sin importar de dónde salió. */
export interface EspecieRiesgo {
  ticker: string
  segmento: string
  naturaleza: string
  naturaleza_nombre: string
  clase_activo: string
  duracion: number | null
  ley: string | null
  volumen_usd: number | null
  calificacion: string | null
  dato_sano: boolean
}

/** Una posición con su peso, sin importar si viene del armador, del diagnóstico o de una
 *  propuesta que todavía no existe — es la misma forma que ya usan `useConcentracion` y
 *  `rendimientosPorNaturaleza`. */
export interface PosicionConPeso {
  ticker: string
  peso: number
}

export interface TramoDeEje {
  nombre: string
  valor: number
  unidad: 'pp' | 'percentil'
  sinDato: boolean
  /** El tope del perfil contra el que se mide este tramo, cuando aplica (eje concentración). */
  tope: number | null
}

export interface GrupoDeEje {
  titulo: string
  tramos: TramoDeEje[]
}

export interface CoberturaDeEje {
  conDato: number
  posiciones: number
  pesoConDato: number
  pesoTotal: number
  /** Faltantes estructurales declarados: "sin calificación", "spread aún no disponible", etc. */
  notas: string[]
}

export interface EjeDeRiesgo {
  id: IdDeEje
  nombre: string
  /** Métrica escalar del eje, o `null` cuando el eje es puramente compositivo o no se pudo medir. */
  valor: number | null
  unidad: 'años' | 'percentil' | 'pp' | null
  grupos: GrupoDeEje[]
  cobertura: CoberturaDeEje
}

/** Adapta una especie del universo (`/especies`) a lo que el vector necesita — mismo criterio en
 *  todo consumidor (armador, cartera cargada, export F-042) para que "la misma composición mide
 *  el mismo vector" (R12) no dependa de que cada uno copie el mapeo a mano. */
export function especieDeRiesgo(especie: Especie): EspecieRiesgo {
  return {
    ticker: especie.ticker,
    segmento: especie.segmento,
    naturaleza: especie.naturaleza,
    naturaleza_nombre: especie.naturaleza_nombre,
    clase_activo: especie.clase_activo,
    duracion: especie.duracion,
    ley: especie.ley,
    volumen_usd: especie.volumen_usd,
    calificacion: especie.calificacion,
    dato_sano: especie.dato_sano,
  }
}

interface FilaRiesgo {
  ticker: string
  peso: number
  especie: EspecieRiesgo | null
}

const ORDEN_EJES: IdDeEje[] = ['duracion', 'credito', 'legislacion', 'liquidez', 'concentracion', 'moneda']

// Calcado de `tools/detectar_swaps.py:81-82`.
const LEY_LOCAL = 'Ley Argentina'
const LEYES_EXTRANJERAS = new Set(['Ley N.Y.', 'Ley Europea', 'Extranjera'])

export function vectorDeRiesgo(
  posiciones: PosicionConPeso[],
  porTicker: ReadonlyMap<string, EspecieRiesgo>,
  concentracion: Concentracion | null,
): EjeDeRiesgo[] {
  const filas: FilaRiesgo[] = sumarPorTicker(posiciones).map((p) => ({
    ticker: p.ticker,
    peso: p.peso,
    especie: porTicker.get(p.ticker) ?? null,
  }))

  const ejes: Record<IdDeEje, EjeDeRiesgo> = {
    duracion: ejeDuracion(filas),
    credito: ejeCredito(filas),
    legislacion: ejeLegislacion(filas),
    liquidez: ejeLiquidez(filas, porTicker),
    concentracion: ejeConcentracion(concentracion, filas.length),
    moneda: ejeMoneda(filas),
  }

  return ORDEN_EJES.map((id) => ejes[id])
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

function suma(filas: { peso: number }[]): number {
  return filas.reduce((acumulado, f) => acumulado + f.peso, 0)
}

function notaFueraDelUniverso(filas: FilaRiesgo[]): string[] {
  const fuera = filas.filter((f) => f.especie === null).length
  return fuera > 0 ? [`${fuera} posición(es) fuera del universo de renta fija`] : []
}

// --- 1. Duración -------------------------------------------------------------------------------

function ejeDuracion(filas: FilaRiesgo[]): EjeDeRiesgo {
  const posiciones = filas.length
  const pesoTotal = suma(filas)
  const conDato = filas.filter((f) => f.especie?.duracion !== null && f.especie?.duracion !== undefined)
  const pesoConDato = suma(conDato)

  const valor = pesoConDato > 0
    ? conDato.reduce((acumulado, f) => acumulado + f.especie!.duracion! * f.peso, 0) / pesoConDato
    : null

  const notas = notaFueraDelUniverso(filas)
  // Difiere a propósito de `plazoPromedio()`: se pondera sólo sobre el peso *con* duración, así
  // que la cobertura efectiva se declara siempre, no sólo cuando es parcial.
  if (pesoTotal > 0) {
    const pct = Math.round((pesoConDato / pesoTotal) * 100)
    notas.push(`sobre el ${pct}% del peso con duración informada`)
  }

  return {
    id: 'duracion',
    nombre: 'Duración',
    valor,
    unidad: 'años',
    // Sin tramos a propósito: `TramoDeEje.unidad` sólo admite 'pp' | 'percentil', y años no
    // encaja ahí — la decisión que el plan deja abierta se resuelve por el propio tipo.
    grupos: [],
    cobertura: { conDato: conDato.length, posiciones, pesoConDato, pesoTotal, notas },
  }
}

// --- 2. Crédito ----------------------------------------------------------------------------------

function ejeCredito(filas: FilaRiesgo[]): EjeDeRiesgo {
  const posiciones = filas.length
  const pesoTotal = suma(filas)
  const conEspecie = filas.filter((f) => f.especie !== null)

  const porClase = new Map<string, number>()
  for (const f of conEspecie) {
    const clase = f.especie!.clase_activo
    porClase.set(clase, (porClase.get(clase) ?? 0) + f.peso)
  }
  const tramosClase: TramoDeEje[] = ordenarPorPeso(porClase).map(([nombre, valor]) => ({
    nombre,
    valor,
    unidad: 'pp',
    sinDato: false,
    tope: null,
  }))

  const conCalificacion = filas.filter((f) => f.especie?.calificacion != null)
  const porCalificacion = new Map<string, number>()
  for (const f of conCalificacion) {
    const calificacion = f.especie!.calificacion!
    porCalificacion.set(calificacion, (porCalificacion.get(calificacion) ?? 0) + f.peso)
  }
  const tramosCalificacion: TramoDeEje[] = ordenarPorPeso(porCalificacion).map(([nombre, valor]) => ({
    nombre,
    valor,
    unidad: 'pp',
    sinDato: false,
    tope: null,
  }))
  const pesoSinCalificacion = filas
    .filter((f) => f.especie?.calificacion == null)
    .reduce((acumulado, f) => acumulado + f.peso, 0)
  if (pesoSinCalificacion > 0) {
    tramosCalificacion.push({ nombre: 'sin calificación', valor: pesoSinCalificacion, unidad: 'pp', sinDato: true, tope: null })
  }

  const conDato = conCalificacion.length
  const pesoConDato = suma(conCalificacion)
  const notas = notaFueraDelUniverso(filas)
  if (conDato < posiciones) {
    notas.push(
      `sin calificación en ${posiciones - conDato} posiciones: el armado y las rotaciones usan los proxies del perfil (tope de rendimiento del segmento, percentil de liquidez, topes de concentración) — la calificación nunca filtra`,
    )
  }

  return {
    id: 'credito',
    nombre: 'Crédito',
    valor: null,
    unidad: null,
    grupos: [
      { titulo: 'Clase', tramos: tramosClase },
      { titulo: 'Calificación', tramos: tramosCalificacion },
    ],
    cobertura: { conDato, posiciones, pesoConDato, pesoTotal, notas },
  }
}

// --- 3. Legislación ------------------------------------------------------------------------------

function ejeLegislacion(filas: FilaRiesgo[]): EjeDeRiesgo {
  const posiciones = filas.length
  const pesoTotal = suma(filas)
  const conEspecie = filas.filter((f) => f.especie !== null)

  const porLey = new Map<string, number>()
  let pesoExtranjera = 0
  const leyesDesconocidas = new Set<string>()

  for (const f of conEspecie) {
    const ley = f.especie!.ley
    const clave = ley ?? 'ley no informada'
    porLey.set(clave, (porLey.get(clave) ?? 0) + f.peso)
    if (ley === null) continue
    if (ley === LEY_LOCAL) continue
    if (LEYES_EXTRANJERAS.has(ley)) {
      pesoExtranjera += f.peso
    } else {
      leyesDesconocidas.add(ley)
    }
  }

  // `valor` es la suma del peso bajo ley extranjera, no un cociente: con la cartera vacía o sin
  // ninguna ley extranjera conocida da 0 por construcción (suma de cero términos), nunca `null` —
  // decisión explícita del edge case "ninguna posición con ley conocida" del plan.
  const valor = pesoExtranjera

  const tramos: TramoDeEje[] = ordenarPorPeso(porLey).map(([nombre, tramoValor]) => ({
    nombre,
    valor: tramoValor,
    unidad: 'pp',
    sinDato: nombre === 'ley no informada',
    tope: null,
  }))

  const conDato = conEspecie.filter((f) => f.especie!.ley !== null).length
  const pesoConDato = conEspecie
    .filter((f) => f.especie!.ley !== null)
    .reduce((acumulado, f) => acumulado + f.peso, 0)

  const notas = notaFueraDelUniverso(filas)
  const pesoConocido = pesoExtranjera + suma(conEspecie.filter((f) => f.especie!.ley === LEY_LOCAL))
  if (conEspecie.length > 0 && pesoConocido === 0 && leyesDesconocidas.size === 0) {
    notas.push('ninguna posición con ley informada: el 0% no implica ley local, es ausencia de dato')
  }
  for (const ley of leyesDesconocidas) {
    notas.push(`ley '${ley}' no reconocida como local ni extranjera: excluida del valor del eje`)
  }

  return {
    id: 'legislacion',
    nombre: 'Legislación',
    valor,
    unidad: 'pp',
    grupos: [{ titulo: 'Por ley', tramos }],
    cobertura: { conDato, posiciones, pesoConDato, pesoTotal, notas },
  }
}

// --- 4. Liquidez -----------------------------------------------------------------------------------

function ejeLiquidez(filas: FilaRiesgo[], porTicker: ReadonlyMap<string, EspecieRiesgo>): EjeDeRiesgo {
  const posiciones = filas.length
  const pesoTotal = suma(filas)

  const volumenesPorSegmento = new Map<string, number[]>()
  for (const especie of porTicker.values()) {
    if (!especie.dato_sano || especie.volumen_usd === null) continue
    const lista = volumenesPorSegmento.get(especie.segmento) ?? []
    lista.push(especie.volumen_usd)
    volumenesPorSegmento.set(especie.segmento, lista)
  }

  function percentilDe(segmento: string, volumen: number): number | null {
    const lista = volumenesPorSegmento.get(segmento)
    if (!lista || lista.length === 0) return null
    const menoresOIguales = lista.filter((v) => v <= volumen).length
    return (100 * menoresOIguales) / lista.length
  }

  interface AcumuladorSegmento {
    pesoSegmento: number
    pesoConDato: number
    sumaPonderada: number
  }
  const porSegmento = new Map<string, AcumuladorSegmento>()
  let pesoConDatoTotal = 0
  let sumaPonderadaTotal = 0
  let conDato = 0

  for (const f of filas) {
    if (!f.especie) continue
    const segmento = f.especie.segmento
    const acumulador = porSegmento.get(segmento) ?? { pesoSegmento: 0, pesoConDato: 0, sumaPonderada: 0 }
    acumulador.pesoSegmento += f.peso

    if (f.especie.dato_sano && f.especie.volumen_usd !== null) {
      const percentil = percentilDe(segmento, f.especie.volumen_usd)
      if (percentil !== null) {
        acumulador.pesoConDato += f.peso
        acumulador.sumaPonderada += percentil * f.peso
        pesoConDatoTotal += f.peso
        sumaPonderadaTotal += percentil * f.peso
        conDato++
      }
    }
    porSegmento.set(segmento, acumulador)
  }

  const valor = pesoConDatoTotal > 0 ? sumaPonderadaTotal / pesoConDatoTotal : null

  const tramos: TramoDeEje[] = [...porSegmento.entries()]
    .sort((a, b) => b[1].pesoSegmento - a[1].pesoSegmento)
    .map(([segmento, acumulador]) => ({
      nombre: segmento,
      valor: acumulador.pesoConDato > 0 ? acumulador.sumaPonderada / acumulador.pesoConDato : 0,
      unidad: 'percentil' as const,
      sinDato: acumulador.pesoConDato === 0,
      tope: null,
    }))

  const notas = notaFueraDelUniverso(filas)
  // El spread ya existe y se mide (F-035), pero por rotación y no por especie: viaja dentro del
  // costo de cada candidata de `POST /rotaciones`, no en la vista viva del universo. Este percentil
  // sigue siendo de volumen puro, y decirlo evita leerlo como si incluyera el costo de salida.
  notas.push('spread bid/ask: no entra en este percentil — se mide por rotación, dentro del costo de rotar (F-035)')

  return {
    id: 'liquidez',
    nombre: 'Liquidez',
    valor,
    unidad: 'percentil',
    grupos: [{ titulo: 'Por segmento', tramos }],
    cobertura: { conDato, posiciones, pesoConDato: pesoConDatoTotal, pesoTotal, notas },
  }
}

// --- 5. Concentración ------------------------------------------------------------------------------

function ejeConcentracion(concentracion: Concentracion | null, posiciones: number): EjeDeRiesgo {
  if (concentracion === null) {
    return {
      id: 'concentracion',
      nombre: 'Concentración',
      valor: null,
      unidad: null,
      grupos: [],
      cobertura: {
        conDato: 0,
        posiciones,
        pesoConDato: 0,
        pesoTotal: 0,
        notas: ['eje no medido: sin respuesta del servicio de concentración'],
      },
    }
  }

  const topesCredito = concentracion.topes.filter((t) => t.tipo === 'soberano' || t.tipo === 'emisor')
  const maxCredito = topesCredito.length > 0 ? topesCredito.reduce((a, b) => (b.peso > a.peso ? b : a)) : null
  const topesSector = concentracion.topes.filter((t) => t.tipo === 'sector')
  const maxSector = topesSector.length > 0 ? topesSector.reduce((a, b) => (b.peso > a.peso ? b : a)) : null

  const tramos: TramoDeEje[] = []
  if (maxCredito) {
    tramos.push({ nombre: 'máximo por crédito', valor: maxCredito.peso, unidad: 'pp', sinDato: false, tope: maxCredito.tope })
  }
  if (maxSector) {
    tramos.push({ nombre: 'máximo por sector', valor: maxSector.peso, unidad: 'pp', sinDato: false, tope: maxSector.tope })
  }
  if (concentracion.sectores.peso_sin_sector > 0) {
    tramos.push({ nombre: 'sin sector informado', valor: concentracion.sectores.peso_sin_sector, unidad: 'pp', sinDato: true, tope: null })
  }

  const notas: string[] = []
  if (concentracion.fuera_del_universo.length > 0) {
    notas.push(`${concentracion.fuera_del_universo.length} posición(es) fuera del universo de renta fija`)
  }

  return {
    id: 'concentracion',
    nombre: 'Concentración',
    valor: maxCredito?.peso ?? null,
    unidad: 'pp',
    grupos: [{ titulo: 'Topes', tramos }],
    cobertura: {
      conDato: posiciones - concentracion.fuera_del_universo.length,
      posiciones,
      pesoConDato: concentracion.peso.medido,
      pesoTotal: concentracion.peso.declarado,
      notas,
    },
  }
}

// --- 6. Moneda -------------------------------------------------------------------------------------

function ejeMoneda(filas: FilaRiesgo[]): EjeDeRiesgo {
  const posiciones = filas.length
  const pesoTotal = suma(filas)
  const fueraDelUniverso = filas.filter((f) => f.especie === null)
  const pesoFuera = suma(fueraDelUniverso)

  const posicionesPonderadas: PosicionPonderada[] = filas.map((f) => ({
    ticker: f.ticker,
    peso: f.peso,
    // `null`, no el peso: así `pesoDe()` de `rendimientosPorNaturaleza` cae siempre a `peso`, que
    // es lo único que este eje tiene (nunca hay un "peso real" acá).
    pesoReal: null,
  }))
  const porTickerMetricas = new Map<string, EspecieMetricas>()
  for (const f of filas) {
    if (!f.especie) continue
    porTickerMetricas.set(f.ticker, {
      // Se descarta `rendimientoPond` en el resultado: este eje mide composición, no rendimiento.
      rendimiento: null,
      duracion: f.especie.duracion,
      naturaleza: f.especie.naturaleza,
      naturaleza_nombre: f.especie.naturaleza_nombre,
      segmento: f.especie.segmento,
    })
  }

  const resultados = rendimientosPorNaturaleza(posicionesPonderadas, porTickerMetricas)
  const tramos: TramoDeEje[] = resultados.map((r) => ({
    nombre: r.nombre,
    valor: r.pctCartera,
    unidad: 'pp',
    sinDato: false,
    tope: null,
  }))

  const notas = notaFueraDelUniverso(filas)

  return {
    id: 'moneda',
    nombre: 'Moneda',
    valor: null,
    unidad: null,
    grupos: [{ titulo: 'Por naturaleza de tasa', tramos }],
    // Cobertura 100% por construcción sobre lo que está en el universo: la naturaleza sale del
    // segmento, que toda especie sana tiene. Lo que no cubre es lo fuera del universo, declarado
    // en `notas` como en los demás ejes.
    cobertura: {
      conDato: posiciones - fueraDelUniverso.length,
      posiciones,
      pesoConDato: pesoTotal - pesoFuera,
      pesoTotal,
      notas,
    },
  }
}

function ordenarPorPeso(mapa: Map<string, number>): [string, number][] {
  return [...mapa.entries()].sort((a, b) => b[1] - a[1])
}
