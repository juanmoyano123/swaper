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
 * otra cosa. Al revés pasa lo mismo: Agro y Energias Renovables existen en renta fija pero Yahoo no
 * les da un sector propio, así que esos presets no filtran renta variable en vez de elegir por la
 * fuente cuál de sus categorías "es" el rubro (regla 11).
 *
 * **Petróleo y renovables van separados a propósito.** El universo de renta fija las clasifica
 * distinto (`O&G` contra `Energias Renovables`) y juntarlas bajo una etiqueta "Energía" haría que
 * un preset devuelva emisiones de un rubro que el asesor no pidió.
 *
 * **Los sectores de renta variable son los de Yahoo Finance**, que llegan por el job de
 * enriquecimiento (`POST /api/v1/jobs/perfiles-renta-variable`). Al 10/08/2026 ese job todavía no
 * corrió y `perfil_renta_variable` está vacía, así que estos filtros no van a encontrar nada hasta
 * que corra: la UI declara ese estado (`SIN_PERFILES_DE_EMPRESA`) en vez de mostrar una lista vacía
 * que se lea como "no hay papeles de este rubro".
 */

import { FILTROS_ARMADOR_VACIOS, type FiltrosArmador } from './filtros'

export interface PresetTematico {
  id: string
  etiqueta: string
  /** Qué filtros de la grilla de renta fija precarga. `null` = ninguno aplica, y la nota dice por qué. */
  filtrosRf: Partial<FiltrosArmador> | null
  /** Sector de Yahoo, literal y sin normalizar, para el bloque de renta variable. `null` = el
   *  preset no filtra la renta variable. */
  sectorRv: string | null
  /** Qué hace y qué no. Se muestra como tooltip: un atajo que no explica qué precargó es magia. */
  nota: string
}

export const PRESETS_TEMATICOS: PresetTematico[] = [
  {
    id: 'financieras',
    etiqueta: 'Financieras',
    filtrosRf: { sector: 'Financiera' },
    sectorRv: 'Financial Services',
    nota: 'Renta fija del sector Financiera y renta variable del sector Financial Services de Yahoo.',
  },
  {
    id: 'petroleo-gas',
    etiqueta: 'Petróleo y gas',
    filtrosRf: { sector: 'O&G' },
    sectorRv: 'Energy',
    nota:
      'Renta fija del sector O&G —que es literalmente Oil & Gas— y renta variable del sector ' +
      'Energy de Yahoo. Las renovables van aparte: el universo las clasifica por separado.',
  },
  {
    id: 'energias-renovables',
    etiqueta: 'Energías renovables',
    filtrosRf: { sector: 'Energias Renovables' },
    sectorRv: null,
    nota:
      'Renta fija del sector Energias Renovables (9 emisiones). No filtra la renta variable: ' +
      'Yahoo no tiene un sector de renovables — las reparte entre Energy y Utilities según la ' +
      'empresa, y elegir una de las dos sería decidir por la fuente.',
  },
  {
    id: 'tecnologicas',
    etiqueta: 'Tecnológicas',
    filtrosRf: null,
    sectorRv: 'Technology',
    nota:
      'Sólo renta variable: el universo de renta fija no tiene emisores tecnológicos, y ' +
      'Telecomunicaciones no es lo mismo. La grilla de bonos queda sin filtrar.',
  },
  {
    id: 'consumo-masivo',
    etiqueta: 'Consumo masivo',
    filtrosRf: { sector: 'Alimentos y Consumo' },
    sectorRv: 'Consumer Defensive',
    nota:
      'Renta fija del sector Alimentos y Consumo (8 emisiones) y renta variable del sector ' +
      'Consumer Defensive de Yahoo, que es el consumo no cíclico. Consumer Cyclical queda ' +
      'afuera: es consumo discrecional, otra cosa.',
  },
  {
    id: 'medicina',
    etiqueta: 'Medicina y salud',
    filtrosRf: null,
    sectorRv: 'Healthcare',
    nota:
      'Sólo renta variable: no hay ningún emisor de salud en el universo de renta fija — ' +
      'Servicios agrupa otra cosa y usarlo sería filtrar por una categoría que no dice salud. ' +
      'La grilla de bonos queda sin filtrar.',
  },
  {
    id: 'agro',
    etiqueta: 'Agro',
    filtrosRf: { sector: 'Agro' },
    sectorRv: null,
    nota:
      'Renta fija del sector Agro (26 emisiones). No filtra la renta variable: Yahoo reparte el ' +
      'agro entre Consumer Defensive y Basic Materials, sin un sector propio.',
  },
  {
    id: 'cobertura-inflacion',
    etiqueta: 'Cobertura inflación',
    filtrosRf: { segmento: 'cer' },
    sectorRv: null,
    nota:
      'Renta fija ajustada por CER. No filtra la renta variable: una acción no ajusta por ' +
      'inflación por contrato, así que no hay un sector que cubra eso.',
  },
]

/** El aviso cuando el universo de renta variable todavía no tiene perfiles de empresa cargados. */
export const SIN_PERFILES_DE_EMPRESA =
  'sin perfiles de empresa cargados todavía: el filtro por rubro no va a encontrar nada hasta que corra el job de enriquecimiento'

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
