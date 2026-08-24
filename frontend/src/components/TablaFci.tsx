/**
 * La grilla de fondos comunes de inversión — F-057.
 *
 * Doce columnas, decisión del dueño del producto (23/08/2026): fondo (con su clase, ya en el
 * nombre) · tipo de renta · moneda · horizonte · valor de cuotaparte con su fecha · las cuatro
 * variaciones · patrimonio · plazo de rescate · calificación. El resto de las 47 columnas de la
 * planilla —gerente, depositaria, comisiones, códigos— va a la ficha del fondo (`FichaFci.tsx`),
 * no acá.
 *
 * Sin columna de TIR ni nada parecido (regla 2): la columna de rendimiento es variación de
 * cuotaparte, una naturaleza propia que nunca comparte eje con la renta fija.
 */

import { useVirtualizer } from '@tanstack/react-virtual'
import type { ReactNode } from 'react'
import { useMemo, useRef, useState } from 'react'

import { fmtCompacto, fmtFecha, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import type { FondoFci, PlanillaFci } from '@/lib/fci'

type Campo =
  | 'fondo'
  | 'tipo_renta'
  | 'moneda'
  | 'vcp'
  | 'var_diaria_pct'
  | 'var_mes_pct'
  | 'var_anio_pct'
  | 'var_12m_pct'
  | 'patrimonio'
  | 'dias_para_rescatar'
type Direccion = 'asc' | 'desc'

interface Orden {
  campo: Campo | null
  direccion: Direccion
}

/** fondo · renta · moneda · horizonte · VCP · diaria · mes · año · 12m · patrimonio · rescate ·
 *  calificación. */
export const PLANTILLA_COLUMNAS_FCI = '1.4fr 120px 64px 76px 96px 76px 76px 76px 76px 96px 80px 96px'
const ALTO_FILA = 32
const ALTO_CONTENEDOR = 520

function comparar(a: FondoFci, b: FondoFci, campo: Campo, direccion: Direccion): number {
  const va = a[campo] as string | number | null
  const vb = b[campo] as string | number | null
  if (va === null && vb === null) return 0
  if (va === null) return 1
  if (vb === null) return -1

  const signo = direccion === 'asc' ? 1 : -1
  if (typeof va === 'number' && typeof vb === 'number') return signo * (va - vb)
  return signo * String(va).localeCompare(String(vb), 'es')
}

/** "31/07/26" → "31/07": la fecha base ya está acotada a un día hábil conocido, no hace falta el
 *  año en la cabecera de la columna. */
function fechaCorta(iso: string | null): string {
  if (!iso) return ''
  const partes = fmtFecha(iso).split('/')
  return partes.length === 3 ? `${partes[0]}/${partes[1]}` : ''
}

export function TablaFci({
  fondos,
  etiqueta,
  planilla,
  filtro,
  onAbrirFondo,
}: {
  /** Ya filtrados por tipo de renta y moneda por quien monta esto: el "de M" del conteo. */
  fondos: FondoFci[]
  /** El nombre de la pestaña activa, para el estado "sin filas hoy". */
  etiqueta: string
  /** Las fechas base de las variaciones, para rotular las cabeceras — `null` si la ingesta nunca
   *  corrió. */
  planilla: PlanillaFci | null
  /** El resto de los filtros de la barra, como predicado: el "N" del conteo sale del mismo cálculo
   *  que decide qué filas se ven, así no hay dos fuentes que puedan desalinearse. Va como función y
   *  no como el tipo `FiltrosFci` porque `components/` no importa de `features/` — eso invertiría
   *  la capa. Ausente = sin filtros, se muestra todo lo recibido. */
  filtro?: (fondo: FondoFci) => boolean
  onAbrirFondo: (codigoCafci: string) => void
}) {
  const [orden, setOrden] = useState<Orden>({ campo: null, direccion: 'asc' })
  const contenedorRef = useRef<HTMLDivElement>(null)

  const filtradas = useMemo(() => (filtro ? fondos.filter(filtro) : fondos), [fondos, filtro])

  const filasOrdenadas = useMemo(() => {
    if (orden.campo === null) return filtradas
    const campo = orden.campo
    return [...filtradas].sort((a, b) => comparar(a, b, campo, orden.direccion))
  }, [filtradas, orden])

  // Sobre `fondos`, antes de filtrar: la cobertura es del segmento y la moneda que se está mirando,
  // así el conteo de faltantes no cambia según los filtros que estén puestos.
  const notaCobertura = useMemo(() => {
    const sinFecha = fondos.filter((f) => f.fecha_vcp === null).length
    const sinCalificacion = fondos.filter((f) => f.calificacion === null).length
    const conDiscrepancia = fondos.filter((f) => f.discrepancia_moneda).length

    const partes: string[] = []
    if (sinFecha > 0) partes.push(`${fmtNumero(sinFecha, 0)} sin fecha de cotización`)
    if (sinCalificacion > 0) partes.push(`${fmtNumero(sinCalificacion, 0)} sin calificación informada`)
    if (conDiscrepancia > 0) {
      partes.push(`${fmtNumero(conDiscrepancia, 0)} con moneda distinta entre sección y fondo`)
    }
    return partes.join(' · ')
  }, [fondos])

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
      return { campo: null, direccion: 'asc' }
    })
  }

  const cabeceraMes = planilla?.fecha_base_mes ? ` (${fechaCorta(planilla.fecha_base_mes)})` : ''
  const cabeceraAnio = planilla?.fecha_base_anio ? ` (${fechaCorta(planilla.fecha_base_anio)})` : ''
  const cabecera12m = planilla?.fecha_base_12m ? ` (${fechaCorta(planilla.fecha_base_12m)})` : ''

  return (
    <div>
      <p className="mono" style={{ margin: '2px 0 2px', fontSize: 11.5, color: 'var(--dim)' }}>
        {fmtNumero(filasOrdenadas.length, 0)} de {fmtNumero(fondos.length, 0)} fondos
      </p>

      {planilla?.advertencia_distribucion && (
        <p style={{ margin: '0 0 6px', fontSize: 11, color: 'var(--dim)' }}>
          {planilla.advertencia_distribucion}
        </p>
      )}

      {notaCobertura && (
        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--dim)' }}>{notaCobertura}</p>
      )}

      {fondos.length === 0 ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          No hay {etiqueta} en la planilla de hoy.
        </p>
      ) : filasOrdenadas.length === 0 ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          Ningún fondo pasa los filtros activos.
        </p>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: PLANTILLA_COLUMNAS_FCI, gap: 0 }}>
            <Cabecera campo="fondo" orden={orden} onClick={alternarOrden}>fondo</Cabecera>
            <Cabecera campo="tipo_renta" orden={orden} onClick={alternarOrden}>renta</Cabecera>
            <Cabecera campo="moneda" orden={orden} onClick={alternarOrden}>moneda</Cabecera>
            <div className="mono" style={{ padding: '7px 8px', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--dim)', background: 'var(--pan2)', borderBottom: '1px solid var(--lin)' }}>
              horizonte
            </div>
            <Cabecera campo="vcp" orden={orden} onClick={alternarOrden} alinear="right">VCP /mil</Cabecera>
            <Cabecera campo="var_diaria_pct" orden={orden} onClick={alternarOrden} alinear="right">día</Cabecera>
            <Cabecera campo="var_mes_pct" orden={orden} onClick={alternarOrden} alinear="right">{`mes${cabeceraMes}`}</Cabecera>
            <Cabecera campo="var_anio_pct" orden={orden} onClick={alternarOrden} alinear="right">{`año${cabeceraAnio}`}</Cabecera>
            <Cabecera campo="var_12m_pct" orden={orden} onClick={alternarOrden} alinear="right">{`12m${cabecera12m}`}</Cabecera>
            <Cabecera campo="patrimonio" orden={orden} onClick={alternarOrden} alinear="right">patrimonio</Cabecera>
            <Cabecera campo="dias_para_rescatar" orden={orden} onClick={alternarOrden} alinear="right">rescate</Cabecera>
            <div className="mono" style={{ padding: '7px 8px', fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--dim)', background: 'var(--pan2)', borderBottom: '1px solid var(--lin)' }}>
              calificación
            </div>
          </div>

          <div ref={contenedorRef} style={{ height: ALTO_CONTENEDOR, overflow: 'auto', position: 'relative', borderTop: '1px solid var(--lin)' }}>
            <div style={{ height: virtualizador.getTotalSize(), position: 'relative' }}>
              {virtualizador.getVirtualItems().map((fila) => {
                const fondo = filasOrdenadas[fila.index]
                return (
                  <FilaFci
                    key={fondo.codigo_cafci}
                    fondo={fondo}
                    top={fila.start}
                    alto={fila.size}
                    onClick={() => onAbrirFondo(fondo.codigo_cafci)}
                  />
                )
              })}
            </div>
          </div>
        </>
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
        whiteSpace: 'nowrap',
      }}
    >
      {children}
      {indicador}
    </button>
  )
}

