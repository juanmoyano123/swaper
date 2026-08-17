/**
 * F-042 — el modelo neutral que Excel y PDF renderizan igual: puro, sin ningún binario. Separado
 * de `hojasExcel.ts`/`seccionesPdf.ts` para poder testear el *contenido* del export (qué filas, qué
 * declaraciones, qué falta) sin generar un archivo.
 *
 * **Los tres GWT de F-042, hechos estructura:**
 * - GWT-1: `rendimientos` trae las cuatro naturalezas siempre abiertas (`rendimientosPorNaturaleza`
 *   — la misma función que usa `ColumnaKpis`/`DiagnosticoCartera`, misma vara por identidad de
 *   código) y el tipo `ModeloExport` no tiene ningún campo de "rendimiento total": no hay dónde
 *   poner un promedio aunque alguien quisiera.
 * - GWT-2: `declaraciones.lamina` cuenta las posiciones de renta fija sin lámina informada y su
 *   peso — el mismo criterio que `resumenAjuste()` del armador, sobre datos congelados.
 * - GWT-3: `pie` lleva la hora del snapshot de precios y la demora de la fuente, declaradas por
 *   separado de cuándo se generó el archivo.
 *
 * **Cartera guardada antes de F-042** (`snapshot.mercado === undefined`): el modelo se arma igual,
 * con los atributos de mercado ausentes y una nota que lo declara — nunca se recalculan con
 * precios de hoy (eso sería "Revaluar a hoy", otra función, no un export).
 */

import { BLOQUE_POR_CLASE_ACTIVO, ORDEN_DE_BLOQUES, ROTULO_DE_BLOQUE, type IdBloque } from '@/lib/cartera/bloques'
import {
  plazoPromedio,
  rendimientosPorNaturaleza,
  type EspecieMetricas,
  type PosicionPonderada,
  type RendimientoPorNaturaleza,
} from '@/lib/cartera/metricas'

import type {
  CalendarioCongelado,
  EjeCongelado,
  EspecieCongelada,
  SnapshotArmador,
  SnapshotCargada,
  SnapshotCartera,
} from '../esquemaSnapshot'

export interface ContextoExport {
  /** El nombre guardado, o un rótulo declarando que es una propuesta en curso (sin guardar). */
  nombre: string
  descripcion: string | null
  /** ISO. La fecha del snapshot: la guardada al momento de guardar, o "ahora" para una en curso. */
  snapshotEn: string
  /** ISO. Cuándo se generó *este archivo* — puede ser mucho después de `snapshotEn`. */
  generadoEn: string
}

export interface FilaPosicionExport {
  ticker: string
  bloque: IdBloque
  emisorODenominacion: string | null
  ley: string | null
  calificacion: string | null
  sector: string | null
  naturaleza: string | null
  naturalezaNombre: string | null
  /** `null` cuando no se pudo congelar el dato (regla 1) — distinto de `rendimientoAplica: false`. */
  rendimiento: number | null
  /** `false` en renta variable y FCI: no tienen TIR, no es un faltante (regla 1: "no aplica" ≠ "s/d"). */
  rendimientoAplica: boolean
  duracion: number | null
  duracionAplica: boolean
  vencimiento: string | null
  lamina: number | null
  laminaAplica: boolean
  moneda: 'usd' | 'ars' | null
  precio: number | null
  /** VN en renta fija/FCI, cantidad de unidades en renta variable. */
  vnOCantidad: number | null
  invertido: number | null
  invertidoUsd: number | null
  /** Lo pedido — para origen armador, el peso del mandato; para origen cargada, no existe un
   *  "pedido" separado del real, así que coincide con `pesoReal` (incluido su `null` cuando el
   *  total invertido no se pudo determinar). */
  pesoPedido: number | null
  /** `null` cuando la posición no se pudo resolver a peso real. */
  pesoReal: number | null
}

export interface BloqueExport {
  id: IdBloque
  rotulo: string
  filas: FilaPosicionExport[]
}

export interface ExcluidaExport {
  ticker: string
  motivo: string
  montoDeclarado: number | null
}

