/**
 * Cómo se reparte la cartera en un eje — base común de la Tanda 9.
 *
 * Vive en `components/` y no adentro de una feature porque lo comparten F-020 (distribución por
 * sector, por ley y por naturaleza de tasa en renta fija) y, cuando tenga fuente, el bloque de
 * renta variable de F-026 (por país y por rubro). La duda de solape 6 del plan de tandas pedía
 * exactamente esto: crear a mano lo compartido antes de soltar agentes en paralelo.
 *
 * **Lo que falta se muestra, no se reparte.** Un tramo puede venir con `sinDato: true` —"sector no
 * informado", "ley no informada"— y aparece como cualquier otro, con su peso real y su color
 * apagado. Repartir esas posiciones entre los tramos conocidos, o simplemente omitirlas, haría que
 * la distribución sumara 100 % mintiendo sobre la cobertura (reglas 1 y 11 del dominio).
 *
 * **Color por índice, no un solo verde para todo.** Etapa 1 del rediseño del armador: cada tramo
 * toma su color de `--cat1..--cat6` según su posición en el array (`sinDato` sigue en `--sd`). El
 * verde (`--ac`/`--pos`) queda reservado a renta/positivo/selección — acá no se está afirmando que
 * un tramo sea "bueno", sólo cuánto pesa.
 *
 * No decide nada sobre lo que muestra: no ordena por criterio propio, no marca excesos y no emite
 * juicio. El orden lo fija quien lo llama y las advertencias de tope las pone su propio panel —
 * acá sólo se ve cómo está repartida la cartera.
 */

import { fmtPct } from '@/lib/fmt'

export interface TramoDistribucion {
  /** Cómo se llama el tramo. Para lo no informado, el texto lo declara ("sector no informado"). */
  nombre: string
  /** Peso en puntos porcentuales sobre el total del bloque (16.5 = 16,5%). */
  peso: number
  /** `true` cuando el tramo agrupa lo que no tiene el dato. Se muestra apagado y se nombra. */
  sinDato?: boolean
}

interface Props {
  titulo: string
  tramos: readonly TramoDistribucion[]
  /** Qué decir cuando no hay nada que repartir. Por defecto, que no hay posiciones. */
  vacio?: string
}

const ALTO_BARRA = 8

// Paleta categórica (Etapa 1 del rediseño del armador): un color estable por índice de tramo,
// no uno solo para todos. El orden de `tramos` lo fija quien llama a este componente y ya es
// estable entre renders, así que el color de cada nombre no salta al refrescar.
const CATEGORICOS = [
  'var(--cat1)',
  'var(--cat2)',
  'var(--cat3)',
  'var(--cat4)',
  'var(--cat5)',
  'var(--cat6)',
]

export function DistribucionBarras({ titulo, tramos, vacio }: Props) {
  const total = tramos.reduce((acumulado, t) => acumulado + t.peso, 0)

  return (
    <section style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <h4
        style={{
          margin: 0,
          fontSize: 10,
          color: 'var(--dim)',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        {titulo}
      </h4>

      {tramos.length === 0 ? (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)' }}>
          {vacio ?? 'Sin posiciones para repartir.'}
        </p>
      ) : (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 5 }}>
          {tramos.map((tramo, indice) => (
            <li key={tramo.nombre} style={{ display: 'grid', gap: 2 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
                <span style={{ color: tramo.sinDato ? 'var(--sd)' : 'var(--tx)' }}>
                  {tramo.nombre}
                </span>
                <span className="mono" style={{ color: tramo.sinDato ? 'var(--sd)' : 'var(--tx)' }}>
                  {fmtPct(tramo.peso, 1)}
                </span>
              </div>
              <div
                aria-hidden
                style={{
                  height: ALTO_BARRA,
                  background: 'var(--pan2)',
                  borderRadius: 2,
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    // Contra el total del bloque y no contra 100: si la cartera no suma 100 —cosa
                    // que el armador permite y muestra— las barras siguen siendo comparables entre
                    // sí, que es lo que este panel responde.
                    width: total > 0 ? `${(tramo.peso / total) * 100}%` : '0%',
                    height: '100%',
                    background: tramo.sinDato ? 'var(--sd)' : CATEGORICOS[indice % CATEGORICOS.length],
                  }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
