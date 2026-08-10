/**
 * Rebalanceo pro-rata de los pesos de la cartera — Tanda 13, flujo RF/RV integrado.
 *
 * **El problema que resuelve.** Hasta acá, agregar una posición le daba `100/(n+1)` a la nueva y
 * dejaba a las demás intactas, así que la suma se iba de 100 apenas tocabas algo; y sacar una
 * posición dejaba el hueco sin repartir. En una cartera que mezcla renta fija y renta variable eso
 * es directamente confuso: el asesor sacaba toda la renta variable y el 25% liberado no volvía a
 * ninguna parte. Ahora agregar y quitar reparten proporcionalmente entre lo que queda, que es lo
 * que el asesor espera cuando dice "saco las acciones y lo mando todo a bonos".
 *
 * **Qué garantiza y qué no.** Después de agregar, quitar, equiponderar o cargar una cartera del
 * armado asistido, la suma de los pesos da exactamente 100,0 — no 99,9 ni 100,1. `fijarPeso` es la
 * única acción que puede romperlo, y lo hace a propósito: editar un porcentaje a mano es una
 * intención explícita sobre esa posición y no una orden de mover a las demás. Cuando la suma se
 * desvía, la cabecera de `CarteraEditable` ya lo marca en ámbar; ese es el aviso, no hace falta
 * otro.
 *
 * **Por qué décimas enteras.** Los pesos se muestran con un decimal, así que el reparto se hace en
 * unidades de 0,1 con el método del resto mayor: se reparten 1000 décimas entre las posiciones, y
 * el sobrante de la división va a las que quedaron con la fracción más grande. Sumar floats de a
 * 0,1 acumula error (el clásico 0,1 + 0,2 ≠ 0,3) y con quince posiciones el total termina en
 * 99,99999999999999; trabajar en enteros lo evita de raíz.
 */

/** Tolerancia para comparar la suma contra 100 en tests y asserts: es error de float, no de reparto. */
export const TOLERANCIA_SUMA = 1e-9

/** Décimas de punto porcentual que hay que repartir en total (100,0% = 1000 décimas). */
const DECIMAS_TOTALES = 1000

/** Debajo de esto, dos restos son el mismo resto: la diferencia es error de float, no de reparto. */
const TOLERANCIA_RESTO = 1e-9

/**
 * Reparte 100,0 puntos entre `pesos` respetando sus proporciones, a un decimal y sumando 100,0
 * exacto.
 *
 * Los pesos de entrada no necesitan sumar 100: se los toma como proporciones relativas. Un array
 * vacío devuelve vacío. Si todos los pesos son cero (o la suma es negativa, que no debería pasar)
 * no hay proporción de la que agarrarse y se reparte en partes iguales.
 *
 * El sobrante de la división entera se asigna a las posiciones con mayor resto; si dos empatan,
 * gana la de mayor peso, y si también empatan, la que entró antes. Ese orden de desempate es lo que
 * hace el resultado reproducible: los mismos pesos de entrada dan siempre la misma salida.
 */
