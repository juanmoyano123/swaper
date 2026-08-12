/**
 * Todas las especies del universo, en una sola lista — F-018.
 *
 * No hay un endpoint "dame estas N especies": para armar el `Map<ticker, Especie>` que necesita
 * cualquier pantalla que valúe una cartera (armador o diagnóstico) hay que traer el universo
 * entero una vez y quedarse con lo que hace falta. Es el mismo bucle de cursor que
 * `features/monitor/hooks/useUniversoSegmento.ts` (F-038), portado en vez de importado — ese hook
 * siempre filtra por `?segmento=`, mientras que acá se pide el universo sin filtrar.
 */

import { apiFetch } from '@/lib/api/client'
import { esquemaPagina } from '@/lib/api/schemas'

import { esquemaEspecie, type Especie } from './esquemaEspecie'

const LIMITE_POR_PAGINA = 200

/** Mismo criterio que el tope del monitor: muy por encima del universo real (~1.700 especies). */
const TOPE_PAGINAS = 30

const esquemaPaginaEspecie = esquemaPagina(esquemaEspecie)

export async function traerUniversoEntero(): Promise<Especie[]> {
  const especies: Especie[] = []
  let cursor: string | null = null

  for (let pagina = 0; pagina < TOPE_PAGINAS; pagina++) {
    const busqueda = new URLSearchParams({ limit: String(LIMITE_POR_PAGINA) })
    if (cursor) busqueda.set('cursor', cursor)

    const respuesta = await apiFetch(
      `/api/v1/universo/emisiones/especies?${busqueda.toString()}`,
      esquemaPaginaEspecie,
    )
    especies.push(...respuesta.items)
    cursor = respuesta.next_cursor
    if (cursor === null) return especies
  }

  throw new Error(
    `El universo no terminó de traerse en ${TOPE_PAGINAS} páginas ` +
      `(${especies.length} especies leídas hasta acá): se corta la carga acá para no mostrar un ` +
      'universo truncado sin decirlo.',
  )
}
