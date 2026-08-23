/**
 * Arma el snapshot que se guarda (F-041) a partir del estado vivo de cada origen. Funciones puras,
 * sin red: reciben lo que ya calcularon los hooks existentes (`useCarteraCargadaValuada`,
 * `useCarteraResuelta`, `useRentaVariableResuelta`) y arman el objeto por whitelist explícita —
 * nunca `{...todoElEstado}` — para que agregar un campo nuevo a esos hooks no filtre nada al
 * snapshot sin decidirlo acá (GWT-4).
 */

import type { PosicionCruda } from '@/features/cartera-ingreso/types'
import type {
  CarteraValuada,
  PosicionExcluidaValuacion,
  PosicionValuada,
} from '@/features/cartera-diagnostico/lib/valuacion'
import type {
  ClasePosicion,
  PosicionArmador,
} from '@/features/armador/store/carteraStore'
import type { PosicionResuelta } from '@/features/armador/lib/resolver'
import type { PosicionRvResuelta } from '@/features/armador/lib/resolverRentaVariable'
import type { EstadoDelDato } from '@/features/estado-dato/lib/schema'
import type { CalendarioUniverso } from '@/lib/cartera/esquemaCalendario'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { EjeDeRiesgo } from '@/lib/cartera/riesgo'
import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import type {
  EspecieCongelada,
  MercadoCongelado,
  ResueltaGuardada,
  SnapshotArmador,
  SnapshotCargada,
  SnapshotCartera,
} from './esquemaSnapshot'

/** Especie mínima que hace falta para etiquetar moneda y precio — sin importar el contrato entero
 *  de cada universo (renta fija y renta variable tienen esquemas de precio distintos). */
interface EspecieConMonedaYPrecio {
  precio: number | null
  moneda_cotizacion: string | null
}

function monedaNormalizada(cruda: string | null | undefined): 'usd' | 'ars' | null {
  const m = cruda?.toLowerCase() ?? null
  return m === 'usd' || m === 'ars' ? m : null
}

/** Lo que hace falta de una especie de renta fija (`/especies`) para congelarla — F-042. */
interface EspecieRentaFijaParaCongelar {
  clase_activo: string
  segmento: string
  naturaleza: string
  naturaleza_nombre: string
  rendimiento: number | null
  duracion: number | null
  vencimiento: string | null
  ley: string | null
  moneda_cupon: string | null
  emisor: string | null
  lamina: number | null
  calificacion: string | null
  sector: string | null
}

/** Lo que hace falta de una especie de renta variable para congelarla — F-042. */
interface EspecieRentaVariableParaCongelar {
  nombre_largo: string | null
}

/** Todo lo necesario para `armarMercadoCongelado` — F-042. Cada campo acepta `null`/ausente sin
 *  que la función invente nada: es lo que había disponible en el momento de guardar. */
export interface EntradaMercado {
  /** Sólo los tickers de la cartera se congelan — nunca el universo entero. */
  tickers: readonly string[]
  porTickerRentaFija: ReadonlyMap<string, EspecieRentaFijaParaCongelar>
  porTickerRentaVariable?: ReadonlyMap<string, EspecieRentaVariableParaCongelar>
  vector: EjeDeRiesgo[] | null
  perfilConcentracion: NombreDePerfil | null
  calendario: CalendarioUniverso | null
  estadoDelDato: EstadoDelDato | null
}

const ESPECIE_VACIA: Omit<EspecieCongelada, 'ticker' | 'denominacion'> = {
  clase_activo: null,
  segmento: null,
  naturaleza: null,
  naturaleza_nombre: null,
  rendimiento: null,
  duracion: null,
  vencimiento: null,
  ley: null,
  emisor: null,
  lamina: null,
  calificacion: null,
  sector: null,
  moneda_cupon: null,
}

/** Congela los atributos de mercado que F-042 necesita para exportar — puro, whitelist explícita
 *  (GWT-4). Un ticker que no cruza contra ningún universo (fuera del universo, o FCI) queda con
 *  todo `null`: es dato ausente, no se completa por analogía (regla 1). */
