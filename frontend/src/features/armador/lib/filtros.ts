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

import { facetar, type Faceta } from '@/lib/facetado'

import type { Especie, InstrumentoDelMes, MesDelCalendario } from './schema'

export interface FiltrosArmador {
  /** null = todos los segmentos, con la unidad declarada por renglón (GWT-1). */
  segmento: string | null
  /** Input controlado en años; '' = sin filtro. */
  duracionMax: string
  /** Plazo máximo, en años hasta el vencimiento; '' = sin filtro.
   *
   *  **No reemplaza a `duracionMax`, lo complementa**, porque miden cosas distintas: la duración
   *  es sensibilidad al precio y pesa los cupones intermedios, mientras que el plazo es la fecha
   *  en que el asesor recupera el capital. Un amortizing a 2038 con cupones grandes tiene
   *  duración corta y plazo largo, y un cliente que dice "no quiero nada más allá de 5 años"
   *  está hablando del segundo. */
  vencimientoMax: string
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
  /** Periodicidades de cupón aceptadas, como valores literales de `especie.periodicidad`
   *  (`'mensual'`, `'trimestral'`, `'semestral'`…). Array vacío = sin filtro.
   *
   *  Multiselect y no un valor único porque "quiero cobrar seguido" no es una sola frecuencia:
   *  mensual y trimestral sirven los dos, y obligar a elegir una escondería la mitad de la oferta.
   *
   *  Distinto de `pagos`, que cuenta meses con pago dentro de la ventana de doce: esto es la
   *  frecuencia contractual de la emisión, medida sobre su cronograma entero. */
  periodicidades: string[]
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
 *  `tirMin` activo quedan afuera, no se comparan contra un umbral que no es su unidad.
 *
 *  `tir_ea_ars` entró en la Tanda 2 (26/08/2026): el segmento `tasa_fija` pasó a declarar su TIR
 *  efectiva anual, así que el umbral sí es su unidad y filtrarlo por `tirMin` es legítimo. Que el
 *  umbral cruce monedas —una TIR en dólares y una TIR en pesos contra el mismo 6 %— es lo que ya
 *  hacía con `tir_dolar_linked`: `tirMin` es un piso de descarte, no un eje de comparación, y el
 *  eje sigue separado por naturaleza en la columna y en la curva. */
export const NATURALEZAS_CON_TIR = ['tir_usd', 'tir_dolar_linked', 'tir_ea_ars'] as const

export const FILTROS_ARMADOR_VACIOS: FiltrosArmador = {
  segmento: null,
  duracionMax: '',
  vencimientoMax: '',
  liquidezMin: '',
  sector: null,
  emisor: null,
  ley: null,
  calificaciones: [],
  pagos: '',
  periodicidades: [],
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
    filtros.vencimientoMax !== '' ||
    filtros.liquidezMin !== '' ||
    filtros.sector !== null ||
    filtros.emisor !== null ||
    filtros.ley !== null ||
    filtros.calificaciones.length > 0 ||
    filtros.pagos !== '' ||
    filtros.periodicidades.length > 0 ||
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

/** Días de un año, para pasar de la diferencia de fechas a años. 365,25 y no 365: sobre plazos de
 *  diez años los bisiestos ya corren la cuenta más de un mes. */
const DIAS_POR_ANIO = 365.25

/**
 * Años que faltan hasta el vencimiento. `null` cuando la especie no declara vencimiento o cuando
 * la fecha no se puede leer: no se supone un plazo (regla 1), la especie queda fuera del filtro.
 *
 * Un vencimiento ya pasado da negativo, y eso pasa cualquier tope: es correcto — si sigue en el
 * universo con fecha vencida, el problema es del dato, no del filtro, y taparlo acá lo escondería.
 */
export function aniosHastaVencimiento(vencimiento: string | null, hoy: Date): number | null {
  if (vencimiento === null) return null
  const fecha = new Date(vencimiento)
  if (Number.isNaN(fecha.getTime())) return null
  return (fecha.getTime() - hoy.getTime()) / (DIAS_POR_ANIO * 24 * 60 * 60 * 1000)
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
  /** Contra qué fecha se mide el plazo. Parámetro y no `new Date()` adentro para que el filtro
   *  siga siendo determinístico y testeable — mismo criterio que el reloj afuera del armado del
   *  universo en el backend. */
  hoy: Date = new Date(),
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
    filtros.vencimientoMax !== '' ||
    filtros.liquidezMin !== '' ||
    filtros.sector !== null ||
    filtros.emisor !== null ||
    filtros.ley !== null ||
    filtros.calificaciones.length > 0 ||
    filtros.periodicidades.length > 0

  if (especie === undefined) {
    if (dependeDelUniverso) return false
    return pasaFiltroPagos(dato.pagos, filtros.pagos)
  }

  if (filtros.segmento !== null && especie.segmento !== filtros.segmento) return false

  if (filtros.duracionMax !== '') {
    if (especie.duracion === null) return false
    if (especie.duracion > Number(filtros.duracionMax)) return false
  }

  if (filtros.vencimientoMax !== '') {
    const anios = aniosHastaVencimiento(especie.vencimiento, hoy)
    if (anios === null) return false
    if (anios > Number(filtros.vencimientoMax)) return false
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

  if (filtros.periodicidades.length > 0) {
    // Sin cronograma no se puede afirmar que cumple una frecuencia: queda afuera del filtro
    // activo, igual que cualquier otro campo nulo (regla 1).
    if (especie.periodicidad === null) return false
    if (!filtros.periodicidades.includes(especie.periodicidad)) return false
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

/** Lo que hay que calcular una sola vez sobre la ventana entera para poder evaluar `pasaFiltros`:
 *  los tres derivados del calendario y del cruce que no dependen de los filtros. */
function insumosDeLaVentana(meses: MesDelCalendario[], cruce: Map<string, Especie>) {
  return {
    pagosPorTicker: contarPagosPorTicker(meses),
    percentiles: percentilesDeLiquidez([...cruce.values()]),
    cuponPorTicker: tickersConCupon(meses),
  }
}

/** El dato que `pasaFiltros` evalúa, ya armado, con el ticker al lado. */
export interface DatoDeTicker {
  ticker: string
  especie: Especie | undefined
  pagos: number
  percentil: number | undefined
  rendimiento: number | null
  naturaleza: string
  tieneCupon: boolean
}

/**
 * Un `DatoDeTicker` por ticker distinto de la ventana, para poder evaluar los filtros sobre el
 * conjunto sin recorrer los doce meses cada vez.
 *
 * `rendimiento` y `naturaleza` salen de la primera aparición del ticker en la ventana: son
 * atributos de la emisión que el calendario repite igual en cada mes, no cifras del mes. Todo lo
 * demás ya es por ticker. Por eso un ticker entra o sale entero, y contar tickers acá da lo mismo
 * que el `visibles` de `filtrarMeses`, que también cuenta tickers distintos.
 */
export function datosPorTicker(
  meses: MesDelCalendario[],
  cruce: Map<string, Especie>,
): DatoDeTicker[] {
  const { pagosPorTicker, percentiles, cuponPorTicker } = insumosDeLaVentana(meses, cruce)
  const datos = new Map<string, DatoDeTicker>()
  for (const mes of meses) {
    for (const instrumento of mes.instrumentos) {
      if (datos.has(instrumento.ticker)) continue
      datos.set(instrumento.ticker, {
        ticker: instrumento.ticker,
        especie: cruce.get(instrumento.ticker),
        pagos: pagosPorTicker.get(instrumento.ticker) ?? 0,
        percentil: percentiles.get(instrumento.ticker),
        rendimiento: instrumento.rendimiento,
        naturaleza: instrumento.naturaleza,
        tieneCupon: cuponPorTicker.has(instrumento.ticker),
      })
    }
  }
  return [...datos.values()]
}

/** Las opciones que la barra ofrece en cada dimensión discreta, ya acotadas por el facetado. */
export interface OpcionesFacetadas {
  sectores: string[]
  emisores: string[]
  leyes: string[]
  /** true si alguna especie que pasa el resto de los filtros tiene `ley: null` — habilita la
   *  opción "ley no informada". */
  tieneLeyNoInformada: boolean
  /** Valores literales distintos, ordenados alfabéticamente: orden de presentación, nunca de
   *  riesgo (cuatro calificadoras con escalas que no se equivalen). */
  calificaciones: string[]
  tieneCalificacionNoInformada: boolean
  pagos: number[]
}

export const OPCIONES_FACETADAS_VACIAS: OpcionesFacetadas = {
  sectores: [],
  emisores: [],
  leyes: [],
  tieneLeyNoInformada: false,
  calificaciones: [],
  tieneCalificacionNoInformada: false,
  pagos: [],
}

/** Las dimensiones que el facetado acota. El resto de `FiltrosArmador` son fuentes que siempre
 *  aplican: los umbrales (`tirMin`, `duracionMax`, `vencimientoMax`, `liquidezMin`,
 *  `soloConCupones`), `periodicidades` —cuyo control vive en el panel de armado asistido, no en
 *  esta barra— y `segmento`, porque la pestaña apretada es una elección explícita y visible:
 *  esconder su efecto sería mentir sobre lo que se está mirando. */
export type DimensionFacetada = 'sector' | 'emisor' | 'ley' | 'calificaciones' | 'pagos'

/** Una selección que el facetado apagó, para poder declararla en pantalla. Apagar en silencio
 *  mostraría la ventana entera con el filtro puesto y el asesor leería esos papeles como si
 *  cumplieran el criterio elegido: el faltante se declara, no se tapa (regla 11). */
export interface SeleccionApagada {
  dimension: DimensionFacetada
  valor: string
}

/**
 * Los filtros que siempre aplican, sin importar el facetado: los umbrales, `soloConCupones` y
 * `periodicidades` (su control vive en el panel de armado asistido, no en esta barra, pero se
 * evalúa igual). No incluye las cinco dimensiones facetadas (`sector`/`emisor`/`ley`/
 * `calificaciones`/`pagos`) — esas las evalúa el motor genérico como `Faceta<DatoDeTicker>`.
 *
 * Cada chequeo lee `dato.especie` sin asumir nada cuando falta: un ticker sin ficha en el universo
 * (`especie: undefined`) no puede pasar un filtro que dependa del universo, sin necesidad de un
 * caso especial — simplemente el dato que haría falta no está (regla 1).
 */
function pasaBaseFiltros(dato: DatoDeTicker, filtros: FiltrosArmador, hoy: Date): boolean {
  const { especie } = dato

  if (filtros.tirMin !== '') {
    if (!(NATURALEZAS_CON_TIR as readonly string[]).includes(dato.naturaleza)) return false
    if (dato.rendimiento === null) return false
    if (dato.rendimiento < Number(filtros.tirMin) / 100) return false
  }

  if (filtros.soloConCupones && !dato.tieneCupon) return false

  if (filtros.segmento !== null) {
    if (especie === undefined || especie.segmento !== filtros.segmento) return false
  }

  if (filtros.duracionMax !== '') {
    if (especie === undefined || especie.duracion === null) return false
    if (especie.duracion > Number(filtros.duracionMax)) return false
  }

  if (filtros.vencimientoMax !== '') {
    if (especie === undefined) return false
    const anios = aniosHastaVencimiento(especie.vencimiento, hoy)
    if (anios === null) return false
    if (anios > Number(filtros.vencimientoMax)) return false
  }

  if (filtros.liquidezMin !== '') {
    if (dato.percentil === undefined) return false
    if (dato.percentil < Number(filtros.liquidezMin)) return false
  }

  if (filtros.periodicidades.length > 0) {
    if (especie === undefined || especie.periodicidad === null) return false
    if (!filtros.periodicidades.includes(especie.periodicidad)) return false
  }

  return true
}

/** Las cinco dimensiones facetadas, como `Faceta<DatoDeTicker>` para el motor genérico
 *  (`@/lib/facetado`). El orden del array **es** el orden de validación: de lo general a lo
 *  específico, el mismo orden en que están puestas en la barra. */
function facetasDeArmador(filtros: FiltrosArmador): Array<Faceta<DatoDeTicker>> {
  return [
    {
      id: 'ley',
      seleccion: filtros.ley === null ? [] : [filtros.ley],
      coincide: (dato, valor) => {
        if (dato.especie === undefined) return false
        if (valor === LEY_NO_INFORMADA) return dato.especie.ley === null
        return dato.especie.ley === valor
      },
      valores: (dato) => (dato.especie === undefined ? [] : [dato.especie.ley ?? LEY_NO_INFORMADA]),
    },
    {
      id: 'sector',
      seleccion: filtros.sector === null ? [] : [filtros.sector],
      coincide: (dato, valor) => dato.especie !== undefined && dato.especie.sector === valor,
      valores: (dato) => (dato.especie?.sector != null ? [dato.especie.sector] : []),
    },
    {
      id: 'calificaciones',
      seleccion: filtros.calificaciones,
      coincide: (dato, valor) => {
        if (dato.especie === undefined) return false
        if (valor === CALIFICACION_NO_INFORMADA) return dato.especie.calificacion === null
        return dato.especie.calificacion === valor
      },
      valores: (dato) =>
        dato.especie === undefined ? [] : [dato.especie.calificacion ?? CALIFICACION_NO_INFORMADA],
    },
    {
      id: 'pagos',
      // Se evalúa igual con o sin ficha en el universo: sale del calendario, no del cruce (mismo
      // criterio que `pasaFiltros` de siempre).
      seleccion: filtros.pagos === '' ? [] : [filtros.pagos],
      coincide: (dato, valor) => dato.pagos === Number(valor),
      valores: (dato) => [String(dato.pagos)],
    },
    {
      id: 'emisor',
      seleccion: filtros.emisor === null ? [] : [filtros.emisor],
      coincide: (dato, valor) => dato.especie !== undefined && dato.especie.emisor === valor,
      valores: (dato) => (dato.especie?.emisor != null ? [dato.especie.emisor] : []),
    },
  ]
}

/**
 * Facetado en cascada de la barra de la cordillera (14/08/2026), sobre el motor genérico de
 * `@/lib/facetado` — ver ese módulo para la semántica completa (validación por orden, opciones
 * leave-one-out, selecciones sin respaldo declaradas). Acá sólo se arman los descriptores por
 * dimensión y se traduce el resultado genérico a la forma que ya conoce la barra.
 */
export function facetarFiltros(
  meses: MesDelCalendario[],
  cruce: Map<string, Especie>,
  filtros: FiltrosArmador,
  hoy: Date = new Date(),
): {
  opciones: OpcionesFacetadas
  efectivos: FiltrosArmador
  apagadas: SeleccionApagada[]
} {
  const datos = datosPorTicker(meses, cruce)
  const resultado = facetar(datos, facetasDeArmador(filtros), (dato) =>
    pasaBaseFiltros(dato, filtros, hoy),
  )

  const leyes = resultado.opciones.get('ley') ?? []
  const calificaciones = resultado.opciones.get('calificaciones') ?? []

  const opciones: OpcionesFacetadas = {
    sectores: resultado.opciones.get('sector') ?? [],
    emisores: resultado.opciones.get('emisor') ?? [],
    leyes: leyes.filter((valor) => valor !== LEY_NO_INFORMADA),
    tieneLeyNoInformada: leyes.includes(LEY_NO_INFORMADA),
    calificaciones: calificaciones.filter((valor) => valor !== CALIFICACION_NO_INFORMADA).sort(),
    tieneCalificacionNoInformada: calificaciones.includes(CALIFICACION_NO_INFORMADA),
    pagos: (resultado.opciones.get('pagos') ?? []).map(Number),
  }

  const efectivos: FiltrosArmador = {
    ...filtros,
    sector: resultado.efectivas.get('sector')?.[0] ?? null,
    emisor: resultado.efectivas.get('emisor')?.[0] ?? null,
    ley: resultado.efectivas.get('ley')?.[0] ?? null,
    calificaciones: resultado.efectivas.get('calificaciones') ?? [],
    pagos: resultado.efectivas.get('pagos')?.[0] ?? '',
  }

  return {
    opciones,
    efectivos,
    apagadas: resultado.apagadas.map(({ dimension, valor }) => ({
      dimension: dimension as DimensionFacetada,
      valor,
    })),
  }
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
  const { pagosPorTicker, percentiles, cuponPorTicker } = insumosDeLaVentana(meses, cruce)

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
