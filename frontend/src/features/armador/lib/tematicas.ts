/**
 * Atajos temáticos para armar carteras con un objetivo puntual — Tanda 13.
 *
 * Un preset no decide nada: precarga filtros que ya existen y quedan a la vista, editables. La
 * diferencia con tocarlos a mano es la velocidad —"quiero una cartera de energía" es un clic en vez
 * de dos selects y un scroll—, no el criterio.
 *
 * **Los sectores de renta fija están verificados contra `data/condiciones_emision.csv`** (10/08/2026):
 * los únicos valores que existen son Soberano (125), O&G (85), Financiera (60), Subsoberano (47),
 * Servicios (28), Agro (26), Industria (10), Real Estate (10), Energias Renovables (9), Alimentos y
 * Consumo (8), Telecomunicaciones (8), Construccion (3), Infraestructura (2) y Mineria (2). Un
 * preset no puede referirse a un sector que no está en esa lista: sería filtrar por una categoría
 * inventada y devolver cero sin explicar por qué.
 *
 * **No hay renta fija tecnológica ni de salud en el universo**, y por eso esos dos presets declaran
 * que arman sólo renta variable en vez de aproximar con Telecomunicaciones o con Servicios, que son
 * otra cosa. Al revés pasa lo mismo: Agro y Energias Renovables existen en renta fija pero la
 * fuente de renta variable no les da un rubro propio, así que esos presets no filtran renta
 * variable en vez de elegir por la fuente cuál de sus categorías "es" el rubro (regla 11).
 *
 * **Petróleo y renovables van separados a propósito.** El universo de renta fija las clasifica
 * distinto (`O&G` contra `Energias Renovables`) y juntarlas bajo una etiqueta "Energía" haría que
 * un preset devuelva emisiones de un rubro que el asesor no pidió.
 *
 * **Los rubros de renta variable son los de la SEC** (`sic_oficina`), que llegan por la
 * clasificación (`app/renta_variable/clasificacion.py`) y cubren 870 especies al 13/08/2026.
 *
 * **Desde F-078 un preset puede acotar la renta variable de dos maneras.** `rubroRv` es el atajo
 * de una sola dimensión —una temática que se dice con un solo `sic_oficina`— y sigue existiendo
 * porque el backend lo sigue aceptando (F-052) y algún preset futuro puede volver a necesitarlo.
 * `filtroRv` es la general, para las que ninguna fuente declara con un campo — "metales preciosos"
 * es la unión de tres declaraciones distintas (el metal físico de un ETF, el código SIC de una
 * minera, el nombre oficial de BYMA). **Desde F-079 los presets de un solo rubro (financieras,
 * tecnológicas, medicina) también pasaron a `filtroRv`**: no porque dejaran de ser de un solo
 * rubro, sino porque su definición vive compartida en `lib/presetsRv.ts` —de donde la lee también
 * el monitor— y acá sólo se la referencia por id. Duplicarla dejaría que las dos pantallas
 * empezaran a decir cosas distintas sobre qué oficina define cada temática.
 *
 * **Dos presets no tienen filtro de renta variable, y es a propósito.** La SEC
 * agrupa por oficina, y ninguna de sus oficinas dice "petróleo" ni "consumo masivo":
 * `Office of Energy & Transportation` mezcla petroleras (41 especies) con mineras de oro (46),
 * eléctricas (22) y aerolíneas (25) — medido el 13/08/2026 —, y `Office of Trade & Services` es
 * comercio minorista de todo tipo. Filtrar "Petróleo y gas" por esa oficina traería Barrick Gold y
 * American Airlines, que es exactamente lo que un preset temático no puede hacer.
 */

import { presetRvPorId, type FiltroRv, type ModoFiltroRv, type PresetRv } from '@/lib/presetsRv'

import { FILTROS_ARMADOR_VACIOS, type FiltrosArmador } from './filtros'

export interface PresetTematico {
  id: string
  etiqueta: string
  /** Qué filtros de la grilla de renta fija precarga. `null` = ninguno aplica, y la nota dice por qué. */
  filtrosRf: Partial<FiltrosArmador> | null
  /** Rubro de la SEC (`sic_oficina`), literal y sin normalizar, para el bloque de renta variable.
   *  `null` = el preset no filtra la renta variable por rubro, y la nota dice por qué.
   *
   *  **Se mantiene como el caso particular que ya funciona** (F-078): una temática que se dice con
   *  un solo rubro no necesita un filtro multidimensional, y el backend sigue aceptando `rubro_rv`
   *  como el atajo que es. Los dos campos no se llenan a la vez — mandar `rubro_rv` y
   *  `filtro_rv.rubros` con valores distintos es 422 del lado del backend, a propósito. */
  rubroRv: string | null
  /**
   * Filtro multidimensional de renta variable, para las temáticas que **ninguna fuente declara con
   * un solo campo** — F-078.
   *
   * "Metales preciosos" es el caso: no existe un `sic_oficina` que lo diga, y la categoría se arma
   * uniendo tres declaraciones de fuentes distintas (el metal físico de un ETF, el código SIC de
   * una minera, el nombre oficial de BYMA). La definición **no vive acá**: vive en
   * `lib/presetsRv.ts`, que es de donde la lee también el monitor, y acá sólo se la referencia.
   * Duplicarla haría que la pantalla del monitor y la del armador pudieran empezar a decir cosas
   * distintas sobre qué es un metal precioso.
   */
  filtroRv?: FiltroRv
  /** Cómo se combinan las dimensiones de `filtroRv`. `union` para los presets que juntan
   *  declaraciones de fuentes distintas (ninguna especie las tiene a las tres). */
  modoFiltroRv?: ModoFiltroRv
  /** Qué hace y qué no. Se muestra como tooltip: un atajo que no explica qué precargó es magia. */
  nota: string
}

