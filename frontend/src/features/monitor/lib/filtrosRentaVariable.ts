/**
 * Los filtros de la renta variable del monitor — F-078 (fase 2, 28/08/2026) reescrito por F-079
 * (fase 5, 29/08/2026).
 *
 * Espejo de `lib/filtros.ts` sobre el mismo motor genérico de `@/lib/facetado`: se **porta** la
 * lógica en vez de importarse entre features (precedente F-017/F-018/F-038), y lo genuinamente
 * compartido —el motor, los presets— vive en `lib/`. Lo que cambia respecto de la renta fija son
 * las dimensiones: acá no hay ley ni calificación ni naturaleza de tasa, hay ejes de
 * diversificación, que es lo que F-078 vino a resolver ("no sé en qué estoy invertido con tanto
 * activo") y F-079 vino a hacer buscable ("alguien sin idea de mercado tiene que poder escribir
 * 'oro' y encontrar los CEDEARs").
 *
 * ## Las seis dimensiones, en orden general → específico
 *
 * `region → pais → mercado → sector → rubroEspecifico → estrategiaEtf`. `rubro` (oficina SIC) y
 * `eslabon` (división SIC) de F-078 se van de acá: siguen existiendo en el dato
 * (`especie.sic_oficina`, `especie.division_cadena`) pero ya no son eje de filtro del monitor —
 * `sector` y `rubroEspecifico`, ambos derivados de `sic_codigo` con traducción ES curada
 * (`app/renta_variable/especies.py`), los reemplazan con más granularidad y con una etiqueta
 * pensada para que alguien sin jerga la lea. El orden **es** el orden de validación del facetado
 * (ver el docstring de `@/lib/facetado`): sector antes que rubroEspecifico porque el mismo
 * mecanismo de leave-one-out que encadenaba rubro⇄eslabón en F-078 encadena ahora sector→
 * rubroEspecifico — elegir un sector acota qué códigos SIC de 4 dígitos quedan como opción, sin que
 * este módulo tenga que resolver la jerarquía a mano.
 *
 * ## El valor de faceta es el código, la etiqueta es presentación (regla 11)
 *
 * `sector` factura sobre `sector_codigo` (el major group SIC de dos dígitos, `"73"`) y
 * `rubroEspecifico` sobre `sic_codigo` (cuatro dígitos) — **nunca** sobre `sector`/`rubro_especifico`
 * (las etiquetas ES). Si el curado de `data/sic_sectores.csv` cambiara mañana el texto de un
 * código, una selección guardada por texto se invalidaría sola; guardada por código, sigue
 * apuntando a lo mismo. `etiquetaDeValorRv` traduce el código a texto sólo para mostrarlo, con un
 * `Map` construido sobre el universo (mismo patrón que `formasCanonicasDeMercado`): sin etiqueta ES
 * cargada se muestra el título en inglés que publica la fuente pública correspondiente —
 * `sic_titulo` de la SEC para rubroEspecifico, `sector_titulo` del SIC Manual de OSHA para sector
 * (30/08/2026)— y sólo si tampoco existe ese título (los huecos del Manual) se cae al código
 * pelado. Nunca se inventa una traducción, y el `title` de la opción deja la fuente a la vista.
 *
 * ## El eje geográfico se unifica en país, sigue en cascada en región
 *
 * **País.** Con la geografía de ETFs curada en F-079/D3 (`etf_pais`, ISO 3166-1 alfa-2, mismo
 * vocabulario que `pais`), `especie.pais ?? especie.etf_pais` deja de ser una traducción: los dos
 * son curados en el mismo estándar, así que unificarlos es leer dos fuentes que hablan el mismo
 * idioma, no interpretar una a la otra. Son excluyentes en la práctica (una empresa tiene país y no
 * es fondo; un ETF mono-país es al revés), así que no hace falta ofrecer los dos como valores
 * separados de la faceta como sí seguía haciendo región.
 *
 * **Región.** `especie.region ?? especie.etf_region ?? especie.etf_alcance ?? especie.region_etf`,
 * en ese orden exacto:
 *
 * 1. `region` — la subregión M49 que deriva el backend del país curado de la empresa.
 * 2. `etf_region` — la misma subregión M49, pero derivada de `etf_pais` para un fondo mono-país
 *    curado (F-079/D3).
 * 3. `etf_alcance` — el alcance que el propio emisor del índice declara para un fondo multi-país
 *    curado, ya en español legible ("Mercados emergentes", no una subregión ONU).
 * 4. `region_etf` — el token crudo que la fuente escribe en el nombre del fondo ("EAFE", "Brazil"),
 *    **sin traducir**, y sólo como último recurso: es lo único que queda para un fondo que el
 *    curado todavía no alcanzó.
 *
 * A diferencia de F-078, esto ya no ofrece dos valores en simultáneo por especie: es una cascada de
 * un único valor, porque ahora hay hasta cuatro fuentes candidatas y sumarlas todas duplicaría el
 * papel en la faceta. Se prefiere siempre lo más curado (fuente con validación humana) sobre lo más
 * crudo (token tal cual lo escribió BYMA).
 *
 * ## El mercado se compara sin distinguir caja, pero los tiers de NASDAQ no se tocan
 *
 * Sin cambios respecto de F-078: se colapsan las variantes de mayúsculas del mismo mercado
 * (`"NYSE Arca"` / `"NYSE ARCA"`) porque son el mismo string escrito distinto, pero no los tiers de
 * NASDAQ (`GS`/`GM`/`CM`) porque la fuente los distingue a propósito. Ver `formasCanonicasDeMercado`.
 *
 * ## La búsqueda de texto es filtro base, no faceta
 *
 * `busqueda` entra a `pasaBaseRv` —como la moneda y el preset— para que los conteos de cada
 * `CampoSelect` reflejen el universo ya acotado por texto, y no al revés. Compara contra ticker,
 * nombre largo, la etiqueta ES de sector y de rubro específico (si la especie misma las trae
 * cargadas) y el título SIC en inglés, con acentos y mayúsculas normalizados (`foldTexto`).
 * `presetsQueCoinciden` es la mitad que encuentra un atajo temático a partir de la misma búsqueda:
 * matchea contra la etiqueta del preset y contra `palabrasEnNombre`, así que buscar "oro" encuentra
 * "Metales preciosos" porque el preset ya declara `'oro'` como una de sus palabras. No inventa
 * sinónimos: si el dueño quiere que "salud" encuentre "Medicina y salud", eso se agrega como
 * palabra al preset, no como mapa de sinónimos acá.
 *
 * ## La moneda no es faceta
 *
 * Sigue en `SelectorMoneda`, como filtro base (`pasaBase`). No es una dimensión que pueda quedar
 * apagada ni mostrarse "en todas": la regla 3 del dominio impide comparar magnitudes de distinta
 * moneda sin normalizar, así que el selector siempre resuelve a una concreta con `monedaInicial`
 * antes de filtrar.
 *
 * ## El centinela de "sin dato" es un valor más
 *
 * Cada dimensión ofrece su propio centinela desde `valores()`, mismo precedente que
 * `LEY_NO_INFORMADA` / `CALIFICACION_NO_INFORMADA` de la renta fija. Un dato faltante **nunca
 * cumple** un filtro activo de esa dimensión (regla 1); lo único que cumple es su propio centinela.
 */

