/**
 * Lógica pura de los filtros de la grilla — F-017 (A7).
 *
 * Portada del patrón de `frontend/src/features/monitor/components/FiltrosNumericos.tsx` (F-038):
 * portada y no importada, porque `features/monitor/**` está prohibido para el armador (mismo
 * precedente formal que ya documentan `armador/lib/schema.ts` y `armador/lib/especies.ts` — lo
 * del monitor se redefine acá, no se importa). El criterio de "campo null contra filtro activo no
 * pasa, sin filtro se muestra igual" es el mismo de `pasaFiltros` del monitor, con el mismo
 * porqué: no se puede afirmar que un dato que no existe cumple un umbral (regla 1 del dominio).
 *
 * Nota histórica: al arrancar esta feature, `esquemaEspecie` (`../lib/schema.ts`) todavía no traía
 * `sector` — lo agrega F-024 en paralelo, y se reportó como bloqueo al orquestador antes de escribir
 * el filtro correspondiente (Parte 0 del plan). Aterrizó mientras esta feature seguía en curso; el
 * filtro de sector de abajo ya lo evalúa contra el campo real, mismo trato que sector/emisor/ley:
 * `null` = "sin dato", nunca se le asigna un sector por parecido con otra especie.
 */

import type { Especie, InstrumentoDelMes, MesDelCalendario } from './schema'

export interface FiltrosArmador {
  /** null = todos los segmentos, con la unidad declarada por renglón (GWT-1). */
  segmento: string | null
  /** Input controlado en años; '' = sin filtro. */
  duracionMax: string
  /** Percentil mínimo de volumen_usd; '' = sin filtro. */
  liquidezMin: '' | '25' | '50' | '75'
  sector: string | null
  emisor: string | null
  /** Clave de ley del universo, o LEY_NO_INFORMADA. null = sin filtro. */
  ley: string | null
  /** Multiselect de valores literales de `calificacion` (texto libre de la calificadora, sin
   *  escala común — nunca se ordena por riesgo, sólo se filtra por coincidencia exacta), más
   *  CALIFICACION_NO_INFORMADA. Array vacío = sin filtro. */
  calificaciones: string[]
  /** Cantidad exacta de meses con pago de renta en la ventana; '' = sin filtro. */
  pagos: string
  /** TIR mínima, en puntos porcentuales ('6' = 6%); '' = sin filtro. Sólo se evalúa contra
   *  naturalezas de TIR (`NATURALEZAS_CON_TIR`) — el resto queda afuera mientras esté activo:
   *  no hay eje común para comparar una TIR contra una TNA o una tasa real (regla 2). */
  tirMin: string
  /** true = sólo instrumentos que pagan al menos un cupón en la ventana de 12 meses
   *  (`pct_renta > 0`); un bullet al descuento queda afuera. */
  soloConCupones: boolean
}

export const LEY_NO_INFORMADA = 'ley_no_informada'
export const CALIFICACION_NO_INFORMADA = 'calificacion_no_informada'

/** Las únicas naturalezas donde "TIR" es la unidad — ver `UNIDAD_NATURALEZA` en
 *  `@/components/SelectorSegmento`. `tasa_real_cer` y `tna_nominal_ars` no tienen TIR: con
 *  `tirMin` activo quedan afuera, no se comparan contra un umbral que no es su unidad. */
export const NATURALEZAS_CON_TIR = ['tir_usd', 'tir_dolar_linked'] as const

export const FILTROS_ARMADOR_VACIOS: FiltrosArmador = {
  segmento: null,
  duracionMax: '',
  liquidezMin: '',
  sector: null,
  emisor: null,
  ley: null,
  calificaciones: [],
  pagos: '',
  tirMin: '',
  soloConCupones: false,
}

/** El estado con el que arranca la pantalla (08/08/2026): sólo renta fija con TIR ≥ 6% y que
 *  pague cupones — la grilla sin filtro apila ~1.700 papeles uno abajo del otro en cada mes, la
 *  mayoría con TIR negativa o irrelevante. Separado de `FILTROS_ARMADOR_VACIOS` a propósito:
 *  "limpiar filtros" sigue significando ver todo, no volver a este default. */
export const FILTROS_ARMADOR_INICIALES: FiltrosArmador = {
  ...FILTROS_ARMADOR_VACIOS,
  tirMin: '6',
  soloConCupones: true,
}

