/**
 * Los filtros de los fondos comunes de inversión — 23/08/2026.
 *
 * Port de `./filtros.ts` (el universo de renta fija) sobre el mismo motor genérico de
 * `@/lib/facetado`: mismas convenciones —vacío significa "sin filtro", campo `null` contra filtro
 * activo no pasa, selección sin respaldo se declara en vez de envenenar al resto— sobre los ejes
 * que la planilla de CAFCI sí publica.
 *
 * **Qué no hay acá y por qué.** No hay "rubro": CAFCI no lo publica por fondo, y la columna
 * "Código de Clasificación" del XLSX no se ingiere. Los ejes categóricos son los seis que la fuente
 * declara — sección, tipo de dinero, región, horizonte, calificación y sociedad gerente — más el
 * chip de moneda. Tampoco hay variación semanal ni semestral: la planilla publica cuatro (día, mes,
 * año calendario y 12 meses) y no se pueden derivar otras, porque cada corrida pisa la planilla
 * entera y no queda serie histórica.
 *
 * **Nada se normaliza** (regla 11): `Cor`/`Lar`/`Flex` son códigos propietarios de CAFCI y se
 * comparan y muestran verbatim; `"NA"` y `"N/A"` son dos calificaciones distintas porque la fuente
 * las escribe distinto; `"Gainvest S.A."` y `"GAINVEST SA"` son dos gestoras distintas (mismo
 * contrato que fija `backend/app/fci/agregados.py`).
 */

import { SIN_MONEDA_DECLARADA } from '@/components/SelectorMoneda'
import { facetar, type Faceta } from '@/lib/facetado'
import type { FondoFci } from '@/lib/fci'

import { CALIFICACION_NO_INFORMADA } from './filtros'

export { CALIFICACION_NO_INFORMADA }

export interface FiltrosFci {
  /** `moneda` del fondo (o `SIN_MONEDA_DECLARADA`), o `null` = sin elegir a mano. `null` **no**
   *  significa "todas mezcladas": eso violaría la regla 3 del dominio. Antes de filtrar la tabla se
   *  resuelve a una concreta con `monedaInicial` — ver `MonitorPage.tsx`. */
  moneda: string | null
  /** Título literal de la sección de la planilla ("Renta Variable Peso Argentina"). Es el único
   *  categórico no nulable del dato, así que no lleva centinela. */
  seccion: string | null
  tipoDinero: string | null
  region: string | null
  horizonte: string | null
  /** Multiselect de valores literales de `calificacion`, más CALIFICACION_NO_INFORMADA. Array
   *  vacío = sin filtro. Sin orden ni escala común: son cuatro calificadoras distintas. */
  calificaciones: string[]
  gerente: string | null

  varDiariaMin: string
  varDiariaMax: string
  varMesMin: string
  varMesMax: string
  varAnioMin: string
  varAnioMax: string
  var12mMin: string
  var12mMax: string
}

export const FILTROS_FCI_VACIOS: FiltrosFci = {
  moneda: null,
  seccion: null,
  tipoDinero: null,
  region: null,
  horizonte: null,
  calificaciones: [],
  gerente: null,
  varDiariaMin: '',
  varDiariaMax: '',
  varMesMin: '',
  varMesMax: '',
  varAnioMin: '',
  varAnioMax: '',
  var12mMin: '',
  var12mMax: '',
}

export const GERENTE_NO_INFORMADA = 'gerente_no_informada'
export const REGION_NO_INFORMADA = 'region_no_informada'
export const HORIZONTE_NO_INFORMADO = 'horizonte_no_informado'
export const TIPO_DINERO_NO_INFORMADO = 'tipo_dinero_no_informado'

/** Los cuatro rangos, contra el campo de variación que le corresponde a cada uno. */
const RANGOS: Array<{
  min: keyof FiltrosFci
  max: keyof FiltrosFci
  valor: (fondo: FondoFci) => number | null
}> = [
  { min: 'varDiariaMin', max: 'varDiariaMax', valor: (f) => f.var_diaria_pct },
  { min: 'varMesMin', max: 'varMesMax', valor: (f) => f.var_mes_pct },
  { min: 'varAnioMin', max: 'varAnioMax', valor: (f) => f.var_anio_pct },
  { min: 'var12mMin', max: 'var12mMax', valor: (f) => f.var_12m_pct },
]

/**
 * Los cuatro rangos de variación: la parte de siempre, ajena al facetado. Un fondo con la variación
 * en `null` no puede pasar un rango activo —no se puede afirmar que un dato que no existe cumple un
 * umbral— pero sin ese rango se muestra igual.
 *
 * **Unidad: se compara directo, sin dividir por 100.** Las `var_*_pct` de CAFCI ya vienen en puntos
 * porcentuales (`0.67` es 0,67 %, y la tabla las imprime con `fmtPct` sin transformarlas), así que
 * el input rotulado "(%)" y el dato están en la misma unidad. Es el contraste exacto con
 * `pasaFiltrosNumericos` de `./filtros.ts`, que sí divide porque `especie.rendimiento` es fracción.
 */