import { facetar, type Faceta } from '@/lib/facetado'
import { SIN_MONEDA_DECLARADA } from '@/components/SelectorMoneda'
import { cumpleFiltroRv, presetRvPorId, PRESETS_RV, type PresetRv } from '@/lib/presetsRv'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'

/** Las seis dimensiones facetadas, en el orden de validación. */
export type DimensionRv = 'region' | 'pais' | 'mercado' | 'sector' | 'rubroEspecifico' | 'estrategiaEtf'

export const DIMENSIONES_RV: readonly DimensionRv[] = [
  'region',
  'pais',
  'mercado',
  'sector',
  'rubroEspecifico',
  'estrategiaEtf',
] as const

export const ROTULO_DIMENSION_RV: Record<DimensionRv, string> = {
  region: 'Región',
  pais: 'País',
  mercado: 'Mercado',
  sector: 'Sector',
  rubroEspecifico: 'Rubro específico',
  estrategiaEtf: 'Estrategia del fondo',
}

/** Qué mira cada chip y de dónde sale. Va como `title`: un filtro que no dice qué recorta obliga
 *  al asesor a deducirlo del resultado. */
export const DETALLE_DIMENSION_RV: Record<DimensionRv, string> = {
  region:
    'Subregión M49 de la ONU derivada de un país curado (empresa o ETF mono-país), el alcance que ' +
    'declara el emisor del índice para un ETF multi-país, o el token crudo que trae el nombre del ' +
    'fondo cuando nada de eso está curado todavía ("EAFE", "Brazil") — sin traducir.',
  pais:
    'País de la empresa o del ETF mono-país, ISO 3166-1 alfa-2, curado papel por papel con fuente ' +
    'y fecha. Un fondo multi-país no tiene país propio: su eje geográfico es la región.',
  mercado:
    'Mercado donde cotiza el subyacente, según el PDF de CEDEARs de BYMA. Las variantes de ' +
    'mayúsculas del mismo mercado se cuentan juntas ("NYSE Arca" y "NYSE ARCA"); los escalones de ' +
    'NASDAQ (GS, GM, CM) no, porque la fuente los distingue.',
  sector:
    'Major group SIC de dos dígitos, aritmética sobre el código de la SEC. La etiqueta es curada ' +
    '(`data/sic_sectores.csv`); sin fila cargada se muestra el código crudo.',
  rubroEspecifico:
    'Código SIC de cuatro dígitos, tal como lo declara la SEC. La etiqueta es curada ' +
    '(`data/sic_rubros.csv`); sin fila cargada se muestra el título oficial en inglés de la SEC.',
  estrategiaEtf:
    'Qué idea arma el portafolio del fondo, leída de su nombre oficial. Una acción no tiene ' +
    'estrategia: cae en el chip de sin declarar, junto con los fondos cuyo nombre no la dice.',
}

