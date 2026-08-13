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
 * Hasta esa fecha eran los sectores de Yahoo Finance. Yahoo bloqueó el endpoint de perfil y la
 * tabla quedó con **cero** sectores cargados: cada preset temático filtraba contra un campo vacío y
 * devolvía cero papeles sin que se entendiera por qué. Las dos taxonomías no se mezclan — ver el
 * docstring de `app/armado/renta_variable.py`.
 *
 * **Dos presets perdieron su filtro de renta variable en el cambio, y es a propósito.** La SEC
 * agrupa por oficina, y ninguna de sus oficinas dice "petróleo" ni "consumo masivo":
 * `Office of Energy & Transportation` mezcla petroleras (41 especies) con mineras de oro (46),
 * eléctricas (22) y aerolíneas (25) — medido el 13/08/2026 —, y `Office of Trade & Services` es
 * comercio minorista de todo tipo. Filtrar "Petróleo y gas" por esa oficina traería Barrick Gold y
 * American Airlines, que es exactamente lo que un preset temático no puede hacer.
 */

import { FILTROS_ARMADOR_VACIOS, type FiltrosArmador } from './filtros'

export interface PresetTematico {
  id: string
  etiqueta: string
  /** Qué filtros de la grilla de renta fija precarga. `null` = ninguno aplica, y la nota dice por qué. */
  filtrosRf: Partial<FiltrosArmador> | null
  /** Rubro de la SEC (`sic_oficina`), literal y sin normalizar, para el bloque de renta variable.
   *  `null` = el preset no filtra la renta variable, y la nota dice por qué. */
  rubroRv: string | null
  /** Qué hace y qué no. Se muestra como tooltip: un atajo que no explica qué precargó es magia. */
  nota: string
}

export const PRESETS_TEMATICOS: PresetTematico[] = [
  {
    id: 'financieras',
    etiqueta: 'Financieras',
    filtrosRf: { sector: 'Financiera' },
    rubroRv: 'Office of Finance',
    nota:
      'Renta fija del sector Financiera y renta variable del rubro Office of Finance, que es ' +
      'como la SEC agrupa bancos, seguros y servicios financieros.',
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
      'Renta fija del sector Energias Renovables (9 emisiones). No filtra la renta variable: ' +
      'la SEC no tiene un rubro de renovables — las reparte según la actividad de cada empresa, ' +
      'y elegir uno de sus rubros sería decidir por la fuente.',
  },
  {
    id: 'tecnologicas',
    etiqueta: 'Tecnológicas',
    filtrosRf: null,
    rubroRv: 'Office of Technology',
    nota:
      'Sólo renta variable, del rubro Office of Technology de la SEC: el universo de renta fija ' +
      'no tiene emisores tecnológicos, y Telecomunicaciones no es lo mismo. La grilla de bonos ' +
      'queda sin filtrar.',
  },
  {
    id: 'consumo-masivo',
    etiqueta: 'Consumo masivo',
    filtrosRf: { sector: 'Alimentos y Consumo' },
    rubroRv: null,
    nota:
      'Renta fija del sector Alimentos y Consumo (8 emisiones). No filtra la renta variable: la ' +
      'SEC no separa el consumo masivo del resto del comercio — su oficina de Trade & Services ' +
      'junta supermercados, ropa, restaurantes y alquiler de autos.',
  },
  {
    id: 'medicina',
    etiqueta: 'Medicina y salud',
    filtrosRf: null,
    rubroRv: 'Office of Life Sciences',
    nota:
      'Sólo renta variable, del rubro Office of Life Sciences de la SEC: no hay ningún emisor ' +
      'de salud en el universo de renta fija — Servicios agrupa otra cosa y usarlo sería filtrar ' +
      'por una categoría que no dice salud. La grilla de bonos queda sin filtrar.',
  },
  {
    id: 'agro',
    etiqueta: 'Agro',
    filtrosRf: { sector: 'Agro' },
    rubroRv: null,
    nota:
      'Renta fija del sector Agro (26 emisiones). No filtra la renta variable: la SEC reparte el ' +
      'agro entre manufactura de alimentos y comercio, sin un rubro propio.',
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
