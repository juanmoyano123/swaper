/**
 * Pestañas de primer nivel del Monitor: Renta fija / Renta variable — reordenación del 14/08/2026.
 *
 * Antes la barra única del monitor mezclaba tipo de tasa, crédito y renta variable en un solo nivel
 * plano; ver el header de `MonitorPage.tsx` para el detalle completo de la jerarquía nueva. Este
 * componente es el corte más grueso, y por eso se ve jerárquicamente superior al de segmento
 * (`SelectorSegmento`): tipografía más grande, subrayado más grueso. No comparte componente con
 * `SelectorSegmento` a propósito — comparten muy poco (acá no hay orden que calcular ni conteo por
 * especie) y forzarlos a la misma pieza mezclaría dos niveles distintos en una sola API.
 *
 * Local a esta feature: ninguna otra pantalla necesita la partición renta fija / renta variable
 * como pestañas — el armador la resuelve de otra forma (`CLAVES_RENTA_VARIABLE` para excluir).
 */

export type Familia = 'renta_fija' | 'renta_variable'

const NOMBRE_FAMILIA: Record<Familia, string> = {
  renta_fija: 'Renta fija',
  renta_variable: 'Renta variable',
}

export function SelectorFamilia({
  activa,
  onCambio,
  disponibles,
}: {
  activa: Familia
  onCambio: (familia: Familia) => void
  /** Familias con datos hoy, en el orden en que se muestran. Con menos de dos no hay nada que
   *  elegir: una barra de una sola pestaña grande no navega a ningún lado. */
  disponibles: readonly Familia[]
}) {
  if (disponibles.length < 2) return null

  return (
    <nav
      aria-label="Familia de activos"
      style={{
        display: 'flex',
        gap: 2,
        borderBottom: '1px solid var(--lin)',
        marginBottom: 4,
      }}
    >
      {disponibles.map((familia) => {
        const esActiva = familia === activa
        return (
          <button
            key={familia}
            type="button"
            onClick={() => onCambio(familia)}
            aria-current={esActiva ? 'true' : undefined}
            style={{
              font: '600 13.5px/1 inherit',
              color: esActiva ? 'var(--tx)' : 'var(--dim)',
              background: 'none',
              border: 'none',
              borderBottom: esActiva ? '3px solid var(--ac)' : '3px solid transparent',
              padding: '10px 16px 9px',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {NOMBRE_FAMILIA[familia]}
          </button>
        )
      })}
    </nav>
  )
}