export function hayFiltrosActivos(filtros: FiltrosArmador): boolean {
  return (
    filtros.segmento !== null ||
    filtros.duracionMax !== '' ||
    filtros.liquidezMin !== '' ||
    filtros.sector !== null ||
    filtros.emisor !== null ||
    filtros.ley !== null ||
    filtros.calificaciones.length > 0 ||
    filtros.pagos !== '' ||
    filtros.tirMin !== '' ||
    filtros.soloConCupones
  )
}

/**
 * Meses de la ventana (0–12) en que cada ticker paga renta: `pct_renta > 0`.
 *
 * Es la "frecuencia de cupón" de la ficha, pero no hay tal dato en ninguna fuente: se deriva del
 * propio calendario cargado, observado sobre la ventana de doce meses. No se traduce a "mensual /
 * trimestral / anual" — un ticker con un solo pago en la ventana no se declara "anual" porque la
 * ventana no alcanza para afirmarlo (regla 1: no inventar).
 */
export function contarPagosPorTicker(meses: MesDelCalendario[]): Map<string, number> {
  const conteo = new Map<string, number>()
  for (const mes of meses) {
    for (const instrumento of mes.instrumentos) {
      if (instrumento.pct_renta <= 0) continue
      conteo.set(instrumento.ticker, (conteo.get(instrumento.ticker) ?? 0) + 1)
    }
  }
  return conteo
}

/**
 * Tickers que pagan al menos un cupón en la ventana de doce meses (`pct_renta > 0` en algún mes).
 * Mismo criterio que `contarPagosPorTicker`, como conjunto en vez de conteo: para `soloConCupones`
 * alcanza con saber si paga, no cuántas veces. Un bullet al descuento (sin `pct_renta` en ningún
 * mes) no entra al conjunto.
 */
export function tickersConCupon(meses: MesDelCalendario[]): Set<string> {
  const tickers = new Set<string>()
  for (const mes of meses) {
    for (const instrumento of mes.instrumentos) {
      if (instrumento.pct_renta > 0) tickers.add(instrumento.ticker)
    }
  }
  return tickers
}

/**
 * Percentil (0–100] por ticker, por rango sobre `volumen_usd` — nunca sobre `volumen` crudo: el
 * crudo viene en la moneda de cotización de cada especie y compararlo entre monedas viola la
 * regla 3 del dominio. El conjunto se declara acá para que el llamador lo respete: son las
 * especies que se le pasan con `volumen_usd != null` — el llamador es responsable de restringir
 * esa lista a las especies del cruce (los tickers presentes en la grilla) antes de invocar esto.
 *
 * `percentil(t) = 100 * |{s : volumen_usd(s) <= volumen_usd(t)}| / |conjunto|`
 *
 * Una especie con `volumen_usd: null` queda fuera del conjunto y no tiene entrada en el mapa: no
 * se puede afirmar que un dato que no existe supera un percentil.
 */
export function percentilesDeLiquidez(especies: Especie[]): Map<string, number> {
  const conjunto = especies.filter(
    (especie): especie is Especie & { volumen_usd: number } => especie.volumen_usd !== null,
  )
  const valores = conjunto.map((especie) => especie.volumen_usd)

  const percentiles = new Map<string, number>()
  for (const especie of conjunto) {
    const menoresOIguales = valores.filter((valor) => valor <= especie.volumen_usd).length
    percentiles.set(especie.ticker, (100 * menoresOIguales) / conjunto.length)
  }
  return percentiles
}

function pasaFiltroPagos(pagos: number, filtroPagos: string): boolean {
  if (filtroPagos === '') return true
  return pagos === Number(filtroPagos)
}

/**
 * Si un instrumento pasa los filtros activos.
 *
 * `tirMin` y `soloConCupones` se evalúan primero y contra el instrumento del calendario
 * (`rendimiento`, `naturaleza`, `tieneCupon`), no contra el universo: valen igual para un ticker
 * sin cruce (misma razón que `pagos`).
 *
 * Ticker sin cruce (`especie: undefined`, está en la grilla pero no en el universo): no pasa
 * ningún filtro que dependa del universo (segmento, duración, liquidez, sector, emisor, ley); el
 * de pagos sí lo pasa, porque se deriva del calendario, no del universo.
 *
 * Campo null contra filtro activo: no pasa; sin ese filtro, se muestra (mismo criterio y mismo
 * porqué que `pasaFiltros` del monitor — ver docstring del módulo).
 */