/**
 * Los centinelas de "el dato no está". No son valores de la base —ahí ese caso es `null`— y se
 * nombran para poder filtrar hacia el hueco sin confundirlo con "sin filtro". Los prefijos evitan
 * cualquier colisión con un valor real de la fuente.
 */
export const REGION_SIN_DATO = 'region_sin_dato'
export const PAIS_SIN_DATO = 'pais_sin_dato'
export const MERCADO_SIN_DATO = 'mercado_sin_dato'
export const SECTOR_SIN_DATO = 'sector_sin_dato'
export const RUBRO_ESPECIFICO_SIN_DATO = 'rubro_especifico_sin_dato'
export const ESTRATEGIA_SIN_DATO = 'estrategia_sin_dato'

/** Cómo se lee en pantalla cada centinela. El texto dice qué falta, no "otros": un tramo llamado
 *  "otros" invita a leerlo como una categoría, y esto es un agujero de cobertura. */
export const ETIQUETA_SIN_DATO: Record<string, string> = {
  [REGION_SIN_DATO]: '(sin región)',
  [PAIS_SIN_DATO]: '(sin país)',
  [MERCADO_SIN_DATO]: '(sin mercado)',
  [SECTOR_SIN_DATO]: '(sin sector)',
  [RUBRO_ESPECIFICO_SIN_DATO]: '(sin rubro específico)',
  [ESTRATEGIA_SIN_DATO]: '(sin estrategia)',
}

/** El centinela de cada dimensión, para que quien recorre las dimensiones no tenga que saberlos. */
export const CENTINELA_DE: Record<DimensionRv, string> = {
  region: REGION_SIN_DATO,
  pais: PAIS_SIN_DATO,
  mercado: MERCADO_SIN_DATO,
  sector: SECTOR_SIN_DATO,
  rubroEspecifico: RUBRO_ESPECIFICO_SIN_DATO,
  estrategiaEtf: ESTRATEGIA_SIN_DATO,
}

/** Cómo se lee cada estrategia en pantalla. Espejo de las claves de `app/renta_variable/etfs.py`,
 *  duplicado a propósito de `instrumento/FichaRentaVariable.tsx` y de
 *  `armador/components/BloqueRentaVariable.tsx`: son features distintas que no comparten módulo,
 *  el mismo criterio que ya se aplicó dos veces con este mismo diccionario. */
export const ETIQUETA_ESTRATEGIA_RV: Record<string, string> = {
  indice_amplio: 'índice amplio',
  equiponderado: 'equiponderado',
  factor: 'por factor',
  geografico: 'geográfico',
  sectorial: 'sectorial',
  activo_fisico: 'activo físico',
  cripto: 'cripto',
  esg: 'ESG',
  sin_clasificar: 'sin clasificar',
}

export interface FiltrosRentaVariable {
  /** Cascada de región (ver el docstring del módulo), o `REGION_SIN_DATO`. `null` = sin filtro. */
  region: string | null
  /** `pais ?? etf_pais`, o `PAIS_SIN_DATO`. `null` = sin filtro. */
  pais: string | null
  /** Forma canónica del mercado (la más frecuente entre las variantes de caja), o
   *  `MERCADO_SIN_DATO`. `null` = sin filtro. */
  mercado: string | null
  /** `sector_codigo` (major group SIC, dos dígitos), o `SECTOR_SIN_DATO`. `null` = sin filtro. */
  sector: string | null
  /** `sic_codigo` (cuatro dígitos), o `RUBRO_ESPECIFICO_SIN_DATO`. `null` = sin filtro. */
  rubroEspecifico: string | null
  /** Clave de `estrategia_etf`, o `ESTRATEGIA_SIN_DATO`. `null` = sin filtro. */
  estrategiaEtf: string | null
  /** `id` de `PRESETS_RV`. No es una faceta: es un recorte del universo que siempre aplica y
   *  siempre se ve, como los umbrales de la renta fija. `null` = sin preset. */
  presetId: string | null
  /** Texto libre del buscador, sin normalizar (la normalización ocurre al filtrar). Es intención
   *  temática igual que `presetId`: sobrevive al cambio de moneda (`filtrosAlCambiarDeMoneda`).
   *  `''` = sin búsqueda. */
  busqueda: string
}

export const FILTROS_RV_VACIOS: FiltrosRentaVariable = {
  region: null,
  pais: null,
  mercado: null,
  sector: null,
  rubroEspecifico: null,
  estrategiaEtf: null,
  presetId: null,
  busqueda: '',
}

/** Lo mínimo que este módulo necesita de una especie. Se declara estructural en vez de pedir
 *  `EspecieRentaVariable` entera para que los tests puedan armar fixtures sin las 30 columnas de
 *  precio que acá no juegan; `EspecieRentaVariable` lo satisface por construcción. */
