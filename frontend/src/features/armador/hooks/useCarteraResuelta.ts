/**
 * La cartera de renta fija resuelta a nominales y montos — base común de la Tanda 9.
 *
 * Sale de `CarteraEditable`, que era su único consumidor hasta que F-020 (concentración) y F-021
 * (panel de renta) necesitaron los mismos números. Extraerlo evita tres cosas: que cada panel
 * repita el pipeline, que los tres se desincronicen, y sobre todo que dos features distintas
 * tengan que editar el mismo archivo durante la ejecución en paralelo.
 *
 * **El filtro por clase vive acá adentro, y esa es la razón de ser del hook.** `resolver` hace
 * matemática de bonos —precio cada 100 VN, redondeo a lámina— y el calendario de cupones sólo
 * conoce renta fija: un ticker de renta variable que se colara devolvería nominales sin sentido y
 * caería en `fuera_del_universo` del calendario. Al partir de `posicionesRentaFija(pos)`, eso no
 * puede pasar por construcción, en vez de depender de que cada consumidor se acuerde de filtrar.
 * El bloque de renta variable se resuelve aparte, con su propia matemática de unidades enteras.
 *
 * Los consumidores comparten fetch sin coordinarse: `useEspeciesUniverso` y `useTipoDeCambio` están
 * cacheados por TanStack Query, y `posicionesParaCalendario` produce la misma firma de cartera en
 * los dos paneles, así que `useCalendarioCartera` deduplica en un solo POST.
 */

import { useMemo } from 'react'

import { useFondosFci, type FondoFci } from '@/lib/fci'

import { useEspeciesUniverso } from './useEspeciesUniverso'
import { useTipoDeCambio } from './useTipoDeCambio'
import type { Especie } from '../lib/schema'
import {
  resolver,
  resumenAjuste,
  type EntradaResolver,
  type PosicionResuelta,
  type ResumenAjuste,
} from '../lib/resolver'
import { posicionesRentaFija, useArmador } from '../store/carteraStore'

/** Una posición con monto invertido conocido y positivo: lo que el calendario puede valuar. */
export interface PosicionConMonto {
  ticker: string
  monto: number
}

export interface CarteraResuelta {
  /** Renta fija y FCI resueltos. La renta variable **no** está acá. */
  resueltas: PosicionResuelta[]
  /** Cuánto se pudo ajustar a lámina y cuánto no (F-024). */
  ajuste: ResumenAjuste
  /** Lo que se le manda a `POST /calendario/cartera`: sólo las que tienen monto. */
  posicionesParaCalendario: PosicionConMonto[]
  /** El universo indexado por ticker, para que el consumidor no vuelva a armar el mapa. */
  porTicker: Map<string, Especie>
  /** Tipo de cambio implícito vigente, o `null` si no se pudo derivar (F-012). */
  tipoDeCambio: number | null
  /** Suma de `invertidoUsd`, ignorando las que no se pudieron resolver. */
  totalInvertidoUsd: number
  /** `true` si al menos una posición se resolvió: distingue "cartera vacía" de "sin precio". */
  hayAlgunaResuelta: boolean
}

export function useCarteraResuelta(): CarteraResuelta {
  const { pos, montoTotal } = useArmador()

  const especies = useEspeciesUniverso()
  const tipoDeCambio = useTipoDeCambio()
  // `null` trae todos los fondos (F-046): la cartera puede tener FCI de cualquier tipo de renta, y
  // el hook no filtra por segmento — mismo criterio que el picker (F-057, `useFondosFci`).
  const fondosFci = useFondosFci(null)

  const porTicker = useMemo(() => {
    const mapa = new Map<string, Especie>()
    for (const especie of especies.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [especies.data])

  const porCodigoCafci = useMemo(() => {
    const mapa = new Map<string, FondoFci>()
    for (const fondo of fondosFci.data ?? []) mapa.set(fondo.codigo_cafci, fondo)
    return mapa
  }, [fondosFci.data])

  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const resueltas = useMemo(() => {
    const entradas: EntradaResolver[] = posicionesRentaFija(pos).map((p) => {
      const esFci = p.clase === 'fci'

      if (esFci) {
        // Sin `codigoCafci` (FCI legado, F-046) o con código pero sin fila en la planilla de hoy
        // (el fondo desapareció o todavía no se identificó): `fondo` da `undefined` en los dos
        // casos, y `resolver()` los declara sin resolver de la misma forma — nunca se inventa un
        // VCP ni se matchea por nombre (regla 1 y 11 del proyecto).
        const fondo = p.codigoCafci ? porCodigoCafci.get(p.codigoCafci) : undefined
        // `USB` y cualquier moneda que no sea ARS/USD viajan tal cual la declara CAFCI: `resolver`
        // decide si se puede convertir, acá no se traduce nada (regla 11).
        const monedaCotizacion = fondo?.moneda?.toLowerCase() ?? 'usd'
        return {
          ticker: p.ticker,
          peso: p.peso,
          precio: null,
          monedaCotizacion,
          lamina: null,
          esFci: true,
          vcpPorMil: fondo?.vcp ?? null,
          fechaVcp: fondo?.fecha_vcp ?? null,
        }
      }

      const especie = porTicker.get(p.ticker)
      // Normalizado a minúscula acá: `moneda_cotizacion` llega de BYMA en mayúsculas ("ARS"/"USD")
      // y `EntradaResolver` compara contra los literales en minúscula. Es casing, no negocio.
      const monedaCotizacion = especie?.moneda_cotizacion?.toLowerCase() ?? null
      // Sin moneda declarada no hay con qué decidir si conviene TC: se declara sin precio en vez
      // de asumir una moneda (regla 1 del proyecto), aunque la especie sí traiga un precio.
      const sinBase = monedaCotizacion === null
      return {
        ticker: p.ticker,
        peso: p.peso,
        precio: sinBase ? null : (especie?.precio ?? null),
        monedaCotizacion: monedaCotizacion ?? 'usd', // irrelevante: `resolver` no la usa con precio null
        // F-024: la lámina real, de condiciones_emision vía /especies. `null` = no informada: el
        // resolver no redondea y la fila lo declara. Jamás un default (regla 1 del proyecto).
        lamina: especie?.lamina ?? null,
        esFci: false,
        vcpPorMil: null,
        fechaVcp: null,
      }
    })
    return resolver(entradas, montoTotal, tcValor)
  }, [pos, porTicker, porCodigoCafci, montoTotal, tcValor])

  const ajuste = useMemo(() => resumenAjuste(resueltas), [resueltas])

  const posicionesParaCalendario = useMemo(
    () =>
      resueltas
        // Un FCI nunca tiene cronograma contractual (regla 5 del proyecto): se excluye por clase y
        // no por `invertido`, porque un FCI valuado sí tiene invertido y entraría igual si el
        // filtro fuera sólo "tiene monto" (F-046). Su monto se suma aparte —
        // `lib/cartera/porcionSinCronograma.ts`— y se declara como hueco, no se ignora en silencio.
        .filter(
          (r): r is PosicionResuelta & { invertido: number } =>
            !r.esFci && r.invertido !== null && r.invertido > 0,
        )
        .map((r) => ({ ticker: r.ticker, monto: r.invertido })),
    [resueltas],
  )

  const totalInvertidoUsd = resueltas.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)
  const hayAlgunaResuelta = resueltas.some((r) => r.invertidoUsd !== null)

  return {
    resueltas,
    ajuste,
    posicionesParaCalendario,
    porTicker,
    tipoDeCambio: tcValor,
    totalInvertidoUsd,
    hayAlgunaResuelta,
  }
}