export interface DeclaracionLaminaExport {
  /** `false` cuando no hay `mercado` congelado: no se sabe, y no es lo mismo que "0 sin lámina". */
  aplica: boolean
  posicionesSinLamina: number
  /** Σ pesoReal de las posiciones sin lámina. `null` cuando no hay ninguna posición ajustable
   *  (renta fija) sobre la que medir el porcentaje. */
  pctSinAjustar: number | null
}

export interface FilaCalendarioExport {
  etiqueta: string
  nombre: string
  /** Renta del mes, por moneda de cobro — nunca sumada entre monedas (regla 3). */
  porMoneda: Record<string, number | null>
}

export interface DetalleCalendarioExport {
  etiqueta: string
  ticker: string
  moneda: string
  renta: number | null
  amortizacion: number | null
  fechas: string[]
}

export interface CalendarioExport {
  disponible: boolean
  monedas: string[]
  meses: FilaCalendarioExport[]
  /** Renta anual, por moneda. */
  totalPorMoneda: Record<string, number>
  detalle: DetalleCalendarioExport[]
}

export interface EncabezadoExport {
  nombre: string
  descripcion: string | null
  origen: 'cargada' | 'armador'
  snapshotEn: string
  tipoDeCambio: number | null
  montoUsd: number
}

export interface PieExport {
  capturadoEn: string | null
  demoraMinutos: number | null
  demoraFuente: string | null
  snapshotEn: string
  generadoEn: string
  mercadoDisponible: boolean
}

export interface DeclaracionesExport {
  lamina: DeclaracionLaminaExport
  mercadoDisponible: boolean
  perfilConcentracion: string | null
  /** Texto libre: regla 2, faltantes estructurales, "guardada antes de F-042". Nunca un cálculo. */
  notas: string[]
}

export interface ModeloExport {
  encabezado: EncabezadoExport
  bloques: BloqueExport[]
  excluidas: ExcluidaExport[]
  rendimientos: RendimientoPorNaturaleza[]
  plazoPromedio: { anios: number | null; posicionesExcluidas: number }
  vector: EjeCongelado[] | null
  calendario: CalendarioExport
  declaraciones: DeclaracionesExport
  pie: PieExport
}

const NOTA_REGLA_2 =
  'Los rendimientos se muestran abiertos por naturaleza de tasa (TIR en dólares, dólar linked, tasa real sobre CER, TNA nominal en pesos): son unidades distintas y no se promedian entre sí.'

const NOTA_SIN_MERCADO =
  'Cartera guardada antes de F-042: sin atributos de mercado congelados — naturaleza de tasa, lámina, ejes de riesgo y calendario no disponibles. No se recalculan con precios de hoy.'

const MOTIVO_LABEL_CARGADA: Record<string, string> = {
  no_resuelta: 'no resuelta contra el universo',
  sin_nominal: 'resuelta pero sin nominal declarado (sólo monto, en una moneda no declarada)',
  sin_precio: 'sin precio de mercado o sin moneda de cotización conocida',
  sin_tipo_de_cambio: 'cotiza en pesos y no hay tipo de cambio implícito para llevarla a dólares',
}

function especiePorTicker(especies: readonly EspecieCongelada[]): Map<string, EspecieCongelada> {
  return new Map(especies.map((e) => [e.ticker, e]))
}

function bloqueIdDe(claseActivo: string | null, esFci: boolean, esRentaVariable: boolean): IdBloque {
  if (esFci) return 'fci'
  if (esRentaVariable) return 'renta_variable'
  if (!claseActivo) return 'sin_clasificar'
  return BLOQUE_POR_CLASE_ACTIVO[claseActivo] ?? 'sin_clasificar'
}

function agruparBloques(filas: readonly FilaPosicionExport[]): BloqueExport[] {
  const porBloque = new Map<IdBloque, FilaPosicionExport[]>()
  for (const fila of filas) {
    const acumuladas = porBloque.get(fila.bloque)
    if (acumuladas) acumuladas.push(fila)
    else porBloque.set(fila.bloque, [fila])
  }
  return ORDEN_DE_BLOQUES.filter((id) => porBloque.has(id)).map((id) => ({
    id,
    rotulo: ROTULO_DE_BLOQUE[id],
    filas: porBloque.get(id) as FilaPosicionExport[],
  }))
}

