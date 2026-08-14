/**
 * Motor genérico de filtros en cascada (facetado bidireccional) — 14/08/2026.
 *
 * Nace del picker de CEDEARs del armador (rubro ⇄ eslabón, commit `e4473bc`) y de la barra de la
 * cordillera (ley/sector/calificación/emisor), y se generaliza acá porque el monitor lo necesita
 * también y **`features/monitor/**` y `features/armador/**` tienen prohibido importarse entre sí**
 * (precedente F-017/F-018/F-038): lo genuinamente compartido sube a `lib/`, no se porta dos veces
 * — el mismo movimiento que ya unificó `lib/cartera/esquemaEspecie.ts` para evitar dos contratos
 * que puedan desalinearse.
 *
 * ## El problema que resuelve
 *
 * Una pantalla con varios selects sobre la misma lista, donde elegir un valor en uno debería
 * acotar las opciones de los demás — pero **sin que ningún select se acote a sí mismo** (si
 * "Sector" sólo ofreciera lo que ya eligió Sector, no habría forma de cambiar de idea) y **sin que
 * una selección imposible envenene a las demás** (un preset con `sector: 'Agro'` sobre una lista
 * sin ningún ítem de Agro no puede dejar el select de Emisor vacío).
 *
 * ## Cómo lo resuelve
 *
 * Cada dimensión es una `Faceta<T>`: una selección (0..n valores, disyunción — un multiselect de
 * uno es un select normal), y dos funciones puras sobre el ítem (`coincide`, `valores`). El orden
 * del array de facetas **es** el orden de validación, de lo general a lo específico: hace falta un
 * orden porque dos selecciones incompatibles se invalidarían mutuamente sin él, y con un orden gana
 * la más general — la más específica queda apagada y declarada, no las dos.
 *
 * `facetar()` hace dos pasadas:
 * 1. **Validar**: acepta las selecciones de a una, en orden, y cada una entra sólo si junto a las
 *    ya aceptadas todavía deja algún ítem en pie. La que no, queda afuera de `efectivas` y se
 *    declara en `apagadas`.
 * 2. **Ofrecer opciones**: para cada faceta, los valores que existen sobre lo que sobrevive a
 *    `pasaBase` y a **todas las demás facetas ya validadas, menos la propia** (*leave-one-out*).
 *    Dejar afuera la faceta propia es lo que le permite pivotar; que cada opción salga de lo que
 *    sobrevive al resto es lo que garantiza que ninguna opción visible dé una lista vacía.
 *
 * Nada se sincroniza con `setState`: todo se deriva de `items`/`dimensiones`/`pasaBase` en cada
 * llamada. Dos selects que se corrigen entre sí a fuerza de efectos es una carrera perdida.
 */

export interface Faceta<T> {
  /** Identifica la dimensión en `opciones`/`efectivas`/`apagadas`. */
  id: string
  /** Los valores elegidos (0..n; un select de valor único se modela con 0 o 1 elemento). */
  seleccion: string[]
  /** `true` si el ítem cumple ese valor de la dimensión. Debe devolver `false` cuando al ítem le
   *  falta el dato que haría falta para decidir — nunca asumirlo (regla 1 del dominio: un dato que
   *  no existe no puede afirmarse que cumple un filtro activo). */
  coincide(item: T, valor: string): boolean
  /** Los valores que el ítem aporta como opción posible (0..n). Los centinelas de "dato no
   *  informado" (si la dimensión los tiene) salen de acá, no de un flag aparte. */
  valores(item: T): string[]
}

export interface SeleccionApagada {
  dimension: string
  valor: string
}

export interface ResultadoFacetado {
  /** Valores ofrecibles por dimensión, ya acotados (leave-one-out sobre las efectivas). */
  opciones: Map<string, string[]>
  /** La selección de cada dimensión tras quitar lo que no tiene respaldo. Lo que realmente filtra. */
  efectivas: Map<string, string[]>
  /** Lo que se pidió pero no tiene respaldo bajo el resto — para declararlo, no ocultarlo. */
  apagadas: SeleccionApagada[]
}

function pasaFaceta<T>(item: T, faceta: Faceta<T>, seleccion: string[]): boolean {
  return seleccion.length === 0 || seleccion.some((valor) => faceta.coincide(item, valor))
}

/** `true` si el ítem pasa `pasaBase` y todas las facetas de `efectivas`, salvo la de `excepto` (si
 *  se da: `null` no excluye ninguna). */
function pasaTodasMenos<T>(
  item: T,
  dimensiones: Array<Faceta<T>>,
  efectivas: Map<string, string[]>,
  pasaBase: (item: T) => boolean,
  excepto: string | null,
): boolean {
  if (!pasaBase(item)) return false
  for (const faceta of dimensiones) {
    if (faceta.id === excepto) continue
    if (!pasaFaceta(item, faceta, efectivas.get(faceta.id) ?? [])) return false
  }
  return true
}

/**
 * Facetado en cascada: ver el docstring del módulo para la semántica completa.
 *
 * `pasaBase` son los filtros que siempre aplican y nunca se apagan (umbrales, checkboxes, o una
 * elección explícita y visible como una pestaña de segmento) — lo que no está modelado como
 * `Faceta` porque esconder su efecto sería mentir sobre lo que se está mirando.
 */
export function facetar<T>(
  items: T[],
  dimensiones: Array<Faceta<T>>,
  pasaBase: (item: T) => boolean,
): ResultadoFacetado {
  const sobrevivenCon = (efectivas: Map<string, string[]>, excepto: string | null) =>
    items.some((item) => pasaTodasMenos(item, dimensiones, efectivas, pasaBase, excepto))

  // 1. Validar: se aceptan las selecciones de a una, en el orden de `dimensiones`.
  const efectivas = new Map<string, string[]>()
  for (const faceta of dimensiones) efectivas.set(faceta.id, [])

  for (const faceta of dimensiones) {
    const conRespaldo = faceta.seleccion.filter((valor) => {
      const candidata = new Map(efectivas)
      candidata.set(faceta.id, [valor])
      return sobrevivenCon(candidata, null)
    })
    if (conRespaldo.length > 0) efectivas.set(faceta.id, conRespaldo)
  }

  // 2. Opciones: leave-one-out sobre las efectivas ya validadas.
  const opciones = new Map<string, string[]>()
  for (const faceta of dimensiones) {
    const valores = new Set<string>()
    for (const item of items) {
      if (!pasaTodasMenos(item, dimensiones, efectivas, pasaBase, faceta.id)) continue
      for (const valor of faceta.valores(item)) valores.add(valor)
    }
    opciones.set(faceta.id, [...valores])
  }

  // 3. Apagadas: lo que se pidió y no quedó en `efectivas`.
  const apagadas: SeleccionApagada[] = []
  for (const faceta of dimensiones) {
    const activas = efectivas.get(faceta.id) ?? []
    for (const valor of faceta.seleccion) {
      if (!activas.includes(valor)) apagadas.push({ dimension: faceta.id, valor })
    }
  }

  return { opciones, efectivas, apagadas }
}