export function pasaFiltros(
  dato: {
    especie: Especie | undefined
    pagos: number
    percentil: number | undefined
    rendimiento: number | null
    naturaleza: string
    tieneCupon: boolean
  },
  filtros: FiltrosArmador,
): boolean {
  const { especie } = dato

  if (filtros.tirMin !== '') {
    if (!(NATURALEZAS_CON_TIR as readonly string[]).includes(dato.naturaleza)) return false
    if (dato.rendimiento === null) return false
    if (dato.rendimiento < Number(filtros.tirMin) / 100) return false
  }

  if (filtros.soloConCupones && !dato.tieneCupon) return false

  const dependeDelUniverso =
    filtros.segmento !== null ||
    filtros.duracionMax !== '' ||
    filtros.liquidezMin !== '' ||
    filtros.sector !== null ||
    filtros.emisor !== null ||
    filtros.ley !== null ||
    filtros.calificaciones.length > 0

  if (especie === undefined) {
    if (dependeDelUniverso) return false
    return pasaFiltroPagos(dato.pagos, filtros.pagos)
  }

  if (filtros.segmento !== null && especie.segmento !== filtros.segmento) return false

  if (filtros.duracionMax !== '') {
    if (especie.duracion === null) return false
    if (especie.duracion > Number(filtros.duracionMax)) return false
  }

  if (filtros.liquidezMin !== '') {
    if (dato.percentil === undefined) return false
    if (dato.percentil < Number(filtros.liquidezMin)) return false
  }

  if (filtros.sector !== null && especie.sector !== filtros.sector) return false

  if (filtros.emisor !== null && especie.emisor !== filtros.emisor) return false

  if (filtros.ley !== null) {
    if (filtros.ley === LEY_NO_INFORMADA) {
      if (especie.ley !== null) return false
    } else if (especie.ley !== filtros.ley) {
      return false
    }
  }

  if (filtros.calificaciones.length > 0) {
    if (especie.calificacion === null) {
      if (!filtros.calificaciones.includes(CALIFICACION_NO_INFORMADA)) return false
    } else if (!filtros.calificaciones.includes(especie.calificacion)) {
      return false
    }
  }

  return pasaFiltroPagos(dato.pagos, filtros.pagos)
}

/**
 * Aplica `filtros` a los doce meses, cruzando cada instrumento contra `cruce` (el universo
 * restringido a los tickers de la ventana, `ticker -> Especie`).
 *
 * Reconstruye cada mes con los instrumentos sobrevivientes y recalcula `con_renta` y
 * `con_amortizacion` sobre ese subconjunto, pero **no toca `sin_renta`**: ese flag describe el
 * universo ("nadie paga este mes"), no el filtro, y pisarlo haría mentir el rótulo "sin pagos en
 * el universo" de la columna (`GrillaDoceMesos` lo lee tal cual).
 *
 * `total`/`visibles`/`sinCruce` cuentan tickers distintos de la ventana, no filas: un ticker que
 * paga en tres meses cuenta una sola vez.
 */
export function filtrarMeses(
  meses: MesDelCalendario[],
  cruce: Map<string, Especie>,
  filtros: FiltrosArmador,
): { meses: MesDelCalendario[]; total: number; visibles: number; sinCruce: number } {
  const pagosPorTicker = contarPagosPorTicker(meses)
  const percentiles = percentilesDeLiquidez([...cruce.values()])
  const cuponPorTicker = tickersConCupon(meses)

  const tickersVentana = new Set<string>()
  const tickersSinCruce = new Set<string>()
  const tickersVisibles = new Set<string>()

  const mesesFiltrados = meses.map((mesActual) => {
    const instrumentos = mesActual.instrumentos.filter((instrumento: InstrumentoDelMes) => {
      tickersVentana.add(instrumento.ticker)
      const especie = cruce.get(instrumento.ticker)
      if (especie === undefined) tickersSinCruce.add(instrumento.ticker)

      const pasa = pasaFiltros(
        {
          especie,
          pagos: pagosPorTicker.get(instrumento.ticker) ?? 0,
          percentil: percentiles.get(instrumento.ticker),
          rendimiento: instrumento.rendimiento,
          naturaleza: instrumento.naturaleza,
          tieneCupon: cuponPorTicker.has(instrumento.ticker),
        },
        filtros,
      )
      if (pasa) tickersVisibles.add(instrumento.ticker)
      return pasa
    })

    return {
      ...mesActual,
      instrumentos,
      con_renta: instrumentos.filter((i) => i.pct_renta > 0).length,
      con_amortizacion: instrumentos.filter((i) => i.pct_amortizacion > 0).length,
    }
  })

  return {
    meses: mesesFiltrados,
    total: tickersVentana.size,
    visibles: tickersVisibles.size,
    sinCruce: tickersSinCruce.size,
  }
}