export function normalizarA100(pesos: readonly number[]): number[] {
  if (pesos.length === 0) return []

  const suma = pesos.reduce((acumulado, peso) => acumulado + peso, 0)
  const proporciones =
    suma > 0 ? pesos.map((peso) => (peso / suma) * DECIMAS_TOTALES) : pesos.map(() => DECIMAS_TOTALES / pesos.length)

  const pisos = proporciones.map((decimas) => Math.floor(decimas))
  const asignadas = pisos.reduce((acumulado, piso) => acumulado + piso, 0)
  let sobrante = DECIMAS_TOTALES - asignadas

  // El sobrante nunca puede superar la cantidad de posiciones: cada una aporta a lo sumo una décima
  // de resto. Se ordenan los índices por resto y se le suma una décima a los primeros.
  //
  // Los restos se comparan con tolerancia y no con `>`: dos posiciones que "deberían" pesar lo
  // mismo pueden diferir en el último bit del float según de qué cuenta salió cada una (33,33333…3
  // contra 33,33333…36), y sin la tolerancia esa basura decide quién se lleva la décima. Con ella,
  // los empates reales caen al desempate declarado: mayor peso primero, y a igual peso, la que
  // entró antes.
  const porResto = proporciones
    .map((decimas, indice) => ({ indice, resto: decimas - Math.floor(decimas), peso: decimas }))
    .sort((a, b) => {
      const diferenciaDeResto = b.resto - a.resto
      if (Math.abs(diferenciaDeResto) > TOLERANCIA_RESTO) return diferenciaDeResto
      const diferenciaDePeso = b.peso - a.peso
      if (Math.abs(diferenciaDePeso) > TOLERANCIA_RESTO) return diferenciaDePeso
      return a.indice - b.indice
    })

  for (const { indice } of porResto) {
    if (sobrante <= 0) break
    pisos[indice] += 1
    sobrante -= 1
  }

  return pisos.map((decimas) => decimas / 10)
}

/** Una posición vista por el rebalanceo: sólo le importa el peso. */
interface ConPeso {
  peso: number
}

/**
 * Agrega una posición al final y reparte: la nueva se queda con `pesoPedido` —o con `100/(n+1)` si
 * no se pide ninguno en particular— y las que ya estaban se achican proporcionalmente para hacerle
 * lugar.
 *
 * Sobre una cartera que sumaba 100 y sin peso pedido, esto equivale a escalar a todas por
 * `n/(n+1)`. Sobre una que venía desviada (porque el asesor editó pesos a mano), además la deja
 * sumando 100 — agregar es un buen momento para reconciliar, y dejarla desviada sería arrastrar el
 * problema.
 */
export function agregarConProRata<T extends ConPeso>(
  posiciones: readonly T[],
  nueva: T,
  pesoPedido?: number,
): T[] {
  const pesoNuevo = pesoPedido ?? DECIMAS_TOTALES / 10 / (posiciones.length + 1)
  const sumaPrevia = posiciones.reduce((acumulado, posicion) => acumulado + posicion.peso, 0)

  const exactos =
    sumaPrevia > 0
      ? [
          ...posiciones.map((posicion) => (posicion.peso / sumaPrevia) * (100 - pesoNuevo)),
          pesoNuevo,
        ]
      : [...posiciones.map(() => pesoNuevo), pesoNuevo]

  const repartidos = normalizarA100(exactos)
  const todas = [...posiciones, nueva]
  return todas.map((posicion, indice) => ({ ...posicion, peso: repartidos[indice] }))
}

/**
 * Saca las posiciones que cumplan `sacar` y reparte lo que liberaron entre las que quedan,
 * proporcionalmente a lo que ya pesaban.
 *
 * Sacar la última posición deja la cartera vacía, no una cartera de un elemento con 100%.
 */
export function quitarConProRata<T extends ConPeso>(
  posiciones: readonly T[],
  sacar: (posicion: T) => boolean,
): T[] {
  const restantes = posiciones.filter((posicion) => !sacar(posicion))
  if (restantes.length === 0) return []

  const repartidos = normalizarA100(restantes.map((posicion) => posicion.peso))
  return restantes.map((posicion, indice) => ({ ...posicion, peso: repartidos[indice] }))
}

/**
 * Pone a todas las posiciones el mismo peso, con el residuo de la división repartido por resto
 * mayor: con tres posiciones da 33,4 / 33,3 / 33,3 y no tres veces 33,3 (que sumaría 99,9).
 */
export function equiponderarPesos<T extends ConPeso>(posiciones: readonly T[]): T[] {
  if (posiciones.length === 0) return []
  const repartidos = normalizarA100(posiciones.map(() => 1))
  return posiciones.map((posicion, indice) => ({ ...posicion, peso: repartidos[indice] }))
}