function filasDeCargada(snapshot: SnapshotCargada): FilaPosicionExport[] {
  const porTicker = especiePorTicker(snapshot.mercado?.especies ?? [])
  return snapshot.valuadas.map((v) => {
    const especie = porTicker.get(v.ticker) ?? null
    return {
      ticker: v.ticker,
      bloque: bloqueIdDe(especie?.clase_activo ?? null, false, false),
      emisorODenominacion: especie?.emisor ?? null,
      ley: especie?.ley ?? null,
      calificacion: especie?.calificacion ?? null,
      sector: especie?.sector ?? null,
      naturaleza: especie?.naturaleza ?? null,
      naturalezaNombre: especie?.naturaleza_nombre ?? null,
      rendimiento: especie?.rendimiento ?? null,
      rendimientoAplica: true,
      duracion: especie?.duracion ?? null,
      duracionAplica: true,
      vencimiento: especie?.vencimiento ?? null,
      lamina: especie?.lamina ?? null,
      laminaAplica: true,
      moneda: v.moneda,
      // La foto congelada de F-041 no llevaba precio por posición para el origen cargada.
      precio: null,
      vnOCantidad: null,
      invertido: v.invertido,
      invertidoUsd: v.invertidoUsd,
      pesoPedido: v.pesoReal,
      pesoReal: v.pesoReal,
    }
  })
}

function filasDeArmador(snapshot: SnapshotArmador): FilaPosicionExport[] {
  const porTicker = especiePorTicker(snapshot.mercado?.especies ?? [])
  return snapshot.resueltas.map((r) => {
    const esRentaFija = r.clase === 'renta_fija'
    const especie = porTicker.get(r.ticker) ?? null
    const pesoReal =
      r.invertidoUsd !== null && snapshot.totalInvertidoUsd > 0
        ? (r.invertidoUsd / snapshot.totalInvertidoUsd) * 100
        : null
    return {
      ticker: r.ticker,
      bloque: bloqueIdDe(esRentaFija ? (especie?.clase_activo ?? null) : null, r.clase === 'fci', r.clase === 'renta_variable'),
      emisorODenominacion: esRentaFija ? (especie?.emisor ?? null) : (especie?.denominacion ?? null),
      ley: esRentaFija ? (especie?.ley ?? null) : null,
      calificacion: esRentaFija ? (especie?.calificacion ?? null) : null,
      sector: esRentaFija ? (especie?.sector ?? null) : null,
      naturaleza: esRentaFija ? (especie?.naturaleza ?? null) : null,
      naturalezaNombre: esRentaFija ? (especie?.naturaleza_nombre ?? null) : null,
      rendimiento: esRentaFija ? (especie?.rendimiento ?? null) : null,
      rendimientoAplica: esRentaFija,
      duracion: esRentaFija ? (especie?.duracion ?? null) : null,
      duracionAplica: esRentaFija,
      vencimiento: esRentaFija ? (especie?.vencimiento ?? null) : null,
      lamina: esRentaFija ? (especie?.lamina ?? null) : null,
      laminaAplica: esRentaFija,
      moneda: r.moneda,
      precio: r.precio,
      vnOCantidad: r.clase === 'renta_variable' ? r.cantidad : r.vn,
      invertido: r.invertido,
      invertidoUsd: r.invertidoUsd,
      pesoPedido: r.peso,
      pesoReal,
    }
  })
}

function excluidasDeCargada(snapshot: SnapshotCargada): ExcluidaExport[] {
  const tickerPorId = new Map(snapshot.posiciones.map((p) => [p.id, p.tickerDeclarado]))
  return snapshot.excluidas.map((e) => ({
    ticker: tickerPorId.get(e.id) ?? e.id,
    motivo: MOTIVO_LABEL_CARGADA[e.motivo] ?? e.motivo,
    montoDeclarado: e.montoDeclarado,
  }))
}

function metricasPorTicker(especies: readonly EspecieCongelada[]): Map<string, EspecieMetricas> {
  const mapa = new Map<string, EspecieMetricas>()
  for (const e of especies) {
    if (e.naturaleza === null || e.naturaleza_nombre === null || e.segmento === null) continue
    mapa.set(e.ticker, {
      rendimiento: e.rendimiento,
      duracion: e.duracion,
      naturaleza: e.naturaleza,
      naturaleza_nombre: e.naturaleza_nombre,
      segmento: e.segmento,
    })
  }
  return mapa
}