type EspecieClasificable = Pick<
  EspecieRentaVariable,
  | 'ticker'
  | 'nombre_largo'
  | 'moneda_cotizacion'
  | 'mercado_origen'
  | 'sic_codigo'
  | 'sic_titulo'
  | 'sector_codigo'
  | 'sector'
  | 'rubro_especifico'
  | 'estrategia_etf'
  | 'region_etf'
  | 'pais'
  | 'region'
  | 'etf_pais'
  | 'etf_region'
  | 'etf_alcance'
>

/**
 * La forma canónica de cada mercado: clave en minúsculas → la variante literal **más frecuente**
 * en el universo.
 *
 * Se muestra la más frecuente y no una capitalización propia porque la mayoritaria sigue siendo un
 * string que la fuente escribió; "Nyse Arca" no lo escribió nadie. Los empates se rompen por orden
 * alfabético para que el rótulo no dependa del orden en que llegaron las filas.
 *
 * Se calcula sobre el universo **entero** de la clase, no sobre el recorte visible: si dependiera
 * de los filtros activos, el rótulo del chip podría cambiar de caja al cambiar de moneda.
 */
export function formasCanonicasDeMercado(
  especies: readonly { mercado_origen: string | null }[],
): Map<string, string> {
  const variantes = new Map<string, Map<string, number>>()
  for (const especie of especies) {
    const crudo = especie.mercado_origen
    if (crudo === null) continue
    const clave = crudo.toLowerCase()
    const porVariante = variantes.get(clave) ?? new Map<string, number>()
    porVariante.set(crudo, (porVariante.get(crudo) ?? 0) + 1)
    variantes.set(clave, porVariante)
  }

  const canonicas = new Map<string, string>()
  for (const [clave, porVariante] of variantes) {
    const [ganadora] = [...porVariante.entries()].sort(
      (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]),
    )
    canonicas.set(clave, ganadora[0])
  }
  return canonicas
}

/** El mercado del papel en su forma canónica, o el centinela si la fuente no lo declaró. */
function mercadoDe(especie: EspecieClasificable, canonicas: Map<string, string>): string {
  const crudo = especie.mercado_origen
  if (crudo === null) return MERCADO_SIN_DATO
  return canonicas.get(crudo.toLowerCase()) ?? crudo
}

/** El país del papel: el curado de la empresa, o el del ETF mono-país si no es una empresa. Los
 *  dos son ISO 3166-1 alfa-2 curados con fuente y fecha (F-079/D3), así que unificarlos es leer dos
 *  fuentes del mismo vocabulario, no traducir una a la otra (ver el docstring del módulo). */
function paisDe(especie: EspecieClasificable): string {
  return especie.pais ?? especie.etf_pais ?? PAIS_SIN_DATO
}

/** La región del papel, en cascada de lo más curado a lo más crudo: ver el docstring del módulo
 *  para el porqué de cada escalón. A diferencia de F-078 ya no es dual (no ofrece dos valores a la
 *  vez): con hasta cuatro fuentes candidatas, sumarlas todas duplicaría el papel en la faceta. */
function regionDe(especie: EspecieClasificable): string {
  return especie.region ?? especie.etf_region ?? especie.etf_alcance ?? especie.region_etf ?? REGION_SIN_DATO
}

/** El sector del papel: el major group SIC, dos dígitos. Aritmética pura sobre `sic_codigo`, sin
 *  depender de ningún curado (a diferencia de la etiqueta que lo representa en pantalla). */
function sectorCodigoDe(especie: EspecieClasificable): string {
  return especie.sector_codigo ?? SECTOR_SIN_DATO
}

/** El rubro específico del papel: el código SIC de cuatro dígitos, tal como lo declara la SEC. */
function rubroEspecificoDe(especie: EspecieClasificable): string {
  return especie.sic_codigo ?? RUBRO_ESPECIFICO_SIN_DATO
}

/** Cómo se lee cada `sector_codigo` en pantalla, `rubroEspecifico` en pantalla y el título en
 *  inglés de la SEC por código SIC de cuatro dígitos (para el `title` de cada opción, que deja la
 *  fuente visible incluso cuando la etiqueta ya está en español). Ver `etiquetaDeValorRv` y
 *  `tituloOpcionRv`, que son quienes las consumen. */
export interface EtiquetasRv {
  /** `sector_codigo` → etiqueta ES (`data/sic_sectores.csv`). Sólo trae entrada cuando alguna
   *  especie del universo con ese código trajo la etiqueta cargada. */
  sector: Map<string, string>
  /** `sic_codigo` → etiqueta a mostrar: la ES curada si existe, si no el título en inglés de la
   *  SEC (`sic_titulo`), que siempre está presente cuando hay `sic_codigo`. */
  rubroEspecifico: Map<string, string>
  /** `sic_codigo` → `sic_titulo`, siempre en inglés, tal como lo publica la SEC. Es la fuente que
   *  el `title` de cada opción de rubro específico deja a la vista. */
  sicTitulos: Map<string, string>
  /** `sector_codigo` → `sector_titulo`, el nombre oficial del major group del SIC Manual de OSHA
   *  (30/08/2026), siempre en inglés. A diferencia de `sicTitulos` no está garantizado para todo
   *  código: el Manual deja huecos (18-19, 68-69, 90) sin nombre — ver `app/externos/sic.py`. */
  sectorTitulos: Map<string, string>
}

