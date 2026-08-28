/**
 * Selector de subtipo dentro de los soberanos: Todos, o una sola subclase a la vez.
 *
 * Calcado de `SelectorCredito`, un nivel más abajo: se dibuja **sólo cuando el chip de crédito está
 * en Soberanos**, porque el subtipo es la subclasificación de ese crédito y nada más (una ON no
 * tiene subtipo). Ver `MonitorPage.tsx`, donde el chip se monta y donde cambiar el crédito lo apaga.
 *
 * Nace el 28/08/2026, cuando entró el panel `lebacs` de BYMA: hasta ese día las letras del Tesoro,
 * los bonares, los globales y los bopreales caían todos juntos bajo `bono_soberano` y no había
 * forma de separarlos en pantalla. El dato viene de `instrumentos.subtipo`, con vocabulario cerrado
 * por el CHECK de la base; el frontend no lo deriva ni lo completa.
 *
 * **"Todos" es válido y no mezcla nada que la regla 2 prohíba**: los cuatro subtipos son el mismo
 * crédito y la unidad del rendimiento ya la fijó la pestaña de segmento, dos niveles arriba. Lo que
 * el chip separa es la estructura de la emisión, no la vara con que se la mide.
 *
 * Una subclase sin especies bajo el resto de los filtros no aparece; con una sola opción el
 * selector entero no se dibuja, porque no hay nada que elegir. Es el mismo criterio de
 * `SelectorCredito` y `SelectorMoneda`.
 */

import type { CSSProperties } from 'react'

/** Los cuatro subtipos, del tramo más corto al más largo y el Bopreal al final por ser otro
 *  emisor. Un valor que la base sume mañana no se pierde: entra en "Todos" y se cuenta en la nota
 *  al pie, igual que hace `SelectorCredito` con una clase de activo que no conoce. */
export const ORDEN_SUBTIPO = ['letra', 'bonar', 'global', 'bopreal'] as const

/** La clave del chip que junta a los soberanos sin subclase declarada. No es un valor de la base:
 *  ahí ese caso es `null`. Se nombra para poder filtrarlo sin confundirlo con "sin filtro". */
export const SIN_SUBCLASE = 'sin_subclase'

export const ETIQUETA_SUBTIPO: Record<string, string> = {
  letra: 'Letras',
  bonar: 'Bonares',
  global: 'Globales',
  bopreal: 'Bopreales',
  [SIN_SUBCLASE]: '(sin subclase)',
}

const DETALLE_TODOS =
  'Todo el crédito soberano, las cuatro subclases juntas. El subtipo no cambia la unidad del ' +
  'rendimiento ni la clave de concentración: sólo la estructura de la emisión.'

const DETALLE_POR_SUBTIPO: Record<string, string> = {
  letra:
    'Letras del Tesoro: las trae el panel lebacs de BYMA y el cronograma las declara soberanas. ' +
    'Una letra provincial no entra acá — es otro emisor.',
  bonar: 'Soberanos hard dollar bajo Ley Argentina, según la ley declarada por la fuente curada.',
  global: 'Soberanos hard dollar bajo Ley N.Y., según la ley declarada por la fuente curada.',
  bopreal:
    'Bopreales: los emite el BCRA, no el Tesoro. A efectos de concentración siguen bajo la ' +
    'misma clave soberana y con el mismo tope (regla 4 del dominio); el subtipo sólo los ' +
    'distingue en pantalla.',
  [SIN_SUBCLASE]:
    'Soberanos sin subclase declarada por la fuente — típicamente sin ley informada. El faltante ' +
    'se muestra, no se completa por analogía (regla 1).',
}

/** Cuántas especies hay de cada subtipo, en el orden de `ORDEN_SUBTIPO` y con los `null`
 *  agrupados al final bajo `SIN_SUBCLASE`, más cuántas declaran un subtipo que el orden no cubre. */
export function contarPorSubtipo(
  especies: readonly { subtipo: string | null }[],
): { disponibles: { subtipo: string; especies: number }[]; otros: number } {
  const conteo = new Map<string, number>()
  let otros = 0
  for (const especie of especies) {
    const clave = especie.subtipo ?? SIN_SUBCLASE
    if (clave === SIN_SUBCLASE || (ORDEN_SUBTIPO as readonly string[]).includes(clave)) {
      conteo.set(clave, (conteo.get(clave) ?? 0) + 1)
    } else {
      otros += 1
    }
  }
  const orden = [...ORDEN_SUBTIPO, SIN_SUBCLASE]
  const disponibles = orden
    .filter((subtipo) => conteo.has(subtipo))
    .map((subtipo) => ({ subtipo, especies: conteo.get(subtipo) as number }))
  return { disponibles, otros }
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

export function SelectorSubtipoSoberano({
  total,
  disponibles,
  otros,
  activo,
  onCambio,
}: {
  /** Cantidad total de especies soberanas — el conteo del chip "Todos". */
  total: number
  /** Subtipos presentes con su conteo, tal como los devuelve `contarPorSubtipo`. */
  disponibles: readonly { subtipo: string; especies: number }[]
  /** Especies cuyo subtipo no es ninguno de los cuatro del vocabulario conocido. */
  otros: number
  /** `null` = Todos. */
  activo: string | null
  onCambio: (subtipo: string | null) => void
}) {
  // Una sola subclase y nada fuera del vocabulario: no hay nada que el chip pueda separar.
  if (disponibles.length < 2 && otros === 0) return null

  return (
    <div style={{ margin: '10px 0 2px' }}>
      <div role="radiogroup" aria-label="Subtipo soberano" style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
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
        {disponibles.map(({ subtipo, especies }) => {
          const esActivo = subtipo === activo
          return (
            <button
              key={subtipo}
              type="button"
              role="radio"
              aria-checked={esActivo}
              onClick={() => onCambio(subtipo)}
              title={DETALLE_POR_SUBTIPO[subtipo]}
              style={estiloChip(esActivo)}
            >
              {ETIQUETA_SUBTIPO[subtipo] ?? subtipo}{' '}
              <span className="mono" style={{ fontSize: 11, color: 'var(--dim)' }}>{especies}</span>
            </button>
          )
        })}
      </div>
      {otros > 0 && (
        <p style={{ margin: '5px 0 0', fontSize: 11, color: 'var(--neg)' }}>
          {otros} especies con otro subtipo sólo se ven en Todos.
        </p>
      )}
    </div>
  )
}