export function armarMercadoCongelado(entrada: EntradaMercado): MercadoCongelado {
  const especies: EspecieCongelada[] = entrada.tickers.map((ticker) => {
    const rf = entrada.porTickerRentaFija.get(ticker)
    if (rf) {
      return {
        ticker,
        clase_activo: rf.clase_activo,
        segmento: rf.segmento,
        naturaleza: rf.naturaleza,
        naturaleza_nombre: rf.naturaleza_nombre,
        rendimiento: rf.rendimiento,
        duracion: rf.duracion,
        vencimiento: rf.vencimiento,
        ley: rf.ley,
        emisor: rf.emisor,
        lamina: rf.lamina,
        calificacion: rf.calificacion,
        sector: rf.sector,
        moneda_cupon: rf.moneda_cupon,
        denominacion: null,
      }
    }
    const rv = entrada.porTickerRentaVariable?.get(ticker)
    if (rv) {
      return { ticker, ...ESPECIE_VACIA, denominacion: rv.nombre_largo }
    }
    // FCI (no cotiza, sin especie por construcción) o ticker fuera de los dos universos.
    return { ticker, ...ESPECIE_VACIA, denominacion: null }
  })

  return {
    especies,
    vector: entrada.vector,
    perfilConcentracion: entrada.perfilConcentracion,
    calendario: entrada.calendario
      ? {
          meses: entrada.calendario.meses.map((mes) => ({
            anio: mes.anio,
            mes: mes.mes,
            etiqueta: mes.etiqueta,
            nombre: mes.nombre,
            renta: mes.renta,
            amortizacion: mes.amortizacion,
            instrumentos: mes.instrumentos.map((i) => ({
              ticker: i.ticker,
              moneda: i.moneda,
              fechas: i.fechas,
              renta: i.renta,
              amortizacion: i.amortizacion,
            })),
          })),
          rentaAnual: entrada.calendario.resumen.renta_anual,
          amortizacionAnual: entrada.calendario.resumen.amortizacion_anual,
        }
      : null,
    fuenteDelDato: entrada.estadoDelDato
      ? {
          capturadoEn: entrada.estadoDelDato.dato.capturado_en,
          demoraMinutos: entrada.estadoDelDato.dato.demora.minutos,
          demoraFuente: entrada.estadoDelDato.dato.demora.fuente,
        }
      : null,
  }
}

export function armarSnapshotCargada(
  posiciones: readonly PosicionCruda[],
  valuacion: CarteraValuada,
  porTicker: ReadonlyMap<string, EspecieConMonedaYPrecio>,
  perfil: NombreDePerfil,
  plan: { aceptadas: readonly Candidata[]; descartadas: readonly string[] },
  tipoDeCambio: number | null,
  mercado: MercadoCongelado | null = null,
): SnapshotCargada {
  return {
    version: 1,
    origen: 'cargada',
    tipoDeCambio,
    perfil,
    posiciones: posiciones.map((p) => ({
      id: p.id,
      fila: p.fila,
      tickerDeclarado: p.tickerDeclarado,
      nominal: p.nominal,
      monto: p.monto,
      valida: p.valida,
      motivo: p.motivo,
    })),
    valuadas: valuacion.valuadas.map((v: PosicionValuada) => ({
      ticker: v.ticker,
      moneda: monedaNormalizada(porTicker.get(v.ticker)?.moneda_cotizacion),
      invertido: v.invertido,
      invertidoUsd: v.invertidoUsd,
      pesoReal: v.pesoReal,
    })),
    excluidas: valuacion.excluidas.map((e: PosicionExcluidaValuacion) => ({
      id: e.id,
      motivo: e.motivo,
      montoDeclarado: e.montoDeclarado,
    })),
    totalInvertidoUsd: valuacion.totalInvertidoUsd,
    plan: {
      aceptadas: plan.aceptadas.map((c) => ({ ...c })),
      descartadas: [...plan.descartadas],
    },
    mercado: mercado ?? undefined,
  }
}

