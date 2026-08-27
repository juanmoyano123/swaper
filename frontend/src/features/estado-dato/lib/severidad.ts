/**
 * La jerarquía visual de la barra — F-013.
 *
 * # El criterio, que es de producto y no de código
 *
 * **Una barra que grita en rojo todo el tiempo se vuelve invisible en una semana.** En este dominio
 * la mayoría de las alertas no son fallas: son hechos ciertos y permanentes sobre el dato. Que el
 * calendario no cubra todas las emisiones va a estar mañana y pasado, porque la paridad sale del
 * cálculo propio y sólo se puede calcular donde precio y flujo comparten moneda: no hay nada que
 * arreglar. Pintar eso de rojo enseña a ignorar el rojo, y el día que se caiga una fuente de
 * verdad nadie lo va a mirar. Una fuente que el producto decide no consumir —CAFCI o la CNV en
 * `false`— es del mismo tipo: viaja como `info` y sin acción, porque es una decisión y no una
 * falla.
 *
 * Por eso se separan **dos ejes**, y no uno:
 *
 * 1. **Severidad** — cuánto duele. Sólo `error` lleva el color negativo, y `error` en este proyecto
 *    significa una cosa concreta: esa fuente no aportó nada en esta corrida. `advertencia` va en
 *    ámbar: la corrida sirve pero salió incompleta. `info` va en el gris de siempre.
 * 2. **Acción requerida** — si alguien puede hacer algo. Es la distinción que `Alerta` separa en su
 *    propio campo, y la razón por la que existe: "el token venció" y "la API está caída" duelen
 *    igual, pero sólo la primera espera que una persona actúe. Presentarlas iguales haría que
 *    alguien espere sentado algo que no se destraba solo.
 *
 * El segundo eje es el que de verdad ordena la pantalla, porque es el que cambia lo que alguien
 * hace después de leer. Una advertencia accionable se ve antes que un error que se arregla solo.
 *
 * # Lo que se pinta y lo que no
 *
 * **La franja nunca se pinta entera.** El color va en el punto y en el contador, que ocupan unos
 * pocos píxeles; el fondo se queda en `--pan2` pase lo que pase. Una franja de color a lo ancho de
 * la pantalla compite con el contenido —que es el dato de mercado por el que el asesor abrió la
 * aplicación— y en el caso normal de este producto habría color todos los días.
 */

import type { Severidad } from './schema'

/** Los tokens del design system que le corresponden a cada severidad. */
const COLOR: Record<Severidad, string> = {
  error: 'var(--neg)',
  advertencia: 'var(--ac2)',
  info: 'var(--dim)',
}

/** Cómo se nombra cada nivel en pantalla. En plural, que es como se cuentan. */
const NOMBRE: Record<Severidad, string> = {
  error: 'errores',
  advertencia: 'advertencias',
  info: 'información',
}

/**
 * Orden de urgencia. Se declara acá porque el orden alfabético de los valores
 * (`advertencia` < `error` < `info`) es casi el inverso, y es el que saldría de un `sort` ingenuo.
 * Es el mismo cuidado que toma `ORDEN_SEVERIDAD` en el backend.
 */
export const ORDEN: Severidad[] = ['error', 'advertencia', 'info']

export function colorDe(severidad: Severidad | null): string {
  // Sin alertas el punto va en verde: "no hay nada que declarar" es un estado y no la ausencia de
  // uno. Dejarlo gris lo haría indistinguible de "todavía no cargó".
  return severidad === null ? 'var(--pos)' : COLOR[severidad]
}

export function nombreDe(severidad: Severidad): string {
  return NOMBRE[severidad]
}

/**
 * El resumen de una línea que se lee sin desplegar nada.
 *
 * Nombra los niveles presentes y omite los vacíos: "1 error · 4 advertencias" y no
 * "1 error · 4 advertencias · 0 información". Un cero explícito acá ocupa el lugar de algo que sí
 * pasa —y es distinto del cero de un monto, donde el cero **es** el dato—.
 */
export function resumirConteos(conteos: Partial<Record<Severidad, number>>): string {
  const partes = ORDEN.filter((s) => (conteos[s] ?? 0) > 0).map((s) => {
    const cantidad = conteos[s] ?? 0
    return `${cantidad} ${cantidad === 1 ? singular(s) : NOMBRE[s]}`
  })
  return partes.length > 0 ? partes.join(' · ') : 'sin alertas'
}

function singular(severidad: Severidad): string {
  return severidad === 'error' ? 'error' : severidad === 'advertencia' ? 'advertencia' : 'aviso'
}