export function pasaFiltrosNumericosFci(fondo: FondoFci, filtros: FiltrosFci): boolean {
  for (const rango of RANGOS) {
    const crudoMin = filtros[rango.min] as string
    const crudoMax = filtros[rango.max] as string
    const min = crudoMin === '' ? null : Number(crudoMin)
    const max = crudoMax === '' ? null : Number(crudoMax)
    if (min === null && max === null) continue

    const valor = rango.valor(fondo)
    if (valor === null) return false
    if (min !== null && valor < min) return false
    if (max !== null && valor > max) return false
  }

  return true
}

/**
 * Si un fondo pasa todos los filtros activos, discretos y de rango.
 *
 * Campo null contra filtro activo: no pasa; sin ese filtro, se muestra igual (regla 1 del dominio,
 * mismo criterio que la barra del universo).
 */
export function pasaFiltrosFci(fondo: FondoFci, filtros: FiltrosFci): boolean {
  if (!pasaFiltrosNumericosFci(fondo, filtros)) return false

  if (filtros.moneda !== null) {
    if ((fondo.moneda ?? SIN_MONEDA_DECLARADA) !== filtros.moneda) return false
  }

  if (filtros.seccion !== null && fondo.seccion !== filtros.seccion) return false

  if (!pasaCentinela(fondo.tipo_dinero, filtros.tipoDinero, TIPO_DINERO_NO_INFORMADO)) return false
  if (!pasaCentinela(fondo.region, filtros.region, REGION_NO_INFORMADA)) return false
  if (!pasaCentinela(fondo.horizonte, filtros.horizonte, HORIZONTE_NO_INFORMADO)) return false

  if (filtros.calificaciones.length > 0) {
    if (fondo.calificacion === null) {
      if (!filtros.calificaciones.includes(CALIFICACION_NO_INFORMADA)) return false
    } else if (!filtros.calificaciones.includes(fondo.calificacion)) {
      return false
    }
  }

  if (!pasaCentinela(fondo.gerente, filtros.gerente, GERENTE_NO_INFORMADA)) return false

  return true
}

/** Un categórico nulable contra su filtro: el centinela selecciona exactamente los `null`. */
function pasaCentinela(dato: string | null, filtro: string | null, centinela: string): boolean {
  if (filtro === null) return true
  if (filtro === centinela) return dato === null
  return dato === filtro
}

/** Las siete dimensiones que el facetado acota. Los cuatro rangos quedan afuera: son fuentes que
 *  siempre aplican (`pasaFiltrosNumericosFci`), no un select que pueda quedar apagado. */
export type DimensionFacetadaFci =
  | 'moneda'
  | 'seccion'
  | 'tipoDinero'
  | 'region'
  | 'horizonte'
  | 'calificaciones'
  | 'gerente'

export interface SeleccionApagadaFci {
  dimension: DimensionFacetadaFci
  valor: string
}

/** Las opciones que la pantalla ofrece por dimensión, ya acotadas por el facetado. La moneda no
 *  está: su chip muestra conteos (no sólo una lista de valores) y se calcula aparte con
 *  `contarPorMoneda` sobre el subconjunto que deja el resto de los filtros — ver `MonitorPage.tsx`. */
export interface OpcionesFacetadasFci {
  secciones: string[]
  tiposDinero: string[]
  tieneTipoDineroNoInformado: boolean
  regiones: string[]
  tieneRegionNoInformada: boolean
  horizontes: string[]
  tieneHorizonteNoInformado: boolean
  calificaciones: string[]
  tieneCalificacionNoInformada: boolean
  gerentes: string[]
  tieneGerenteNoInformada: boolean
}

/** Las siete dimensiones, como `Faceta<FondoFci>` para el motor genérico. El orden del array **es**
 *  el orden de validación: moneda primero —el chip, el corte más grueso— y después sección → tipo de
 *  dinero → región → horizonte → calificación → gerente, de menor a mayor cardinalidad, el mismo
 *  criterio general→específico con que la barra del universo termina en emisor. */