export function armarSnapshotArmador(
  pos: readonly PosicionArmador[],
  resueltasRentaFija: readonly PosicionResuelta[],
  porTickerRentaFija: ReadonlyMap<string, EspecieConMonedaYPrecio>,
  resueltasRentaVariable: readonly PosicionRvResuelta[],
  porTickerRentaVariable: ReadonlyMap<string, EspecieConMonedaYPrecio>,
  tipoDeCambio: number | null,
  montoTotalUsd: number,
  mercado: MercadoCongelado | null = null,
): SnapshotArmador {
  const resueltaRfPorTicker = new Map(resueltasRentaFija.map((r) => [r.ticker, r]))
  const resueltaRvPorTicker = new Map(resueltasRentaVariable.map((r) => [r.ticker, r]))

  const resueltas: ResueltaGuardada[] = pos.map((p) => {
    if (p.clase === 'renta_variable') {
      const r = resueltaRvPorTicker.get(p.ticker)
      const especie = porTickerRentaVariable.get(p.ticker)
      return {
        ticker: p.ticker,
        clase: p.clase as ClasePosicion,
        peso: p.peso,
        moneda: monedaNormalizada(especie?.moneda_cotizacion),
        precio: especie?.precio ?? null,
        vn: null,
        cantidad: r?.cantidad ?? null,
        invertido: r?.invertido ?? null,
        invertidoUsd: r?.invertidoUsd ?? null,
      }
    }

    const r = resueltaRfPorTicker.get(p.ticker)
    // Un FCI no tiene especie en el universo (no cotiza): sin precio ni moneda por construcción,
    // no porque falte el dato (GWT-4 de F-018, ya vigente en `useCarteraResuelta`).
    const especie = p.clase === 'fci' ? undefined : porTickerRentaFija.get(p.ticker)
    return {
      ticker: p.ticker,
      clase: p.clase,
      peso: p.peso,
      moneda: monedaNormalizada(especie?.moneda_cotizacion),
      precio: especie?.precio ?? null,
      vn: r?.vn ?? null,
      cantidad: null,
      invertido: r?.invertido ?? null,
      invertidoUsd: r?.invertidoUsd ?? null,
    }
  })

  const totalInvertidoUsd = resueltas.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)

  return {
    version: 1,
    origen: 'armador',
    tipoDeCambio,
    montoTotalUsd,
    posiciones: pos.map((p) => ({ ticker: p.ticker, peso: p.peso, clase: p.clase })),
    resueltas,
    totalInvertidoUsd,
    mercado: mercado ?? undefined,
  }
}

function plural(n: number, singular: string, pluralForma: string): string {
  return n === 1 ? singular : pluralForma
}

/** La línea de una fila del listado (columna "Resumen"). Se calcula sólo desde el snapshot —
 *  nunca vuelve a consultar el mercado — así que es idéntica antes y después de revaluar. */
export function resumenDeCartera(snapshot: SnapshotCartera): string {
  if (snapshot.origen === 'cargada') {
    const partes = [`${snapshot.valuadas.length} ${plural(snapshot.valuadas.length, 'posición', 'posiciones')}`]
    if (snapshot.excluidas.length > 0) partes.push(`${snapshot.excluidas.length} sin valuar`)
    if (snapshot.plan.aceptadas.length > 0) {
      partes.push(
        `${snapshot.plan.aceptadas.length} ${plural(snapshot.plan.aceptadas.length, 'rotación aceptada', 'rotaciones aceptadas')}`,
      )
    }
    return partes.join(' · ')
  }

  const porClase = { renta_fija: 0, renta_variable: 0, fci: 0 }
  for (const p of snapshot.posiciones) porClase[p.clase] += 1

  const partes = [
    `${snapshot.posiciones.length} ${plural(snapshot.posiciones.length, 'posición', 'posiciones')}`,
  ]
  if (porClase.renta_fija > 0) partes.push(`${porClase.renta_fija} renta fija`)
  if (porClase.renta_variable > 0) partes.push(`${porClase.renta_variable} renta variable`)
  if (porClase.fci > 0) partes.push(`${porClase.fci} FCI`)
  return partes.join(' · ')
}

export function montoDeCartera(snapshot: SnapshotCartera): number {
  return snapshot.totalInvertidoUsd
}
