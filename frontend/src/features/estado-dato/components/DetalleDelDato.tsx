/**
 * El panel desplegable de la barra de estado del dato — F-013.
 *
 * Cuatro bloques, en el orden en que alguien los necesita:
 *
 * 1. **Alertas**, partidas en dos por la única distinción que cambia qué hace quien lee: las que
 *    esperan que alguien actúe y las que no. Es el GWT-4 llevado a la pantalla — la credencial
 *    vencida arriba, con su acción; la fuente caída abajo, diciendo que se destraba sola.
 * 2. **Instrumentos descartados por sanidad**, con motivo y el valor que lo disparó (GWT-3).
 * 3. **Cobertura de cada campo crítico**, con el porqué al lado. Un porcentaje sin decir qué se
 *    rompe sin ese campo es un número de tablero y no una advertencia.
 * 4. **La corrida** que trajo el dato, o el aviso de que no hay ninguna registrada.
 *
 * Todo lo que se muestra viene del backend redactado. Acá no se reescribe ningún mensaje ni se
 * traduce ningún motivo: el backend ya dice el hecho con nombre y apellido, y una segunda redacción
 * haría que el mismo problema se cuente distinto según por dónde se lo mire.
 */

import { fmtFechaHora, fmtNumero, fmtPct } from '@/lib/fmt'

import type { Alerta, CoberturaCampo, Descarte, EstadoDelDato } from '../lib/schema'
import { colorDe } from '../lib/severidad'

export function DetalleDelDato({ id, estado }: { id: string; estado: EstadoDelDato }) {
  const accionables = estado.alertas.filter((a) => a.accion_requerida !== null)
  const restantes = estado.alertas.filter((a) => a.accion_requerida === null)

  return (
    <div
      id={id}
      style={{
        background: 'var(--pan)',
        borderBottom: '1px solid var(--lin)',
        padding: '14px 18px',
        display: 'grid',
        gap: 18,
      }}
    >
      <Bloque
        rotulo="Requieren que alguien haga algo"
        vacio="Ninguna alerta necesita intervención: nada de lo que falta se arregla a mano hoy."
      >
        {accionables.map((a) => (
          <FilaAlerta key={a.codigo} alerta={a} />
        ))}
      </Bloque>

      <Bloque
        rotulo="Se resuelven solas, o son el estado del dato"
        vacio="No hay nada más que declarar sobre el dato de hoy."
      >
        {restantes.map((a) => (
          <FilaAlerta key={a.codigo} alerta={a} />
        ))}
      </Bloque>

      <Descartes estado={estado} />
      <Cobertura campos={estado.cobertura} />
      <Corrida estado={estado} />
    </div>
  )
}

function Bloque({
  rotulo,
  vacio,
  children,
}: {
  rotulo: string
  /** Qué se dice cuando el bloque está vacío. Nunca se oculta: una sección ausente no se lee. */
  vacio?: string
  children: React.ReactNode
}) {
  const hayContenido = Array.isArray(children) ? children.length > 0 : Boolean(children)

  return (
    <section>
      <h2 className="rotulo" style={{ margin: '0 0 7px' }}>
        {rotulo}
      </h2>
      {hayContenido ? (
        <div style={{ display: 'grid', gap: 6 }}>{children}</div>
      ) : (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)' }}>{vacio}</p>
      )}
    </section>
  )
}

/**
 * Una alerta, con el borde izquierdo del color de su severidad.
 *
 * El color es lo único que la severidad decide: no hay fondos teñidos ni iconos que griten. Cuatro
 * advertencias apiladas con fondo ámbar convierten el panel en una pared de color donde el error
 * de verdad no se distingue de la advertencia que va a estar todos los días.
 */
