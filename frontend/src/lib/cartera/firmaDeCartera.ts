/**
 * La firma de una cartera, para la clave de caché de `useCalendarioCartera` — mismo patrón que
 * `features/cartera-resolucion/lib/resolverCartera.ts::firmaDeCartera` (F-029), portado en vez de
 * importado: esa carpeta pertenece a otra feature.
 *
 * Se firma con `monto` y no con `peso`: lo que efectivamente viaja en el cuerpo del POST es el
 * `invertido` que calculó cada consumidor, y ese es el número que determina si la respuesta
 * cacheada sigue sirviendo. Dos carteras con el mismo peso pedido pero precios distintos (otro
 * refresh de mercado) tienen `invertido` distinto y necesitan volver a pedirse.
 */

export function firmaDeCartera(posiciones: { ticker: string; monto: number }[]): string {
  return posiciones.map((p) => `${p.ticker}:${p.monto}`).join('|')
}