/** Los dos mapas de sector: la etiqueta ES curada (`data/sic_sectores.csv`, sólo trae entrada
 *  cuando alguna especie del universo con ese código trajo la etiqueta cargada) y el nombre
 *  oficial del major group en inglés (SIC Manual de OSHA, presente salvo en los huecos del
 *  Manual). Mismo patrón que `etiquetasDeRubroEspecifico`: se recorren juntos porque escanean el
 *  mismo universo una sola vez. Sin ninguna entrada para un código, el fallback (mostrar el
 *  código crudo) lo decide `etiquetaDeValorRv`, no esta función. */
export function etiquetasDeSector(
  especies: readonly {
    sector_codigo: string | null
    sector: string | null
    sector_titulo: string | null
  }[],
): { etiquetas: Map<string, string>; sectorTitulos: Map<string, string> } {
  const etiquetas = new Map<string, string>()
  const sectorTitulos = new Map<string, string>()
  for (const especie of especies) {
    if (especie.sector_codigo === null) continue
    if (especie.sector_titulo !== null && !sectorTitulos.has(especie.sector_codigo)) {
      sectorTitulos.set(especie.sector_codigo, especie.sector_titulo)
    }
    if (especie.sector !== null && !etiquetas.has(especie.sector_codigo)) {
      etiquetas.set(especie.sector_codigo, especie.sector)
    }
  }
  return { etiquetas, sectorTitulos }
}

/** Los dos mapas de rubro específico: la etiqueta a mostrar (ES si hay, si no el título EN de la
 *  SEC) y el título EN puro para el `title` de cada opción. Se calculan juntos porque recorren el
 *  mismo universo una sola vez. */
export function etiquetasDeRubroEspecifico(
  especies: readonly {
    sic_codigo: string | null
    rubro_especifico: string | null
    sic_titulo: string | null
  }[],
): { etiquetas: Map<string, string>; sicTitulos: Map<string, string> } {
  const etiquetas = new Map<string, string>()
  const sicTitulos = new Map<string, string>()
  for (const especie of especies) {
    if (especie.sic_codigo === null) continue
    if (especie.sic_titulo !== null && !sicTitulos.has(especie.sic_codigo)) {
      sicTitulos.set(especie.sic_codigo, especie.sic_titulo)
    }
    if (especie.rubro_especifico !== null && !etiquetas.has(especie.sic_codigo)) {
      etiquetas.set(especie.sic_codigo, especie.rubro_especifico)
    }
  }
  // Sin etiqueta ES para el código, el fallback es el título EN de la propia fila — que, a
  // diferencia del sector, siempre existe si hay `sic_codigo` (es la fuente, no una interpretación).
  for (const [codigo, titulo] of sicTitulos) {
    if (!etiquetas.has(codigo)) etiquetas.set(codigo, titulo)
  }
  return { etiquetas, sicTitulos }
}

/** Quita acentos y normaliza mayúsculas, para que la búsqueda no dependa de cómo el asesor tipeó
 *  ("Farmaceutica" y "farmacéutica" tienen que matchear lo mismo). */