/** Un preset de `lib/presetsRv.ts` por id, o error al cargar el módulo. Un `id` mal escrito acá
 *  dejaría una temática silenciosamente sin filtro de renta variable —que es un estado válido para
 *  otras temáticas— y nadie lo notaría hasta que un asesor pidiera metales y recibiera el panel
 *  entero. */
function presetRvObligatorio(id: string): PresetRv {
  const preset = presetRvPorId(id)
  if (preset === null) {
    throw new Error(`tematicas.ts referencia el preset de renta variable "${id}", que no existe en PRESETS_RV`)
  }
  return preset
}

const METALES_PRECIOSOS = presetRvObligatorio('metales-preciosos')
// F-079: financieras, tecnológicas y medicina eran temáticas de un solo `sic_oficina` inline;
// ahora referencian el mismo preset compartido que ya usa el monitor (`lib/presetsRv.ts`), para
// que las dos pantallas no puedan empezar a decir cosas distintas sobre qué oficina las define.
const FINANCIERAS = presetRvObligatorio('financieras')
const TECNOLOGICAS = presetRvObligatorio('tecnologicas')
const MEDICINA = presetRvObligatorio('medicina')

export const PRESETS_TEMATICOS: PresetTematico[] = [
  {
    id: 'financieras',
    etiqueta: 'Financieras',
    filtrosRf: { sector: 'Financiera' },
    // F-079: migrado de `rubroRv` inline a referenciar el preset compartido de `lib/presetsRv.ts`
    // — mismo `sic_oficina`, mismo conjunto de especies, sólo cambia dónde vive la definición.
    rubroRv: null,
    filtroRv: FINANCIERAS.filtro,
    modoFiltroRv: FINANCIERAS.modo,
    nota:
      'Renta fija del sector Financiera y renta variable del rubro Office of Finance, que es ' +
      'como la SEC agrupa bancos, seguros y servicios financieros. ' +
      FINANCIERAS.nota,
  },
  {
    id: 'petroleo-gas',
    etiqueta: 'Petróleo y gas',
    filtrosRf: { sector: 'O&G' },
    rubroRv: null,
    nota:
      'Renta fija del sector O&G —que es literalmente Oil & Gas—. No filtra la renta variable: ' +
      'la SEC mete petroleras, mineras de oro, eléctricas y aerolíneas en la misma oficina ' +
      '(Energy & Transportation), y filtrar por ahí traería Barrick Gold y American Airlines.',
  },
  {
    id: 'energias-renovables',
    etiqueta: 'Energías renovables',
    filtrosRf: { sector: 'Energias Renovables' },
    rubroRv: null,
    nota:
      'Renta fija del sector Energias Renovables (9 emisiones, medido 10/08/2026). No filtra la renta variable: ' +
      'la SEC no tiene un rubro de renovables — las reparte según la actividad de cada empresa, ' +
      'y elegir uno de sus rubros sería decidir por la fuente.',
  },
  {
    id: 'tecnologicas',
    etiqueta: 'Tecnológicas',
    filtrosRf: null,
    // F-079: migrado de `rubroRv` inline a referenciar el preset compartido de `lib/presetsRv.ts`.
    rubroRv: null,
    filtroRv: TECNOLOGICAS.filtro,
    modoFiltroRv: TECNOLOGICAS.modo,
    nota:
      'Sólo renta variable, del rubro Office of Technology de la SEC: el universo de renta fija ' +
      'no tiene emisores tecnológicos, y Telecomunicaciones no es lo mismo. La grilla de bonos ' +
      'queda sin filtrar. ' +
      TECNOLOGICAS.nota,
  },
  {
    id: 'consumo-masivo',
    etiqueta: 'Consumo masivo',
    filtrosRf: { sector: 'Alimentos y Consumo' },
    rubroRv: null,
    nota:
      'Renta fija del sector Alimentos y Consumo (8 emisiones, medido 10/08/2026). No filtra la renta variable: la ' +
      'SEC no separa el consumo masivo del resto del comercio — su oficina de Trade & Services ' +
      'junta supermercados, ropa, restaurantes y alquiler de autos.',
  },
  {
    id: 'medicina',
    etiqueta: 'Medicina y salud',
    filtrosRf: null,
    // F-079: migrado de `rubroRv` inline a referenciar el preset compartido de `lib/presetsRv.ts`.
    rubroRv: null,
    filtroRv: MEDICINA.filtro,
    modoFiltroRv: MEDICINA.modo,
    nota:
      'Sólo renta variable, del rubro Office of Life Sciences de la SEC: no hay ningún emisor ' +
      'de salud en el universo de renta fija — Servicios agrupa otra cosa y usarlo sería filtrar ' +
      'por una categoría que no dice salud. La grilla de bonos queda sin filtrar. ' +
      MEDICINA.nota,
  },
  {
    id: 'agro',
    etiqueta: 'Agro',
    filtrosRf: { sector: 'Agro' },
    rubroRv: null,
    nota:
      'Renta fija del sector Agro (26 emisiones, medido 10/08/2026). No filtra la renta variable: la SEC reparte el ' +
      'agro entre manufactura de alimentos y comercio, sin un rubro propio.',
  },
  {
    // La primera temática que no se puede decir con un `sic_oficina`: la definición completa —qué
    // entra, qué queda afuera y por qué— es la de `PRESETS_RV`, y se referencia en vez de
    // reescribirse. Ver `PresetTematico.filtroRv`.
    id: 'metales-preciosos',
    etiqueta: METALES_PRECIOSOS.etiqueta,
    filtrosRf: null,
    rubroRv: null,
    filtroRv: METALES_PRECIOSOS.filtro,
    modoFiltroRv: METALES_PRECIOSOS.modo,
    nota:
      'Sólo renta variable. El universo de renta fija tiene un sector Mineria (2 emisiones, ' +
      'medido 10/08/2026) pero no declara qué metal extrae cada emisor, así que filtrar por ahí ' +
      'sería suponer que esas dos son de metales preciosos. La grilla de bonos queda sin filtrar. ' +
      METALES_PRECIOSOS.nota,
  },
  {
    id: 'cobertura-inflacion',
    etiqueta: 'Cobertura inflación',
    filtrosRf: { segmento: 'cer' },
    rubroRv: null,
    nota:
      'Renta fija ajustada por CER. No filtra la renta variable: una acción no ajusta por ' +
      'inflación por contrato, así que no hay un sector que cubra eso.',
  },
]

