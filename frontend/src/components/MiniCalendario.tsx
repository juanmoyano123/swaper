/**
 * Mini-calendario de doce celdas: en qué meses paga un papel, leído de un vistazo.
 *
 * Es base común de la tanda 6 y por eso vive en `components/` y no dentro de una feature: lo usan
 * las filas del monitor (F-038) y las tarjetas comparables del detalle de mes (F-016), y si cada
 * una tuviera su versión las dos pantallas dibujarían el mismo dato distinto.
 *
 * Las celdas se pintan con lo que el dato dice y nada más: `renta` en acento, `atencion` en ámbar
 * (amortizaciones, dividendos estimados — lo que el design system marca con `--ac2`), y `null`
 * queda transparente con borde. Una celda vacía es un mes sin pagos, que es dato, no ausencia.
 */

export type CeldaMes = 'renta' | 'atencion' | null

/** Índice 0 = el primer mes de la ventana que muestre la pantalla (no necesariamente enero). */
export function MiniCalendario({
  meses,
  etiqueta,
}: {
  /** Exactamente 12 valores; si llegan menos, las celdas que faltan se dibujan vacías. */
  meses: readonly CeldaMes[]
  /** Texto accesible; por defecto describe cuántos meses pagan. */
  etiqueta?: string
}) {
  const celdas = Array.from({ length: 12 }, (_, i) => meses[i] ?? null)
  const conPago = celdas.filter((c) => c !== null).length
  return (
    <div
      role="img"
      aria-label={etiqueta ?? `Paga en ${conPago} de 12 meses`}
      style={{ display: 'flex', gap: 2 }}
    >
      {celdas.map((celda, i) => (
        <span
          // eslint-disable-next-line react/no-array-index-key -- la posición ES la identidad: celda i = mes i
          key={i}
          style={{
            width: 7,
            height: 16,
            borderRadius: 2,
            background:
              celda === 'renta' ? 'var(--ac)' : celda === 'atencion' ? 'var(--ac2)' : 'transparent',
            border: celda === null ? '1px solid var(--lin)' : '1px solid transparent',
          }}
        />
      ))}
    </div>
  )
}
