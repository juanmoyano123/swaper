/**
 * La grilla densa del universo — F-038.
 *
 * ~1.700 filas de renta fija en total, y hasta ~700 en el segmento más grande. Ordenar, filtrar y
 * contar corre sobre las filas ya cargadas (`useMemo`, sin refetch) para que la respuesta sea
 * inmediata (GWT-2); lo único que existe para no pintar de una las ~700 filas es la virtualización
 * de `@tanstack/react-virtual` (mitigación R11 del plan).
 *
 * El conteo "N de M especies" vive acá y no en un componente aparte porque es del mismo cálculo
 * que hace la tabla para decidir qué filas mostrar: separarlo forzaría a filtrar dos veces o a
 * levantar el resultado a un estado que nadie más necesita.
 */

import { useVirtualizer } from '@tanstack/react-virtual'
import type { ReactNode } from 'react'
import { useMemo, useRef, useState } from 'react'

import { unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { etiquetaClase } from '@/lib/claseActivo'
import { fmtCompacto, fmtFecha, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'

import type { FiltrosUniverso } from './FiltrosNumericos'
import { pasaFiltros } from './FiltrosNumericos'
import type { Especie } from '../lib/schema'

/** Las columnas ordenables, en el orden en que se muestran. Todas lo son. */
type Campo =
  | 'ticker'
  | 'clase_activo'
  | 'ley'
  | 'emisor'
  | 'precio'
  | 'rendimiento'
  | 'duracion'
  | 'paridad'
  | 'volumen'
  | 'vencimiento'

type Direccion = 'asc' | 'desc'

interface Orden {
  campo: Campo | null
  direccion: Direccion
}

/**
 * ticker · tipo · ley · emisor · precio · rendimiento · duración · paridad · volumen ·
 * vencimiento · relleno. El emisor tiene techo (240px) para que un nombre corto no deje un bloque
 * de blanco en el medio de la fila: el espacio sobrante se junta en la columna final vacía. TIPO
 * son 108px porque "ON corporativa" —la etiqueta más larga— mide ~101px con padding; LEY son 96px
 * porque "Ley Argentina" —el valor más largo de la fuente— entra completo sin truncar; PRECIO son
 * 104px, dieciséis menos que antes: dejó de llevar la moneda pegada al número (ver abajo).
 */
const PLANTILLA_COLUMNAS = '64px 108px 96px minmax(120px,240px) 104px 108px 68px 72px 92px 96px 1fr'
const ALTO_FILA = 32
const ALTO_CONTENEDOR = 520

/**
 * Umbrales de color de la paridad, en fracción del valor técnico. No son un juicio sobre el papel:
 * la paridad es un dato duro —precio sucio sobre valor técnico— y esto sólo la hace legible de un
 * vistazo sobre setecientas filas. Los cortes están en los dos lugares obvios, la par (1,00) y el
 * descuento fuerte, y no en percentiles del universo: un corte relativo movería el color de un bono
 * sin que el bono se moviera.
 */
const PARIDAD_SOBRE_LA_PAR = 1
const PARIDAD_DESCUENTO_FUERTE = 0.8

function colorDeParidad(paridad: number | null): string {
  if (paridad === null) return 'var(--tx)'
  if (paridad >= PARIDAD_SOBRE_LA_PAR) return 'var(--pos)'
  if (paridad < PARIDAD_DESCUENTO_FUERTE) return 'var(--neg)'
  return 'var(--tx)'
}

/**
 * Compara dos especies por un campo, con `null` **siempre al final** sin importar la dirección:
 * un dato que falta no es "el más chico" ni "el más grande", así que no puede decidir el orden.
 */
function comparar(a: Especie, b: Especie, campo: Campo, direccion: Direccion): number {
  // TIPO se ordena por la etiqueta que se ve en pantalla, no por el valor interno: ordenado por
  // `clase_activo` crudo, "Soberano" (bono_soberano) quedaría antes que "ON corporativa"
  // (on_corporativo) en un orden supuestamente alfabético.
  const va = campo === 'clase_activo' ? etiquetaClase(a.clase_activo) : (a[campo] as string | number | null)
  const vb = campo === 'clase_activo' ? etiquetaClase(b.clase_activo) : (b[campo] as string | number | null)
  if (va === null && vb === null) return 0
  if (va === null) return 1
  if (vb === null) return -1

  const signo = direccion === 'asc' ? 1 : -1
  if (typeof va === 'number' && typeof vb === 'number') return signo * (va - vb)
  return signo * String(va).localeCompare(String(vb), 'es')
}

export function TablaUniverso({
  especies,
  naturaleza,
  filtros,
  moneda,
}: {
  /** Ya filtradas por moneda: la tabla no elige qué mostrar, sólo ordena y aplica los filtros. */
  especies: Especie[]
  naturaleza: string
  filtros: FiltrosUniverso
  /** La moneda del selector, para el conteo. La tabla no la usa para decidir nada más. */
  moneda: string
}) {
  const [orden, setOrden] = useState<Orden>({ campo: null, direccion: 'asc' })
  const abrirInstrumento = useAbrirInstrumento()
  const contenedorRef = useRef<HTMLDivElement>(null)

  const filasOrdenadas = useMemo(() => {
    const filtradas = especies.filter((e) => pasaFiltros(e, filtros))
    if (orden.campo === null) return filtradas
    const campo = orden.campo
    return [...filtradas].sort((a, b) => comparar(a, b, campo, orden.direccion))
  }, [especies, filtros, orden])

  const virtualizador = useVirtualizer({
    count: filasOrdenadas.length,
    getScrollElement: () => contenedorRef.current,
    estimateSize: () => ALTO_FILA,
    overscan: 10,
  })

  function alternarOrden(campo: Campo) {
    setOrden((actual) => {
      if (actual.campo !== campo) return { campo, direccion: 'asc' }
      if (actual.direccion === 'asc') return { campo, direccion: 'desc' }
      return { campo: null, direccion: 'asc' } // tercer clic: vuelve a sin ordenar
    })
  }

  return (
    <div>
      <p className="mono" style={{ margin: '2px 0 8px', fontSize: 11.5, color: 'var(--dim)' }}>
        {fmtNumero(filasOrdenadas.length, 0)} de {fmtNumero(especies.length, 0)} especies en {moneda}
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: PLANTILLA_COLUMNAS, gap: 0 }}>
        <Cabecera campo="ticker" orden={orden} onClick={alternarOrden}>ticker</Cabecera>
        <Cabecera campo="clase_activo" orden={orden} onClick={alternarOrden}>tipo</Cabecera>
        <Cabecera campo="ley" orden={orden} onClick={alternarOrden}>ley</Cabecera>
        <Cabecera campo="emisor" orden={orden} onClick={alternarOrden}>emisor</Cabecera>
        <Cabecera campo="precio" orden={orden} onClick={alternarOrden} alinear="right">precio</Cabecera>
        <Cabecera campo="rendimiento" orden={orden} onClick={alternarOrden} alinear="right">
          rendimiento ({unidadDeNaturaleza(naturaleza)})
        </Cabecera>
        <Cabecera campo="duracion" orden={orden} onClick={alternarOrden} alinear="right">duración</Cabecera>
        <Cabecera campo="paridad" orden={orden} onClick={alternarOrden} alinear="right">paridad</Cabecera>
        <Cabecera campo="volumen" orden={orden} onClick={alternarOrden} alinear="right">volumen</Cabecera>
        <Cabecera campo="vencimiento" orden={orden} onClick={alternarOrden} alinear="right">vencimiento</Cabecera>
        {/* Relleno: la cabecera son botones con fondo y borde propios, así que la columna vacía
            necesita su celda para que la línea del header llegue pareja hasta el final. */}
        <div aria-hidden style={{ background: 'var(--pan2)', borderBottom: '1px solid var(--lin)' }} />
      </div>

      {filasOrdenadas.length === 0 ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          Ninguna especie en {moneda} pasa los filtros activos.
        </p>
      ) : (
        <div ref={contenedorRef} style={{ height: ALTO_CONTENEDOR, overflow: 'auto', position: 'relative', borderTop: '1px solid var(--lin)' }}>
          <div style={{ height: virtualizador.getTotalSize(), position: 'relative' }}>
            {virtualizador.getVirtualItems().map((fila) => {
              const especie = filasOrdenadas[fila.index]
              return (
                <FilaEspecie
                  key={especie.ticker}
                  especie={especie}
                  top={fila.start}
                  alto={fila.size}
                  onClick={() => abrirInstrumento(especie.ticker)}
                />
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

function Cabecera({
  campo,
  orden,
  onClick,
  alinear = 'left',
  children,
}: {
  campo: Campo
  orden: Orden
  onClick: (campo: Campo) => void
  alinear?: 'left' | 'right'
  children: ReactNode
}) {
  const activo = orden.campo === campo
  const indicador = activo ? (orden.direccion === 'asc' ? ' ▲' : ' ▼') : ''

  return (
    <button
      type="button"
      onClick={() => onClick(campo)}
      aria-sort={activo ? (orden.direccion === 'asc' ? 'ascending' : 'descending') : 'none'}
      style={{
        font: 'inherit',
        fontSize: 10.5,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        textAlign: alinear,
        color: activo ? 'var(--tx)' : 'var(--dim)',
        background: 'var(--pan2)',
        border: 'none',
        borderBottom: '1px solid var(--lin)',
        padding: '7px 8px',
        cursor: 'pointer',
      }}
    >
      {children}
      {indicador}
    </button>
  )
}

function FilaEspecie({ especie, top, alto, onClick }: { especie: Especie; top: number; alto: number; onClick: () => void }) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick()
      }}
      title={especie.dato_sano ? undefined : 'descartado por sanidad'}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: alto,
        transform: `translateY(${top}px)`,
        display: 'grid',
        gridTemplateColumns: PLANTILLA_COLUMNAS,
        alignItems: 'center',
        borderBottom: '1px solid var(--lin)',
        opacity: especie.dato_sano ? 1 : 0.5,
        cursor: 'pointer',
      }}
    >
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, whiteSpace: 'nowrap' }}>
        {especie.ticker}
      </span>
      <span style={{ padding: '0 8px', fontSize: 12, whiteSpace: 'nowrap', color: 'var(--dim)' }}>
        {etiquetaClase(especie.clase_activo)}
      </span>
      <span style={{ padding: '0 8px', fontSize: 12, whiteSpace: 'nowrap', color: 'var(--dim)' }}>
        {especie.ley ?? SIN_DATO}
      </span>
      <span style={{ padding: '0 8px', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={especie.emisor ?? undefined}>
        {especie.emisor ?? SIN_DATO}
      </span>
      {/* Sin la moneda pegada al número: la declara el selector de arriba, una vez para toda la
          tabla. Repetirla en cada fila era necesario mientras convivían las tres especies de una
          emisión; con una moneda por vez es ruido, y además invitaba a comparar hacia abajo una
          columna que mezclaba pesos con dólares. */}
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.precio)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtPct(especie.rendimiento === null ? null : especie.rendimiento * 100)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.duracion)}
      </span>
      <span
        className="mono"
        style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: colorDeParidad(especie.paridad) }}
      >
        {fmtPct(especie.paridad === null ? null : especie.paridad * 100)}
      </span>
      {/* El volumen crudo, en la moneda del selector. No es `volumen_usd`: convertirlo exigía saber
          en qué moneda está, y para las especies `EXT` eso no consta (regla 11). Con una sola
          moneda en pantalla la columna es comparable sin convertir nada. `volumen_usd` sigue
          existiendo en el contrato para el filtro de liquidez del armador, que sí cruza monedas. */}
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtCompacto(especie.volumen)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtFecha(especie.vencimiento)}
      </span>
    </div>
  )
}