function declaracionLamina(filas: readonly FilaPosicionExport[], mercadoDisponible: boolean): DeclaracionLaminaExport {
  if (!mercadoDisponible) return { aplica: false, posicionesSinLamina: 0, pctSinAjustar: null }

  const ajustables = filas.filter((f) => f.laminaAplica)
  if (ajustables.length === 0) return { aplica: true, posicionesSinLamina: 0, pctSinAjustar: null }

  const sinLamina = ajustables.filter((f) => f.lamina === null)
  const pctSinAjustar = sinLamina.reduce((acumulado, f) => acumulado + (f.pesoReal ?? 0), 0)
  return { aplica: true, posicionesSinLamina: sinLamina.length, pctSinAjustar }
}

function calendarioDesdeCongelado(calendario: CalendarioCongelado | null): CalendarioExport {
  if (!calendario) return { disponible: false, monedas: [], meses: [], totalPorMoneda: {}, detalle: [] }

  const totalPorMoneda = calendario.rentaAnual ?? {}
  return {
    disponible: true,
    monedas: Object.keys(totalPorMoneda),
    meses: calendario.meses.map((mes) => ({ etiqueta: mes.etiqueta, nombre: mes.nombre, porMoneda: mes.renta ?? {} })),
    totalPorMoneda,
    detalle: calendario.meses.flatMap((mes) =>
      mes.instrumentos.map((i) => ({
        etiqueta: mes.etiqueta,
        ticker: i.ticker,
        moneda: i.moneda,
        renta: i.renta,
        amortizacion: i.amortizacion,
        fechas: i.fechas,
      })),
    ),
  }
}

export function modeloDesdeSnapshot(snapshot: SnapshotCartera, contexto: ContextoExport): ModeloExport {
  const mercadoDisponible = snapshot.mercado !== undefined
  const especies = snapshot.mercado?.especies ?? []

  const filas = snapshot.origen === 'cargada' ? filasDeCargada(snapshot) : filasDeArmador(snapshot)
  const excluidas = snapshot.origen === 'cargada' ? excluidasDeCargada(snapshot) : []

  // Mismo criterio que `PanelRiesgo`/`PanelConcentracion`: se pondera sobre el peso real cuando se
  // pudo resolver, sobre el pedido si no — nunca se excluye una posición sin resolver del todo.
  const posicionesPonderadas: PosicionPonderada[] = filas.map((f) => ({
    ticker: f.ticker,
    peso: f.pesoPedido,
    pesoReal: f.pesoReal,
  }))
  const porTickerMetricas = metricasPorTicker(especies)

  const notas: string[] = []
  if (!mercadoDisponible) notas.push(NOTA_SIN_MERCADO)
  notas.push(NOTA_REGLA_2)

  return {
    encabezado: {
      nombre: contexto.nombre,
      descripcion: contexto.descripcion,
      origen: snapshot.origen,
      snapshotEn: contexto.snapshotEn,
      tipoDeCambio: snapshot.tipoDeCambio,
      montoUsd: snapshot.totalInvertidoUsd,
    },
    bloques: agruparBloques(filas),
    excluidas,
    rendimientos: rendimientosPorNaturaleza(posicionesPonderadas, porTickerMetricas),
    plazoPromedio: plazoPromedio(posicionesPonderadas, porTickerMetricas),
    vector: snapshot.mercado?.vector ?? null,
    calendario: calendarioDesdeCongelado(snapshot.mercado?.calendario ?? null),
    declaraciones: {
      lamina: declaracionLamina(filas, mercadoDisponible),
      mercadoDisponible,
      perfilConcentracion: snapshot.mercado?.perfilConcentracion ?? null,
      notas,
    },
    pie: {
      capturadoEn: snapshot.mercado?.fuenteDelDato?.capturadoEn ?? null,
      demoraMinutos: snapshot.mercado?.fuenteDelDato?.demoraMinutos ?? null,
      demoraFuente: snapshot.mercado?.fuenteDelDato?.demoraFuente ?? null,
      snapshotEn: contexto.snapshotEn,
      generadoEn: contexto.generadoEn,
      mercadoDisponible,
    },
  }
}