/** El aviso cuando ninguno de los papeles de esta clase tiene rubro conocido.
 *
 * Es el estado normal de las acciones argentinas: la SEC sólo lista las que tienen ADR (21 de 245),
 * y las demás esperan a la CNV (F-054). Decirlo evita que una lista vacía se lea como "no hay
 * papeles de este rubro" cuando lo que falta es el dato (regla 1). */
export const SIN_PERFILES_DE_EMPRESA =
  'sin rubro conocido para estos papeles: la SEC sólo clasifica las que tienen ADR, y el resto espera a la CNV'

export function presetPorId(id: string | null): PresetTematico | null {
  if (id === null) return null
  return PRESETS_TEMATICOS.find((preset) => preset.id === id) ?? null
}

/** Si el preset acota la renta variable de alguna de las dos maneras —por rubro suelto o por
 *  filtro multidimensional—. Los que no la acotan no se ofrecen en el selector de temática del
 *  armado asistido: elegirlos no cambiaría nada del bloque de CEDEARs, y la nota ya explica por qué
 *  no hay ninguna categoría de la fuente que los diga. */
export function filtraRentaVariable(preset: PresetTematico): boolean {
  return preset.rubroRv !== null || preset.filtroRv !== undefined
}

/**
 * Los filtros que deja aplicar un preset: parte de todo limpio y encima pone los suyos.
 *
 * Parte de `FILTROS_ARMADOR_VACIOS` y no de lo que estaba activo para que el resultado sea el mismo
 * sin importar desde dónde se lo aplique — un preset que a veces trae 40 papeles y a veces 3, según
 * qué había tocado antes, no sirve como atajo.
 */
export function filtrosDelPreset(preset: PresetTematico): FiltrosArmador {
  return { ...FILTROS_ARMADOR_VACIOS, ...(preset.filtrosRf ?? {}) }
}

/**
 * Si los filtros activos siguen siendo exactamente los que dejó el preset.
 *
 * Sirve para desmarcar el chip cuando el asesor tocó un filtro a mano: dejarlo prendido diría que
 * la grilla muestra la temática cuando ya muestra otra cosa.
 */
export function coincideConPreset(filtros: FiltrosArmador, preset: PresetTematico): boolean {
  const esperados = filtrosDelPreset(preset)
  return (Object.keys(esperados) as Array<keyof FiltrosArmador>).every((clave) => {
    const esperado = esperados[clave]
    const actual = filtros[clave]
    if (Array.isArray(esperado) && Array.isArray(actual)) {
      return esperado.length === actual.length && esperado.every((valor, i) => valor === actual[i])
    }
    return esperado === actual
  })
}
