/**
 * Todas las especies de un segmento, en una sola lista — F-038.
 *
 * El monitor ordena y filtra del lado del cliente para que la respuesta al asesor sea inmediata
 * (GWT-2), y eso exige tener el segmento entero, no una página de scroll manual. `usePaginaQuery`
 * existe para lo segundo y por eso no sirve acá: cortaría el universo justo cuando alguien quiere
 * ordenar por rendimiento y vería sólo las primeras filas cargadas.
 *
 * El filtro va en el pedido (`?segmento=`) y no después: pedir el universo entero para mirar un
 * segmento sería traer ~1.700 filas para descartar la mayoría en el navegador.
 */

import { useQuery } from '@tanstack/react-query'

import { TIEMPOS } from '@/app/queryClient'
import { apiFetch } from '@/lib/api/client'
import { claves } from '@/lib/api/queryKeys'
import { esquemaPagina } from '@/lib/api/schemas'

import { esquemaEspecie, type Especie } from '../lib/schema'

const LIMITE_POR_PAGINA = 200

/** 30 páginas de 200 son 6.000 especies: muy por encima del universo real (~1.700). Si se llega
 * acá es porque algo está mal —un cursor que no avanza, un segmento que creció sin aviso— y la
 * regla 1 del proyecto pide un error explícito, nunca un resultado cortado en silencio. */
const TOPE_PAGINAS = 30

const esquemaPaginaEspecie = esquemaPagina(esquemaEspecie)

async function traerSegmentoEntero(segmento: string): Promise<Especie[]> {
  const especies: Especie[] = []
  let cursor: string | null = null

  for (let pagina = 0; pagina < TOPE_PAGINAS; pagina++) {
    const busqueda = new URLSearchParams({ limit: String(LIMITE_POR_PAGINA), segmento })
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
    `El segmento "${segmento}" no terminó de traerse en ${TOPE_PAGINAS} páginas ` +
      `(${especies.length} especies leídas hasta acá): se corta la carga acá para no mostrar un ` +
      'universo truncado sin decirlo.',
  )
}

export function useUniversoSegmento(segmento: string) {
  return useQuery({
    queryKey: claves.mercado.universo(segmento),
    queryFn: () => traerSegmentoEntero(segmento),
    staleTime: TIEMPOS.mercado.staleTime,
  })
}
