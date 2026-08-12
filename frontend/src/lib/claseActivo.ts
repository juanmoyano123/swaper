/**
 * Etiquetas legibles para `clase_activo`, compartidas entre el monitor y la ficha de instrumento.
 *
 * Un solo mapa para las dos pantallas: si el rótulo de un soberano cambia, cambia en todos lados.
 * Las claves son las cinco clases que produce la clasificación de la ingesta (SUBMARKET_MAP del
 * backend). "Letra" no figura a propósito: ninguna fuente del pipeline distingue una LECAP de un
 * bono a tasa fija —ambas llegan como `bono_soberano`— y derivarlo del prefijo del ticker sería
 * inventar un dato.
 */

import { SIN_DATO } from './fmt'

export const ETIQUETA_CLASE: Record<string, string> = {
  bono_soberano: 'Soberano',
  bono_subsoberano: 'Subsoberano',
  on_corporativo: 'ON corporativa',
  accion: 'Acción',
  cedear: 'CEDEAR',
}

/** Una clase que la vista no reconoce se declara `s/d`, nunca queda la celda muda. */
export function etiquetaClase(clase: string): string {
  return ETIQUETA_CLASE[clase] ?? SIN_DATO
}
