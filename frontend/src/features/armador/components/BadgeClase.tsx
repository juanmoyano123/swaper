/**
 * Qué es cada ticker, en dos o tres letras — Tanda 13.
 *
 * En una cartera que mezcla bonos del Tesoro, deuda provincial, obligaciones negociables, acciones
 * y CEDEARs, el ticker solo no alcanza: `AL30` y `YMCXO` se leen igual si no sabés de memoria cuál
 * es soberano y cuál corporativo, y el riesgo de crédito detrás de cada uno no tiene nada que ver.
 * Este badge pone esa distinción al lado del ticker en la grilla, en la cartera y en el bloque de
 * renta variable.
 *
 * **Una clase que no está en la tabla se muestra tal cual viene.** `clase_activo` es vocabulario
 * curado del proyecto (lo asigna `app/ingesta/consolidacion/clasificacion.py`, no es un código
 * propietario de una fuente externa), así que traducir los cinco valores conocidos es leer lo que
 * la fuente declara, no interpretarla. Pero si mañana aparece un sexto valor, se muestra el código
 * crudo y sin color en vez de meterlo a la fuerza en la categoría más parecida: la regla 11 del
 * dominio prohíbe justamente esa clase de relleno.
 */

interface Rotulo {
  sigla: string
  color: string
  /** Qué significa la sigla, para el `title`: nadie tiene por qué saber que SUB es subsoberano. */
  descripcion: string
}

const ROTULOS: Record<string, Rotulo> = {
  bono_soberano: { sigla: 'SOB', color: 'var(--cat1)', descripcion: 'Bono soberano' },
  bono_subsoberano: { sigla: 'SUB', color: 'var(--cat1)', descripcion: 'Bono subsoberano' },
  on_corporativo: { sigla: 'ON', color: 'var(--cat2)', descripcion: 'Obligación negociable' },
  accion: { sigla: 'ACC', color: 'var(--cat3)', descripcion: 'Acción' },
  cedear: { sigla: 'CEDEAR', color: 'var(--cat3)', descripcion: 'CEDEAR' },
}

/**
 * Cómo rotular esa clase de activo. Una clase desconocida vuelve con su propio código como sigla y
 * sin color: se muestra, no se adivina.
 */
export function rotuloDeClase(claseActivo: string): Rotulo {
  return (
    ROTULOS[claseActivo] ?? {
      sigla: claseActivo,
      color: 'var(--dim)',
      descripcion: `Clase de activo declarada por la fuente: ${claseActivo}`,
    }
  )
}

/**
 * El badge. `null`/`undefined` no renderiza nada: no hay dato de clase para ese ticker y un
 * "s/d" al lado de cada ticker sería ruido sin información.
 */
export function BadgeClase({ claseActivo }: { claseActivo?: string | null }) {
  if (!claseActivo) return null
  const { sigla, color, descripcion } = rotuloDeClase(claseActivo)

  return (
    <span
      className="mono"
      title={descripcion}
      style={{
        fontSize: 9,
        lineHeight: 1.4,
        letterSpacing: '0.04em',
        padding: '1px 4px',
        borderRadius: 2,
        border: `1px solid ${color}`,
        color,
        whiteSpace: 'nowrap',
      }}
    >
      {sigla}
    </span>
  )
}