function celdaVariacion(valor: number | null) {
  const color = valor === null ? 'var(--tx)' : valor > 0 ? 'var(--pos)' : valor < 0 ? 'var(--neg)' : 'var(--tx)'
  const texto = valor === null ? SIN_DATO : `${valor > 0 ? '+' : ''}${fmtPct(valor)}`
  return { color, texto }
}

function FilaFci({
  fondo,
  top,
  alto,
  onClick,
}: {
  fondo: FondoFci
  top: number
  alto: number
  onClick: () => void
}) {
  const diaria = celdaVariacion(fondo.var_diaria_pct)
  const mes = celdaVariacion(fondo.var_mes_pct)
  const anio = celdaVariacion(fondo.var_anio_pct)
  const doceM = celdaVariacion(fondo.var_12m_pct)

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick()
      }}
      title={fondo.discrepancia_moneda ? `Moneda de sección ${fondo.moneda}, moneda de fondo ${fondo.moneda_fondo}` : undefined}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: alto,
        transform: `translateY(${top}px)`,
        display: 'grid',
        gridTemplateColumns: PLANTILLA_COLUMNAS_FCI,
        alignItems: 'center',
        borderBottom: '1px solid var(--lin)',
        cursor: 'pointer',
      }}
    >
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {fondo.fondo}
      </span>
      <span style={{ padding: '0 8px', fontSize: 11.5, whiteSpace: 'nowrap' }}>{fondo.tipo_renta}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12 }}>
        {fondo.moneda}
        {fondo.discrepancia_moneda ? ' ⚠' : ''}
      </span>
      <span style={{ padding: '0 8px', fontSize: 11.5, whiteSpace: 'nowrap' }}>{fondo.horizonte ?? SIN_DATO}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }} title={fondo.fecha_vcp ? `al ${fmtFecha(fondo.fecha_vcp)}` : 'sin fecha'}>
        {fmtNumero(fondo.vcp)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: diaria.color }}>{diaria.texto}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: mes.color }}>{mes.texto}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: anio.color }}>{anio.texto}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: doceM.color }}>{doceM.texto}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>{fmtCompacto(fondo.patrimonio)}</span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }} title={fondo.plazo_liq !== null ? `Plazo Liq. crudo: ${fondo.plazo_liq}` : undefined}>
        {fondo.dias_para_rescatar === null ? SIN_DATO : fmtNumero(fondo.dias_para_rescatar, 0)}
      </span>
      <span style={{ padding: '0 8px', fontSize: 11.5, whiteSpace: 'nowrap' }}>
        {fondo.calificacion ?? 'no informada'}
      </span>
    </div>
  )
}
