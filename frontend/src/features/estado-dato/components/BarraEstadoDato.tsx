/**
 * La franja de estado del dato, debajo de la barra superior y presente en las seis pantallas.
 *
 * # Lo que declara sin que nadie despliegue nada
 *
 * **La hora del dato, no la del reloj.** Es el GWT-2 de F-013 y la regla 1 del proyecto aplicada al
 * tiempo: un snapshot de las 11:00 mirado a las 11:15 dice 11:00, y al lado dice que la fuente
 * publica con 20 minutos de demora. Las dos horas son distintas y las dos importan — la primera
 * dice cuándo se trajo el dato, la segunda hasta qué momento del mercado llega.
 *
 * El resto de la línea son los números que dicen de qué tamaño es lo que se está mirando: cuántas
 * emisiones tiene el universo, cuántas llegan al calendario, cuántos instrumentos se descartaron. Y
 * un contador de alertas por severidad, que es lo único que cambia de color.
 *
 * # Por qué esto no puede quedarse callado nunca
 *
 * Los tres estados —cargando, error y listo— dibujan la franja igual de visible. Una barra que
 * desaparece cuando el backend no contesta deja las seis pantallas mostrando números sin ninguna
 * declaración sobre ellos, que es exactamente el estado que esta feature existe para que no exista.
 * Si no se sabe nada del dato, lo que se dice es que no se sabe nada.
 */

import { useId, useState } from 'react'

import { fmtFechaHora, fmtNumero, hace } from '@/lib/fmt'

import { useDispararCorrida } from '../hooks/useDispararCorrida'
import { useEstadoDelDato } from '../hooks/useEstadoDelDato'
import { esCorridaOmitida, type EstadoDelDato, type ResultadoCorrida } from '../lib/schema'
import { colorDe, resumirConteos } from '../lib/severidad'

import { DetalleDelDato } from './DetalleDelDato'

const franja = {
  position: 'sticky',
  top: 52,
  zIndex: 39,
  display: 'flex',
  alignItems: 'center',
  gap: 14,
  minHeight: 28,
  padding: '5px 18px',
  fontSize: 11,
  background: 'var(--pan2)',
  borderBottom: '1px solid var(--lin)',
  color: 'var(--dim)',
  // La franja nunca se pinta entera: el color va en el punto y en el contador. Ver `severidad.ts`.
  flexWrap: 'wrap',
} as const

export function BarraEstadoDato() {
  const consulta = useEstadoDelDato()
  const [abierto, setAbierto] = useState(false)
  const idDetalle = useId()

  if (consulta.isPending) return <Franja>consultando el estado del dato…</Franja>

  if (consulta.isError) {
    return (
      <Franja>
        <Punto color="var(--neg)" />
        <span style={{ color: 'var(--neg)' }}>
          No se pudo leer el estado del dato: no hay forma de saber de cuándo es lo que se está
          viendo.
        </span>
        <button type="button" onClick={() => void consulta.refetch()} style={boton}>
          reintentar
        </button>
      </Franja>
    )
  }

  const estado = consulta.data

  return (
    <>
      <Franja>
        <Punto color={colorDe(estado.resumen.peor_severidad)} />
        <HoraDelDato estado={estado} />
        <Tamanio estado={estado} />
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
          <Conteos estado={estado} />
          <BotonActualizar />
          <button
            type="button"
            onClick={() => setAbierto((v) => !v)}
            aria-expanded={abierto}
            aria-controls={idDetalle}
            style={boton}
          >
            {abierto ? 'ocultar detalle ▴' : 'ver detalle ▾'}
          </button>
        </span>
      </Franja>
      {abierto && <DetalleDelDato id={idDetalle} estado={estado} />}
    </>
  )
}

function Franja({ children }: { children: React.ReactNode }) {
  // `role="status"` y no `role="alert"`: se actualiza sola cada pocos minutos y un `alert`
  // interrumpiría al lector de pantalla en medio de otra cosa cada vez que cambie un contador.
  return (
    <div className="mono" role="status" style={franja}>
      {children}
    </div>
  )
}

function Punto({ color }: { color: string }) {
  return (
    <span
      aria-hidden="true"
      style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }}
    />
  )
}

/**
 * Las dos horas, juntas y distinguidas.
 *
 * `capturado_en` es cuándo se trajo el dato. `dato_valido_hasta` es hasta qué momento del mercado
 * llega, que es `capturado_en` menos la demora que la fuente declara. **Ninguna de las dos es la
 * hora actual**, y por eso la hora actual no aparece en esta línea: si estuviera, sería la más
 * grande y la más nueva de las tres, y se leería como la del dato.
 */
