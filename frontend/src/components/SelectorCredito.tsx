/**
 * Selector de crédito dentro de un segmento de renta fija: Todos, o un solo crédito a la vez.
 *
 * Reordenación del monitor del 14/08/2026: antes sólo el dólar hard se abría en pestañas propias
 * de Soberanos/Subsoberanos/ONs (`SEGMENTO_POR_CREDITO` en `SelectorSegmento.tsx`), y las cinco
 * pestañas restantes lo dejaban todo junto. Este componente generaliza esa partición a cualquier
 * segmento, como un chip un nivel debajo de la pestaña de tipo de tasa — el mismo lugar que ocupa
 * `SelectorMoneda` — en vez de como pestañas propias.
 *
 * **"Todos" es válido como opción**, y no una forma de mezclar lo que la regla 2 prohíbe: el
 * crédito no cambia la unidad del rendimiento, sólo el riesgo emisor. La regla 2 (nunca mezclar
 * naturalezas de tasa) la sigue garantizando la pestaña de segmento, un nivel arriba — el crédito
 * es ortogonal a eso, es la regla 4 (el riesgo soberano se agrupa aparte) hecha filtro.
 *
 * La lista de créditos que se muestra sale del dato: un crédito sin especies en el segmento activo
 * no aparece como chip (mismo criterio que `SelectorMoneda`, que omite monedas vacías). Con un solo
 * crédito presente el selector entero no se dibuja — no hay nada que elegir. Una clase de activo
 * que no sea ninguna de las tres de renta fija (`SUBMARKET_MAP` del backend) no se pierde: entra en
 * "Todos" igual, y su cantidad se declara en la nota al pie en vez de desaparecer sin aviso — es lo
 * que antes hacía el guard `sinPestania` del monitor, ahora resuelto acá porque el problema es del
 * mismo lugar: una pestaña que reparte por clase de activo puede dejar afuera una clase nueva.
 */

import type { CSSProperties } from 'react'

/** Los tres créditos de renta fija, en el orden de la regla 4: soberano primero. */
export const ORDEN_CREDITO = ['bono_soberano', 'bono_subsoberano', 'on_corporativo'] as const

/** Rótulo de chip, en plural — distinto del singular de `ETIQUETA_CLASE` que usa la celda de tipo. */
export const ETIQUETA_CREDITO: Record<string, string> = {
  bono_soberano: 'Soberanos',
  bono_subsoberano: 'Subsoberanos',
  on_corporativo: 'ONs',
}

const DETALLE_TODOS =
  'Todo el segmento, los tres créditos juntos. El crédito no cambia la unidad del rendimiento ' +
  '(regla 2); lo que separa es el riesgo emisor (regla 4).'

const DETALLE_POR_CREDITO: Record<string, string> = {
  bono_soberano: 'Riesgo Tesoro Nacional, agrupado bajo una sola clave (regla 4 del dominio).',
  bono_subsoberano: 'Provincias y municipios: riesgo emisor propio, distinto del Tesoro.',
  on_corporativo: 'Obligaciones negociables: riesgo del emisor corporativo, no del Estado.',
}

/**
 * Cuántas especies hay de cada crédito reconocido, en el orden de `ORDEN_CREDITO`, más cuántas
 * declaran una clase de activo que ninguno de los tres cubre.
 */
export function contarPorCredito(
  especies: readonly { clase_activo: string }[],
): { disponibles: { credito: string; especies: number }[]; otras: number } {
  const conteo = new Map<string, number>()
  let otras = 0
  for (const especie of especies) {
    if ((ORDEN_CREDITO as readonly string[]).includes(especie.clase_activo)) {
      conteo.set(especie.clase_activo, (conteo.get(especie.clase_activo) ?? 0) + 1)
    } else {
      otras += 1
    }
  }
  const disponibles = ORDEN_CREDITO.filter((credito) => conteo.has(credito)).map((credito) => ({
    credito,
    especies: conteo.get(credito) as number,
  }))
  return { disponibles, otras }
}

function estiloChip(activo: boolean): CSSProperties {
  return {
    font: `${activo ? 600 : 400} 12px/1 inherit`,
    color: activo ? 'var(--tx)' : 'var(--dim)',
    background: activo ? 'var(--pan2)' : 'transparent',
    border: `1px solid ${activo ? 'var(--ac)' : 'var(--lin)'}`,
    borderRadius: 3,
    padding: '5px 10px',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  }
}

export function SelectorCredito({
  total,
  disponibles,
  otras,
  activo,
  onCambio,
}: {
  /** Cantidad total de especies del segmento — el conteo del chip "Todos". */
  total: number
  /** Créditos presentes en el segmento con su conteo, tal como los devuelve `contarPorCredito`. */
  disponibles: readonly { credito: string; especies: number }[]
  /** Especies del segmento cuya clase de activo no es ninguna de las tres de renta fija. */
  otras: number
  /** `null` = Todos. */
  activo: string | null
  onCambio: (credito: string | null) => void
}) {
  // Un solo crédito real y nada fuera de esas tres clases: no hay nada que el chip pueda separar.
  if (disponibles.length < 2 && otras === 0) return null

  return (
    <div style={{ margin: '10px 0 2px' }}>
      <div role="radiogroup" aria-label="Crédito" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
        <button
          type="button"
          role="radio"
          aria-checked={activo === null}
          onClick={() => onCambio(null)}
          title={DETALLE_TODOS}
          style={estiloChip(activo === null)}
        >
          Todos <span className="mono" style={{ fontSize: 11, color: 'var(--dim)' }}>{total}</span>
        </button>
        {disponibles.map(({ credito, especies }) => {
          const esActivo = credito === activo
          return (
            <button
              key={credito}
              type="button"
              role="radio"
              aria-checked={esActivo}
              onClick={() => onCambio(credito)}
              title={DETALLE_POR_CREDITO[credito]}
              style={estiloChip(esActivo)}
            >
              {ETIQUETA_CREDITO[credito] ?? credito}{' '}
              <span className="mono" style={{ fontSize: 11, color: 'var(--dim)' }}>{especies}</span>
            </button>
          )
        })}
      </div>
      {otras > 0 && (
        <p style={{ margin: '5px 0 0', fontSize: 11, color: 'var(--neg)' }}>
          {otras} especies con otra clase de activo sólo se ven en Todos.
        </p>
      )}
    </div>
  )
}