function facetasDeFci(filtros: FiltrosFci): Array<Faceta<FondoFci>> {
  return [
    {
      id: 'moneda',
      seleccion: filtros.moneda === null ? [] : [filtros.moneda],
      coincide: (fondo, valor) => (fondo.moneda ?? SIN_MONEDA_DECLARADA) === valor,
      valores: (fondo) => [fondo.moneda ?? SIN_MONEDA_DECLARADA],
    },
    {
      id: 'seccion',
      seleccion: filtros.seccion === null ? [] : [filtros.seccion],
      coincide: (fondo, valor) => fondo.seccion === valor,
      valores: (fondo) => [fondo.seccion],
    },
    facetaConCentinela('tipoDinero', filtros.tipoDinero, TIPO_DINERO_NO_INFORMADO, (f) => f.tipo_dinero),
    facetaConCentinela('region', filtros.region, REGION_NO_INFORMADA, (f) => f.region),
    facetaConCentinela('horizonte', filtros.horizonte, HORIZONTE_NO_INFORMADO, (f) => f.horizonte),
    {
      id: 'calificaciones',
      seleccion: filtros.calificaciones,
      coincide: (fondo, valor) =>
        valor === CALIFICACION_NO_INFORMADA
          ? fondo.calificacion === null
          : fondo.calificacion === valor,
      valores: (fondo) => [fondo.calificacion ?? CALIFICACION_NO_INFORMADA],
    },
    facetaConCentinela('gerente', filtros.gerente, GERENTE_NO_INFORMADA, (f) => f.gerente),
  ]
}

function facetaConCentinela(
  id: DimensionFacetadaFci,
  seleccionado: string | null,
  centinela: string,
  dato: (fondo: FondoFci) => string | null,
): Faceta<FondoFci> {
  return {
    id,
    seleccion: seleccionado === null ? [] : [seleccionado],
    coincide: (fondo, valor) => (valor === centinela ? dato(fondo) === null : dato(fondo) === valor),
    valores: (fondo) => [dato(fondo) ?? centinela],
  }
}

/**
 * Facetado en cascada de los FCI, sobre el motor genérico de `@/lib/facetado` — ver ese módulo para
 * la semántica completa (validación por orden, opciones leave-one-out, selecciones sin respaldo
 * declaradas).
 *
 * `efectivos.moneda` puede seguir en `null` a la salida —sin elegir a mano, o apagada por no tener
 * fondos bajo el resto de los filtros—: quien llama tiene que resolverla a una concreta con
 * `monedaInicial` antes de filtrar la tabla, nunca dejarla en `null` (regla 3).
 */
export function facetarFci(
  fondos: FondoFci[],
  filtros: FiltrosFci,
): {
  opciones: OpcionesFacetadasFci
  efectivos: FiltrosFci
  apagadas: SeleccionApagadaFci[]
} {
  const resultado = facetar(fondos, facetasDeFci(filtros), (fondo) =>
    pasaFiltrosNumericosFci(fondo, filtros),
  )

  const partir = (id: DimensionFacetadaFci, centinela: string) => {
    const valores = resultado.opciones.get(id) ?? []
    return {
      concretos: valores.filter((valor) => valor !== centinela).sort(),
      tieneNoInformado: valores.includes(centinela),
    }
  }

  const tiposDinero = partir('tipoDinero', TIPO_DINERO_NO_INFORMADO)
  const regiones = partir('region', REGION_NO_INFORMADA)
  const horizontes = partir('horizonte', HORIZONTE_NO_INFORMADO)
  const calificaciones = partir('calificaciones', CALIFICACION_NO_INFORMADA)
  const gerentes = partir('gerente', GERENTE_NO_INFORMADA)

  const opciones: OpcionesFacetadasFci = {
    secciones: (resultado.opciones.get('seccion') ?? []).sort(),
    tiposDinero: tiposDinero.concretos,
    tieneTipoDineroNoInformado: tiposDinero.tieneNoInformado,
    regiones: regiones.concretos,
    tieneRegionNoInformada: regiones.tieneNoInformado,
    horizontes: horizontes.concretos,
    tieneHorizonteNoInformado: horizontes.tieneNoInformado,
    calificaciones: calificaciones.concretos,
    tieneCalificacionNoInformada: calificaciones.tieneNoInformado,
    gerentes: gerentes.concretos,
    tieneGerenteNoInformada: gerentes.tieneNoInformado,
  }

  const efectivos: FiltrosFci = {
    ...filtros,
    moneda: resultado.efectivas.get('moneda')?.[0] ?? null,
    seccion: resultado.efectivas.get('seccion')?.[0] ?? null,
    tipoDinero: resultado.efectivas.get('tipoDinero')?.[0] ?? null,
    region: resultado.efectivas.get('region')?.[0] ?? null,
    horizonte: resultado.efectivas.get('horizonte')?.[0] ?? null,
    calificaciones: resultado.efectivas.get('calificaciones') ?? [],
    gerente: resultado.efectivas.get('gerente')?.[0] ?? null,
  }

  return {
    opciones,
    efectivos,
    apagadas: resultado.apagadas.map(({ dimension, valor }) => ({
      dimension: dimension as DimensionFacetadaFci,
      valor,
    })),
  }
}