function HoraDelDato({ estado }: { estado: EstadoDelDato }) {
  const { capturado_en, dato_valido_hasta, antiguedad_minutos, demora } = estado.dato

  if (capturado_en === null) {
    return (
      <span style={{ color: 'var(--neg)' }}>
        sin dato de mercado: no hay ni un precio capturado en la base
      </span>
    )
  }

  return (
    <span>
      <span style={{ color: 'var(--tx)' }}>dato de {fmtFechaHora(capturado_en)}</span>
      {antiguedad_minutos !== null && <> ({hace(antiguedad_minutos)})</>}
      {' · refleja el mercado hasta '}
      <span style={{ color: 'var(--tx)' }}>{fmtFechaHora(dato_valido_hasta)}</span>
      <span title={demora.por_que}> · {demora.fuente} declara {demora.minutos} min de demora</span>
    </span>
  )
}

/**
 * De qué tamaño es lo que se está mirando.
 *
 * La cobertura del calendario va acá arriba, sin desplegar nada, porque es el número que más cambia
 * lo que alguien cree estar viendo: la grilla de doce meses muestra 70 de 431 emisiones y sin este
 * rótulo se lee como si mostrara el universo entero.
 */
function Tamanio({ estado }: { estado: EstadoDelDato }) {
  const { universo, calendario, descartes } = estado

  return (
    <span>
      {'universo '}
      <span style={{ color: 'var(--tx)' }}>{fmtNumero(universo.emisiones, 0)}</span>
      {' emisiones · calendario '}
      <span style={{ color: calendario.con_calendario < calendario.emisiones ? 'var(--ac2)' : 'var(--tx)' }}>
        {fmtNumero(calendario.con_calendario, 0)}/{fmtNumero(calendario.emisiones, 0)}
      </span>
      {' · descartados '}
      <span style={{ color: descartes.total > 0 ? 'var(--ac2)' : 'var(--tx)' }}>
        {fmtNumero(descartes.total, 0)}
      </span>
    </span>
  )
}

/**
 * El contador por severidad, y el único lugar de la franja que lleva color.
 *
 * Cuando hay algo que requiere intervención se dice aparte y en el color de su severidad: es la
 * distinción entre lo que alguien puede arreglar y lo que se arregla solo, que es la que de verdad
 * cambia qué hace la persona que lee.
 */
function Conteos({ estado }: { estado: EstadoDelDato }) {
  const { peor_severidad, por_severidad, requiere_intervencion } = estado.resumen

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <span style={{ color: colorDe(peor_severidad) }}>{resumirConteos(por_severidad)}</span>
      {requiere_intervencion && (
        <span
          style={{
            border: `1px solid ${colorDe(peor_severidad)}`,
            borderRadius: 3,
            padding: '1px 6px',
            color: colorDe(peor_severidad),
          }}
        >
          requiere acción
        </span>
      )}
    </span>
  )
}

/**
 * El disparo manual de BYMA + data912 (F-008/`POST /jobs/corridas/matinal`). Vive acá y no en el
 * monitor porque la barra ya es el lugar de las seis pantallas que declara de qué hora es el dato
 * — el botón que fuerza uno nuevo es la otra mitad de esa misma responsabilidad.
 *
 * La corrida completa puede tardar varios minutos (BYMA + data912 + consolidación + barrido de
 * emisores + CAFCI, con `maxDuration: 300` en Vercel): el estado "actualizando" lo dice explícito
 * para que nadie interprete el botón trabado como colgado.
 */
function BotonActualizar() {
  const mutacion = useDispararCorrida()

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <button
        type="button"
        onClick={() => mutacion.mutate()}
        disabled={mutacion.isPending}
        style={boton}
      >
        {mutacion.isPending ? 'actualizando…' : 'actualizar ahora'}
      </button>
      {mutacion.isPending && (
        <span style={{ color: 'var(--dim)' }}>puede tardar varios minutos</span>
      )}
      {!mutacion.isPending && mutacion.isSuccess && <ResumenDeCorrida resultado={mutacion.data} />}
      {!mutacion.isPending && mutacion.isError && (
        <span style={{ color: 'var(--neg)' }}>{mutacion.error.message}</span>
      )}
    </span>
  )
}

const COLOR_POR_ESTADO: Record<string, string> = {
  completa: 'var(--tx)',
  parcial: 'var(--ac2)',
  fallida: 'var(--neg)',
}

function ResumenDeCorrida({ resultado }: { resultado: ResultadoCorrida }) {
  if (esCorridaOmitida(resultado)) {
    return <span style={{ color: 'var(--dim)' }}>no se disparó: {resultado.motivo}</span>
  }

  const { estado, duracion_ms, filas_por_fuente, alertas } = resultado
  const segundos = fmtNumero(duracion_ms / 1000, 1)
  const byma = filas_por_fuente.byma ?? 0
  const data912 = filas_por_fuente.data912 ?? 0

  return (
    <span style={{ color: COLOR_POR_ESTADO[estado] ?? 'var(--tx)' }}>
      {estado} · {segundos}s · byma {fmtNumero(byma, 0)} · data912 {fmtNumero(data912, 0)}
      {alertas.length > 0 && <> · {alertas.length} alertas</>}
    </span>
  )
}

const boton = {
  font: 'inherit',
  fontSize: 11,
  padding: '2px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'transparent',
  color: 'var(--dim)',
  cursor: 'pointer',
} as const
