/**
 * Selector de moneda de cotización: una sola a la vez, nunca dos.
 *
 * Es el mismo mecanismo que `SelectorSegmento` y por la misma razón, un eje más abajo. La regla 2
 * del dominio impide mezclar rendimientos de distinta naturaleza; la regla 3 impide comparar
 * magnitudes de distinta moneda sin normalizar. Con las tres especies de una emisión conviviendo en
 * la grilla, la columna de volumen mezclaba pesos con dólares y el orden por liquidez ponía arriba
 * a las especies en pesos por el tipo de cambio y no por operarse más.
 *
 * **Eligiendo una moneda el problema desaparece en vez de resolverse.** La lista entera queda en la
 * misma unidad por construcción, el volumen se puede mostrar crudo —sin convertir nada, sin
 * interpretar nada— y de paso se ve una fila por emisión en vez de tres. Es lo que hace el monitor
 * de mesa que se tomó de referencia; Balanz llega a lo mismo con un multi-select, que permite
 * volver a mezclar.
 *
 * **Las etiquetas son los códigos crudos de BYMA** (`denominationCcy`): `ARS`, `USD`, `EXT`. No se
 * traducen a "pesos / MEP / cable" porque BYMA sólo documenta los dos primeros —son ISO 4217— y
 * `EXT` es vocabulario propio de la fuente sin publicar. Lo medido sugiere que es el cable, y
 * sugerir no es declarar (regla 11). El asesor ve el código y la aclaración; el que quiera saber
 * qué es va al ticker, cuya última letra sí conoce.
 */

const ORDEN_MONEDAS = ['ARS', 'USD', 'EXT']

/** Lo que la fuente no declara. Se muestra igual, con su nombre, para que el hueco no sea invisible. */
export const SIN_MONEDA_DECLARADA = '(sin declarar)'

/** Aclaración de lo que significa cada chip. Va al lado del selector, no adentro de la tabla. */
export const NOTA_MONEDA =
  'Denominación declarada por BYMA, sin traducir. Los precios y volúmenes de la tabla están en la moneda elegida.'

const DETALLE_POR_MONEDA: Record<string, string> = {
  ARS: 'Pesos argentinos (ISO 4217).',
  USD: 'Dólares estadounidenses (ISO 4217).',
  EXT: 'Código propio de BYMA, sin documentar: la fuente no publica qué denota. Su volumen no se convierte a dólares en ningún lado de la aplicación.',
  [SIN_MONEDA_DECLARADA]: 'La fuente no declaró denominación para estas especies.',
}

/** Cuántas especies hay de cada moneda, en el orden de los chips. Sólo las que tienen al menos una. */
export function contarPorMoneda(
  especies: readonly { moneda_cotizacion: string | null }[],
): { moneda: string; especies: number }[] {
  const conteo = new Map<string, number>()
  for (const especie of especies) {
    const clave = especie.moneda_cotizacion ?? SIN_MONEDA_DECLARADA
    conteo.set(clave, (conteo.get(clave) ?? 0) + 1)
  }
  return [...conteo.entries()]
    .map(([moneda, cantidad]) => ({ moneda, especies: cantidad }))
    .sort((a, b) => {
      const ia = ORDEN_MONEDAS.indexOf(a.moneda)
      const ib = ORDEN_MONEDAS.indexOf(b.moneda)
      return (ia === -1 ? ORDEN_MONEDAS.length : ia) - (ib === -1 ? ORDEN_MONEDAS.length : ib)
    })
}

/**
 * La moneda que conviene mostrar al abrir un segmento, entre las que de verdad tienen especies.
 *
 * `preferida` es lo que el segmento pide —dólares en el hard dollar, pesos en las curvas en pesos—
 * pero no se impone: si no hay ninguna especie en esa moneda, la tabla arrancaría vacía sobre un
 * universo que sí tiene datos, y eso se lee como "no hay nada" cuando lo que pasa es otra cosa.
 * En ese caso gana la moneda con más especies, que es un desempate del conteo y no un juicio.
 */
export function monedaInicial(
  disponibles: readonly { moneda: string; especies: number }[],
  preferida: string,
): string | null {
  if (disponibles.length === 0) return null
  const conLaPreferida = disponibles.find((d) => d.moneda === preferida && d.especies > 0)
  if (conLaPreferida) return conLaPreferida.moneda
  return [...disponibles].sort((a, b) => b.especies - a.especies)[0].moneda
}

export function SelectorMoneda({
  disponibles,
  activa,
  onCambio,
}: {
  /** Monedas presentes en el segmento con su conteo, tal como las devuelve `contarPorMoneda`. */
  disponibles: readonly { moneda: string; especies: number }[]
  activa: string
  onCambio: (moneda: string) => void
}) {
  if (disponibles.length === 0) return null

  return (
    <div style={{ margin: '10px 0 2px' }}>
      <div role="radiogroup" aria-label="Moneda de cotización" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        {disponibles.map(({ moneda, especies }) => {
          const esActiva = moneda === activa
          return (
            <button
              key={moneda}
              type="button"
              role="radio"
              aria-checked={esActiva}
              onClick={() => onCambio(moneda)}
              title={DETALLE_POR_MONEDA[moneda]}
              style={{
                font: `${esActiva ? 600 : 400} 12px/1 inherit`,
                color: esActiva ? 'var(--tx)' : 'var(--dim)',
                background: esActiva ? 'var(--pan2)' : 'transparent',
                border: `1px solid ${esActiva ? 'var(--ac)' : 'var(--lin)'}`,
                borderRadius: 3,
                padding: '5px 10px',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {moneda}{' '}
              <span className="mono" style={{ fontSize: 11, color: 'var(--dim)' }}>{especies}</span>
            </button>
          )
        })}
      </div>
      <p style={{ margin: '5px 0 0', fontSize: 11, color: 'var(--dim)' }}>{NOTA_MONEDA}</p>
    </div>
  )
}
