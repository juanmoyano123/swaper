/**
 * Claves de las consultas, agrupadas por dominio.
 *
 * Son jerárquicas para que la invalidación funcione por prefijo. El contrato para el refresh de
 * precios —que implementan F-008 y F-013— es una sola línea:
 *
 *     queryClient.invalidateQueries({ queryKey: claves.mercado.todas })
 *
 * y con eso se recargan universo, precios, puntas y todo lo que cuelgue de mercado. Sin esta
 * jerarquía, cada feature nueva tendría que acordarse de agregar su clave a la lista del refresh,
 * y la que se olvide muestra precios viejos sin que nadie lo note.
 */

export const claves = {
  salud: ['salud'] as const,

  mercado: {
    todas: ['mercado'] as const,
    universo: (segmento: string) => ['mercado', 'universo', segmento] as const,
    instrumento: (ticker: string) => ['mercado', 'instrumento', ticker] as const,
    puntas: (ticker: string) => ['mercado', 'puntas', ticker] as const,
  },

  // Condiciones de emisión y demás dato curado: cambia por ingesta, no por paso del tiempo.
  referencia: {
    todas: ['referencia'] as const,
    condiciones: (ticker: string) => ['referencia', 'condiciones', ticker] as const,
  },

  carteras: {
    todas: ['carteras'] as const,
    detalle: (id: string) => ['carteras', 'detalle', id] as const,
  },
} as const