function FilaAlerta({ alerta }: { alerta: Alerta }) {
  return (
    <div
      style={{
        borderLeft: `2px solid ${colorDe(alerta.severidad)}`,
        background: 'var(--pan2)',
        borderRadius: '0 3px 3px 0',
        padding: '7px 10px',
        maxWidth: '92ch',
      }}
    >
      <p style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
        {alerta.mensaje}
      </p>
      {alerta.accion_requerida !== null && (
        <p style={{ margin: '4px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>
          {alerta.accion_requerida}
        </p>
      )}
      <p className="mono" style={{ margin: '4px 0 0', fontSize: 10, color: 'var(--sd)' }}>
        {alerta.codigo} · {alerta.origen === 'ingesta' ? 'al traer el dato' : 'sobre el dato traído'}
      </p>
    </div>
  )
}

/**
 * Los instrumentos que no se proponen, con el número que los sacó — GWT-3.
 *
 * **El cero se explica.** Que la sanidad no descarte nada no significa que el dato esté sano:
 * significa que nada de lo que llegó a tener segmento superó el techo de su segmento. Las especies
 * sin tipo de tasa no pasan por ninguna de las dos capas, así que un universo con cientos de ellas
 * puede descartar cero y estar lleno de números imposibles que nadie miró.
 */
function Descartes({ estado }: { estado: EstadoDelDato }) {
  const { descartes, universo } = estado

  return (
    <section>
      <h2 className="rotulo" style={{ margin: '0 0 7px' }}>
        Instrumentos descartados por sanidad
      </h2>

      {descartes.total === 0 ? (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)', maxWidth: '92ch' }}>
          Ninguno de los {fmtNumero(universo.evaluados, 0)} instrumentos evaluados declara un
          rendimiento imposible para su segmento. Ojo con leerlo como &ldquo;el dato está
          sano&rdquo;: otras {fmtNumero(universo.sin_segmento, 0)} especies de renta fija no tienen
          tipo de tasa, y sin segmento no hay techo contra el cual compararlas — la sanidad ni las
          mira.
        </p>
      ) : (
        <>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
            {descartes.items.map((d) => (
              <FilaDescarte key={d.ticker} descarte={d} />
            ))}
          </ul>
          {descartes.truncado && (
            <p className="mono" style={{ margin: '6px 0 0', fontSize: 10.5, color: 'var(--sd)' }}>
              Se muestran {fmtNumero(descartes.items.length, 0)} de{' '}
              {fmtNumero(descartes.total, 0)}. El listado completo está en
              /api/v1/universo/sanidad/descartes.
            </p>
          )}
        </>
      )}
    </section>
  )
}

/**
 * Un descarte con su motivo, su valor y contra qué se lo comparó.
 *
 * El rendimiento se muestra **con la unidad de su segmento al lado**: 4,8 es un descarte en CER y un
 * instrumento sano en tasa fija, y el número solo no se puede leer. Es la regla 2 del proyecto.
 */
function FilaDescarte({ descarte }: { descarte: Descarte }) {
  return (
    <li
      className="mono"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        fontSize: 11.5,
        padding: '4px 8px',
        borderRadius: 3,
        background: 'var(--pan2)',
      }}
    >
      <span style={{ color: 'var(--tx)', minWidth: 72 }}>{descarte.ticker}</span>
      <span style={{ color: 'var(--ac2)' }}>
        {fmtPct(descarte.rendimiento === null ? null : descarte.rendimiento * 100)}
      </span>
      <span style={{ color: 'var(--dim)', flex: 1 }}>
        {descarte.naturaleza_nombre} · contra {fmtPct(descarte.umbral * 100)}
        {descarte.ticker_referencia !== null && (
          <>
            {' · su hermana '}
            {descarte.ticker_referencia} declara{' '}
            {fmtPct(
              descarte.rendimiento_referencia === null
                ? null
                : descarte.rendimiento_referencia * 100,
            )}
          </>
        )}
      </span>
    </li>
  )
}

/** Cuánto del universo trae cada campo crítico, y qué deja de poder hacerse cuando no lo trae. */
function Cobertura({ campos }: { campos: CoberturaCampo[] }) {
  return (
    <section>
      <h2 className="rotulo" style={{ margin: '0 0 7px' }}>
        Cobertura de los campos críticos
      </h2>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 }}>
        {campos.map((campo) => (
          <li
            key={campo.campo}
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'baseline',
              gap: 10,
              fontSize: 11.5,
              padding: '4px 8px',
              borderRadius: 3,
              background: 'var(--pan2)',
            }}
          >
            <span style={{ color: 'var(--tx)', minWidth: 150 }}>{campo.rotulo}</span>
            <span
              className="mono"
              style={{ color: campo.presentes === 0 ? 'var(--ac2)' : 'var(--dim)', minWidth: 130 }}
            >
              {fmtNumero(campo.presentes, 0)}/{fmtNumero(campo.total, 0)} ·{' '}
              {fmtPct(campo.porcentaje, 1)}
            </span>
            <span style={{ color: 'var(--sd)', flex: 1, minWidth: 260, textWrap: 'pretty' }}>
              {campo.por_que}
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * De qué corrida salió el dato.
 *
 * Cuando no hay ninguna registrada se dice, y se dice qué significa: puede haber precios cargados
 * por otro camino —es lo que pasa hoy— y lo que falta no es el dato sino poder saber de dónde vino.
 */
function Corrida({ estado }: { estado: EstadoDelDato }) {
  const { corrida, costo } = estado

  return (
    <section>
      <h2 className="rotulo" style={{ margin: '0 0 7px' }}>
        Última corrida de ingesta
      </h2>

      {corrida === null ? (
        <p style={{ margin: 0, fontSize: 11.5, color: 'var(--sd)', maxWidth: '92ch' }}>
          No hay ninguna corrida registrada. El dato que se está viendo puede haber entrado por otro
          camino, pero no hay traza de qué fuente lo trajo ni de qué alertó al traerlo.
        </p>
      ) : (
        <p className="mono" style={{ margin: 0, fontSize: 11.5, color: 'var(--dim)' }}>
          {corrida.tipo} · {corrida.estado} · {fmtFechaHora(corrida.finalizado_en)} ·{' '}
          {fmtNumero(corrida.duracion_ms / 1000, 1)} s ·{' '}
          {Object.entries(corrida.filas_por_fuente)
            .map(([fuente, filas]) => `${fuente} ${fmtNumero(filas, 0)}`)
            .join(' · ')}
        </p>
      )}

      {/* Lo que costó armar esta respuesta. Va en la pantalla y no sólo en el log porque la barra
          está en las seis y quien la mire tiene que poder ver si le están sirviendo una foto: si
          sale del caché, el análisis es de ese momento y no de ahora. */}
      <p className="mono" style={{ margin: '6px 0 0', fontSize: 10, color: 'var(--sd)' }}>
        análisis del universo{' '}
        {costo.desde_cache
          ? `en caché desde ${fmtFechaHora(costo.analisis_calculado_en)}`
          : `calculado recién en ${fmtNumero(costo.analisis_duracion_ms, 0)} ms`}
      </p>
    </section>
  )
}