export function foldTexto(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

/** Si el texto buscado aparece en algo que la especie declara: ticker, nombre largo, la etiqueta ES
 *  de sector o de rubro específico si la especie misma las trae cargadas, o el título SIC en
 *  inglés (para que la búsqueda encuentre algo incluso sin curado ES). `textoFoldeado` ya viene
 *  normalizado con `foldTexto`; un texto vacío no filtra nada. */
export function coincideBusquedaRv(especie: EspecieClasificable, textoFoldeado: string): boolean {
  if (textoFoldeado === '') return true
  const candidatos = [
    especie.ticker,
    especie.nombre_largo,
    especie.sector,
    especie.rubro_especifico,
    especie.sic_titulo,
  ]
  return candidatos.some((candidato) => candidato !== null && foldTexto(candidato).includes(textoFoldeado))
}

/** Qué presets temáticos coinciden con el texto buscado: por su etiqueta o por cualquiera de las
 *  `palabrasEnNombre` que declara su filtro. No inventa sinónimos —si "salud" tiene que encontrar
 *  "Medicina y salud", esa palabra se agrega al preset, no a un mapa acá (ver el docstring del
 *  módulo)—, así que un preset sin ninguna palabra cargada simplemente no aparece en las sugerencias
 *  salvo que el texto matchee su propia etiqueta. */
export function presetsQueCoinciden(textoFoldeado: string): PresetRv[] {
  if (textoFoldeado === '') return []
  return PRESETS_RV.filter((preset) => {
    if (foldTexto(preset.etiqueta).includes(textoFoldeado)) return true
    return (preset.filtro.palabrasEnNombre ?? []).some((palabra) =>
      foldTexto(palabra).includes(textoFoldeado),
    )
  })
}

/** El preset activo, como recorte del universo. Un `presetId` que no existe en `PRESETS_RV` no
 *  filtra nada (en vez de vaciar la pantalla en silencio por un id viejo guardado en un estado). */
function cumplePreset(especie: EspecieRentaVariable, presetId: string | null): boolean {
  const preset = presetRvPorId(presetId)
  if (preset === null) return true
  return cumpleFiltroRv(especie, preset.filtro, preset.modo)
}

/**
 * Los filtros que siempre aplican y nunca quedan apagados: la moneda elegida, el preset temático y
 * el buscador de texto.
 *
 * `moneda === null` significa **sin restringir por moneda**, no "todas mezcladas": quien llama
 * resuelve la moneda a una concreta con `monedaInicial` antes de mostrar nada (regla 3), y el
 * `null` sólo existe para poder contar los chips de moneda con la propia dimensión neutralizada,
 * igual que hace `UniversoDelSegmento` en la renta fija.
 *
 * La búsqueda entra acá y no como faceta: si fuera una dimensión más, el facetado podría apagarla
 * cuando no tuviera respaldo, y un buscador que se autolimpia en silencio es peor que uno que
 * simplemente no encuentra nada.
 */
function pasaBaseRv(
  especie: EspecieRentaVariable,
  filtros: FiltrosRentaVariable,
  moneda: string | null,
): boolean {
  if (moneda !== null && (especie.moneda_cotizacion ?? SIN_MONEDA_DECLARADA) !== moneda) return false
  if (!cumplePreset(especie, filtros.presetId)) return false
  const textoBuscado = filtros.busqueda.trim()
  if (textoBuscado !== '' && !coincideBusquedaRv(especie, foldTexto(textoBuscado))) return false
  return true
}

/** Las seis dimensiones como `Faceta` para el motor genérico. El orden del array es el orden de
 *  validación (ver el docstring del módulo). */
function facetasDeRentaVariable(
  filtros: FiltrosRentaVariable,
  canonicas: Map<string, string>,
): Array<Faceta<EspecieRentaVariable>> {
  const unica = (valor: string | null) => (valor === null ? [] : [valor])

  return [
    {
      id: 'region',
      seleccion: unica(filtros.region),
      coincide: (especie, valor) => regionDe(especie) === valor,
      valores: (especie) => [regionDe(especie)],
    },
    {
      id: 'pais',
      seleccion: unica(filtros.pais),
      coincide: (especie, valor) => paisDe(especie) === valor,
      valores: (especie) => [paisDe(especie)],
    },
    {
      id: 'mercado',
      seleccion: unica(filtros.mercado),
      // Se compara en minúsculas de los dos lados: así la selección guardada sigue valiendo aunque
      // la forma canónica cambie de caja al cambiar el universo de referencia.
      coincide: (especie, valor) => {
        const propio = mercadoDe(especie, canonicas)
        return propio.toLowerCase() === valor.toLowerCase()
      },
      valores: (especie) => [mercadoDe(especie, canonicas)],
    },
    {
      id: 'sector',
      seleccion: unica(filtros.sector),
      coincide: (especie, valor) => sectorCodigoDe(especie) === valor,
      valores: (especie) => [sectorCodigoDe(especie)],
    },
    {
      id: 'rubroEspecifico',
      seleccion: unica(filtros.rubroEspecifico),
      coincide: (especie, valor) => rubroEspecificoDe(especie) === valor,
      valores: (especie) => [rubroEspecificoDe(especie)],
    },
    {
      id: 'estrategiaEtf',
      seleccion: unica(filtros.estrategiaEtf),
      coincide: (especie, valor) => (especie.estrategia_etf ?? ESTRATEGIA_SIN_DATO) === valor,
      valores: (especie) => [especie.estrategia_etf ?? ESTRATEGIA_SIN_DATO],
    },
  ]
}

/**
 * Si una especie pasa todos los filtros activos: la moneda, el preset, la búsqueda y las seis
 * dimensiones.
 *
 * Se le pasa `efectivos` (lo que el facetado confirmó), no el filtro crudo: una selección sin
 * respaldo ya quedó apagada y declarada, y aplicarla igual acá dejaría la tabla vacía sin que
 * ningún chip lo explique.
 */
export function pasaFiltrosRv(
  especie: EspecieRentaVariable,
  filtros: FiltrosRentaVariable,
  moneda: string | null,
): boolean {
  if (!pasaBaseRv(especie, filtros, moneda)) return false
  if (filtros.region !== null && regionDe(especie) !== filtros.region) return false
  if (filtros.pais !== null && paisDe(especie) !== filtros.pais) return false
  if (filtros.mercado !== null) {
    const propio = especie.mercado_origen?.toLowerCase() ?? MERCADO_SIN_DATO
    if (propio !== filtros.mercado.toLowerCase()) return false
  }
  if (filtros.sector !== null && sectorCodigoDe(especie) !== filtros.sector) return false
  if (filtros.rubroEspecifico !== null && rubroEspecificoDe(especie) !== filtros.rubroEspecifico) {
    return false
  }
  if (
    filtros.estrategiaEtf !== null &&
    (especie.estrategia_etf ?? ESTRATEGIA_SIN_DATO) !== filtros.estrategiaEtf
  ) {
    return false
  }
  return true
}

/** Una opción de chip con su conteo. `especies`, no papeles: es la cantidad de filas que la tabla
 *  va a mostrar si se toca ese chip, y con una sola moneda a la vista hay una fila por papel. */
export interface OpcionRv {
  valor: string
  especies: number
}

export interface OpcionesFacetadasRv {
  /** Por dimensión: las opciones con respaldo, ya ordenadas para la pantalla. */
  porDimension: Record<DimensionRv, OpcionRv[]>
  /** Cuántas especies quedan bajo el resto de los filtros con esa dimensión neutralizada — el
   *  conteo del chip "Todos" de cada fila. */
  totalPorDimension: Record<DimensionRv, number>
}

export interface SeleccionApagadaRv {
  dimension: DimensionRv
  valor: string
}

/** `true` si la especie pasa `pasaBase` y todas las dimensiones **menos** `excepto`. Es el mismo
 *  leave-one-out que aplica `facetar()` para las opciones, replicado acá porque los chips además
 *  de la lista de valores muestran cuántas especies hay en cada uno, y eso el motor genérico no lo
 *  devuelve (no tiene por qué: no todas las pantallas cuentan). */
function pasaTodasMenosRv(
  especie: EspecieRentaVariable,
  facetas: Array<Faceta<EspecieRentaVariable>>,
  efectivas: Map<string, string[]>,
  base: (especie: EspecieRentaVariable) => boolean,
  excepto: DimensionRv,
): boolean {
  if (!base(especie)) return false
  for (const faceta of facetas) {
    if (faceta.id === excepto) continue
    const seleccion = efectivas.get(faceta.id) ?? []
    if (seleccion.length === 0) continue
    if (!seleccion.some((valor) => faceta.coincide(especie, valor))) return false
  }
  return true
}

/** Primero lo más poblado, después alfabético, y el centinela siempre último: el hueco se ve, pero
 *  no encabeza la fila de chips como si fuera una categoría más del universo. */
function ordenarOpciones(opciones: OpcionRv[], centinela: string): OpcionRv[] {
  return [...opciones].sort((a, b) => {
    if (a.valor === centinela) return 1
    if (b.valor === centinela) return -1
    return b.especies - a.especies || a.valor.localeCompare(b.valor, 'es')
  })
}

/**
 * Facetado en cascada de la renta variable, sobre el motor genérico de `@/lib/facetado` — ver ese
 * módulo para la semántica completa (validación por orden, opciones leave-one-out, selecciones sin
 * respaldo declaradas). Acá se arman los descriptores, se cuentan las opciones y se traduce el
 * resultado a la forma que consume la pantalla.
 *
 * `especies` tiene que ser el universo **entero** de la clase, sin recortar por moneda: la moneda
 * entra como `pasaBase` para que los chips se acoten con ella, y las formas canónicas de mercado y
 * los mapas de etiquetas se calculan sobre todo el universo para que no dependan del recorte
 * visible.
 */
export function facetarRentaVariable(
  especies: EspecieRentaVariable[],
  filtros: FiltrosRentaVariable,
  moneda: string | null,
): {
  opciones: OpcionesFacetadasRv
  efectivos: FiltrosRentaVariable
  apagadas: SeleccionApagadaRv[]
  /** Las formas canónicas de mercado usadas acá, para que la composición del universo agrupe con
   *  el mismo criterio que los chips en vez de recalcularlo y arriesgarse a divergir. */
  mercados: Map<string, string>
  /** Los mapas de etiqueta de sector y rubro específico, con el mismo criterio: se calculan una
   *  vez acá y se comparten con quien pinta los `CampoSelect`. */
  etiquetas: EtiquetasRv
} {
  const mercados = formasCanonicasDeMercado(especies)
  const { etiquetas: etiquetasRubroEspecifico, sicTitulos } = etiquetasDeRubroEspecifico(especies)
  const { etiquetas: etiquetasSector, sectorTitulos } = etiquetasDeSector(especies)
  const etiquetas: EtiquetasRv = {
    sector: etiquetasSector,
    rubroEspecifico: etiquetasRubroEspecifico,
    sicTitulos,
    sectorTitulos,
  }
  const facetas = facetasDeRentaVariable(filtros, mercados)
  const base = (especie: EspecieRentaVariable) => pasaBaseRv(especie, filtros, moneda)

  const resultado = facetar(especies, facetas, base)

  const porDimension = {} as Record<DimensionRv, OpcionRv[]>
  const totalPorDimension = {} as Record<DimensionRv, number>

  for (const faceta of facetas) {
    const dimension = faceta.id as DimensionRv
    const conRespaldo = new Set(resultado.opciones.get(faceta.id) ?? [])
    const conteo = new Map<string, number>()
    let total = 0

    for (const especie of especies) {
      if (!pasaTodasMenosRv(especie, facetas, resultado.efectivas, base, dimension)) continue
      total += 1
      for (const valor of faceta.valores(especie)) {
        if (!conRespaldo.has(valor)) continue
        conteo.set(valor, (conteo.get(valor) ?? 0) + 1)
      }
    }

    porDimension[dimension] = ordenarOpciones(
      [...conteo.entries()].map(([valor, cantidad]) => ({ valor, especies: cantidad })),
      CENTINELA_DE[dimension],
    )
    totalPorDimension[dimension] = total
  }

  const efectivos: FiltrosRentaVariable = {
    ...filtros,
    region: resultado.efectivas.get('region')?.[0] ?? null,
    pais: resultado.efectivas.get('pais')?.[0] ?? null,
    mercado: resultado.efectivas.get('mercado')?.[0] ?? null,
    sector: resultado.efectivas.get('sector')?.[0] ?? null,
    rubroEspecifico: resultado.efectivas.get('rubroEspecifico')?.[0] ?? null,
    estrategiaEtf: resultado.efectivas.get('estrategiaEtf')?.[0] ?? null,
  }

  return {
    opciones: { porDimension, totalPorDimension },
    efectivos,
    apagadas: resultado.apagadas.map(({ dimension, valor }) => ({
      dimension: dimension as DimensionRv,
      valor,
    })),
    mercados,
    etiquetas,
  }
}

/** Cómo se lee un valor de faceta en pantalla: los centinelas por su nombre de hueco, las
 *  estrategias por su etiqueta en castellano, rubroEspecifico por el `Map` que trae `etiquetas`
 *  (si se pasa; sin él, el propio código), sector por la etiqueta ES si existe y si no por el
 *  nombre oficial del major group (SIC Manual de OSHA, 30/08/2026) — y todo lo demás **tal como la
 *  fuente lo escribe** (regla 11: un rótulo de la fuente no se traduce). */
export function etiquetaDeValorRv(dimension: DimensionRv, valor: string, etiquetas?: EtiquetasRv): string {
  if (valor === CENTINELA_DE[dimension]) return ETIQUETA_SIN_DATO[valor]
  if (dimension === 'estrategiaEtf') return ETIQUETA_ESTRATEGIA_RV[valor] ?? valor
  if (dimension === 'sector') return etiquetas?.sector.get(valor) ?? etiquetas?.sectorTitulos.get(valor) ?? valor
  if (dimension === 'rubroEspecifico') return etiquetas?.rubroEspecifico.get(valor) ?? valor
  return valor
}

/** El `title` de una opción de `CampoSelect`, cuando hace falta dejar la fuente a la vista:
 *  - Sector con el nombre OSHA (sin ES curada, con título): la fuente queda visible aunque la
 *    etiqueta que se ve ya venga del catálogo público y no de un curado validado.
 *  - Sector sin ES **ni** título OSHA (un código en un hueco del Manual): el código no alcanza
 *    para explicarse solo — caso residual, ya no el habitual desde 30/08/2026.
 *  - Rubro específico: siempre, con el título en inglés de la SEC (`sic_titulo`), esté o no
 *    curada la etiqueta ES — así la fuente queda visible aunque la etiqueta ya esté en español.
 *  `undefined` cuando no hace falta (sector con etiqueta ES cargada, centinelas, otras dimensiones):
 *  un `title` vacío es peor que ninguno. */
export function tituloOpcionRv(
  dimension: DimensionRv,
  valor: string,
  etiquetas: EtiquetasRv,
): string | undefined {
  if (dimension === 'sector' && valor !== SECTOR_SIN_DATO && !etiquetas.sector.has(valor)) {
    const titulo = etiquetas.sectorTitulos.get(valor)
    if (titulo !== undefined) return `SIC major group ${valor} — ${titulo} (OSHA)`
    return `SIC major group ${valor} — sin traducción cargada`
  }
  if (dimension === 'rubroEspecifico' && valor !== RUBRO_ESPECIFICO_SIN_DATO) {
    const titulo = etiquetas.sicTitulos.get(valor)
    if (titulo !== undefined) return `SIC ${valor} — ${titulo} (SEC)`
  }
  return undefined
}

/**
 * Qué queda del recorte cuando el asesor cambia de moneda: las facetas se limpian, **el preset
 * temático y la búsqueda sobreviven**.
 *
 * Las dos mitades tienen motivo propio y opuesto, y por eso esto es una función con nombre y no un
 * `setFiltros(FILTROS_RV_VACIOS)` adentro de un handler:
 *
 * - **Las facetas se limpian** porque no todo papel cotiza en las tres denominaciones: un recorte
 *   por país o por sector armado sobre una moneda describe otro subconjunto en la siguiente, y las
 *   barras de composición cambiarían de significado sin cambiar de aspecto.
 * - **El preset y la búsqueda no**, porque ninguno de los dos depende de la moneda: "quiero metales
 *   preciosos" o "busco farmacéuticas" son intención sobre qué empresa, y en qué denominación
 *   liquida es otra pregunta. Borrarlos obligaría a volver a tocarlos para seguir mirando
 *   exactamente lo mismo.
 */
export function filtrosAlCambiarDeMoneda(filtros: FiltrosRentaVariable): FiltrosRentaVariable {
  return { ...FILTROS_RV_VACIOS, presetId: filtros.presetId, busqueda: filtros.busqueda }
}
