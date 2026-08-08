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

  // F-013. Fija y fuera de `mercado` a propósito: la barra de estado del dato está en las seis
  // pantallas y una sola consulta las alimenta a todas. Si colgara de `mercado`, el refresh de
  // precios la invalidaría junto con todo lo demás — y lo que la barra tiene que declarar es
  // justamente **cuándo** entró ese refresh, así que se pide con su propio reloj.
  estadoDelDato: ['estado-del-dato'] as const,

  mercado: {
    todas: ['mercado'] as const,
    universo: (segmento: string) => ['mercado', 'universo', segmento] as const,
    instrumento: (ticker: string) => ['mercado', 'instrumento', ticker] as const,
    puntas: (ticker: string) => ['mercado', 'puntas', ticker] as const,
    // F-029: qué instrumento es cada ticker de una cartera cargada. Cuelga de mercado y no de
    // carteras porque lo que resuelve el ticker es el universo del día: si entra una corrida de
    // ingesta nueva, esto tiene que volver a preguntarse igual que un precio.
    resolucion: (firma: string) => ['mercado', 'resolucion', firma] as const,
    // F-015/F-016: la grilla de doce meses. Cuelga de mercado porque el calendario se calcula
    // sobre paridades y cronogramas del snapshot del día: un refresh de precios lo invalida.
    calendarioUniverso: ['mercado', 'calendario', 'universo'] as const,
    // La misma firma determinística de cartera que usa `resolucion` (F-029): mismas posiciones,
    // misma clave, así el POST-que-es-lectura se cachea como cualquier consulta.
    calendarioCartera: (firma: string) => ['mercado', 'calendario', 'cartera', firma] as const,
    // F-020: los topes de concentración de una cartera. Cuelga de mercado porque el veredicto se
    // calcula contra el universo del día —qué emisor, qué sector, qué ley tiene cada ticker—, así
    // que una corrida de ingesta nueva lo puede cambiar sin que la cartera se haya tocado. El
    // perfil entra en la clave: la misma cartera contra otro perfil es otra respuesta.
    concentracion: (firma: string, perfil: string) =>
      ['mercado', 'concentracion', perfil, firma] as const,
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
