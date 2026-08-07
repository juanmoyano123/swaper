/**
 * La grilla de renta variable — F-052.
 *
 * Zona compartida a propósito: el monitor (F-052) la monta hoy y el armador (F-026, tanda 9) la
 * reusa — F-026 se engancha acá, no en `features/monitor/`. No importa nada de `features/**`: la
 * navegación entra por prop, igual mecánica que `TablaUniverso.tsx` del monitor (leerla como
 * patrón, copiada y no importada).
 *
 * Sin columna de rendimiento, ni de duración, ni de paridad, ni de vencimiento (regla 2): una
 * acción no tiene ninguna de esas magnitudes y no se pone nada en su lugar. La única columna
 * comparable de volumen es `volumen_usd` (regla 3): el crudo viaja en el dato para poder auditar,
 * pero no hay columna que lo muestre ni que ordene por él.
 *
 * `etiqueta` es el nombre de la pestaña activa ("Acciones", "CEDEARs"), para el párrafo del estado
 * "sin filas hoy": sin esta prop el componente no tiene forma de saber en qué pestaña está, y el
 * texto quedaría genérico. El monitor la saca de `nombreSegmento`; **F-026 (armador, tanda 9) la
 * va a necesitar igual**, con el nombre que le corresponda en su propio contexto.
 */

import { useVirtualizer } from '@tanstack/react-virtual'
import type { ReactNode } from 'react'
import { useMemo, useRef, useState } from 'react'

import { fmtCompacto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'

type Campo = 'ticker' | 'precio' | 'variacion' | 'volumen_usd' | 'px_bid' | 'px_ask' | 'operaciones'
type Direccion = 'asc' | 'desc'

interface Orden {
  campo: Campo | null
  direccion: Direccion
}

/** ticker · precio · variación · volumen USD · compra · venta · operaciones · relleno. */
export const PLANTILLA_COLUMNAS_RV = '64px 116px 96px 100px 92px 92px 92px 1fr'
const ALTO_FILA = 32
const ALTO_CONTENEDOR = 520

/** `null` siempre al final, sin importar la dirección: un dato que falta no es el más chico ni el
 * más grande, así que no puede decidir el orden. Misma regla que `TablaUniverso.tsx`. */
function comparar(a: EspecieRentaVariable, b: EspecieRentaVariable, campo: Campo, direccion: Direccion): number {
  const va = a[campo] as string | number | null
  const vb = b[campo] as string | number | null
  if (va === null && vb === null) return 0
  if (va === null) return 1
  if (vb === null) return -1

  const signo = direccion === 'asc' ? 1 : -1
  if (typeof va === 'number' && typeof vb === 'number') return signo * (va - vb)
  return signo * String(va).localeCompare(String(vb), 'es')
}

export function TablaRentaVariable({
  especies,
  etiqueta,
  onAbrirTicker,
}: {
  especies: EspecieRentaVariable[]
  /** El nombre de la pestaña activa, para el estado "sin filas hoy" ("No hay {etiqueta} en el
   * universo de hoy."). El monitor pasa `nombreSegmento(clase)`. */
  etiqueta: string
  /** Qué hacer al clickear una fila. El monitor pasa `useAbrirInstrumento()`; F-026 pasará lo suyo. */
  onAbrirTicker: (ticker: string) => void
}) {
  const [orden, setOrden] = useState<Orden>({ campo: null, direccion: 'asc' })
  const contenedorRef = useRef<HTMLDivElement>(null)

  const filasOrdenadas = useMemo(() => {
    if (orden.campo === null) return especies
    const campo = orden.campo
    return [...especies].sort((a, b) => comparar(a, b, campo, orden.direccion))
  }, [especies, orden])

  // GWT-3: lo vacío se cuenta, no se disimula. Sólo los términos con conteo mayor a cero aparecen.
  const notaCobertura = useMemo(() => {
    const sinCierreAnterior = especies.filter((e) => e.cierre_anterior === null).length
    const sinPuntas = especies.filter((e) => e.px_bid === null && e.px_ask === null).length
    const sinVolumenUsd = especies.filter((e) => e.volumen_usd === null).length

    const partes: string[] = []
    if (sinCierreAnterior > 0) partes.push(`${fmtNumero(sinCierreAnterior, 0)} sin cierre anterior (sin variación)`)
    if (sinPuntas > 0) partes.push(`${fmtNumero(sinPuntas, 0)} sin puntas`)
    if (sinVolumenUsd > 0) partes.push(`${fmtNumero(sinVolumenUsd, 0)} sin volumen en dólares`)
    return partes.join(' · ')
  }, [especies])

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
      <p className="mono" style={{ margin: '2px 0 2px', fontSize: 11.5, color: 'var(--dim)' }}>
        {fmtNumero(filasOrdenadas.length, 0)} de {fmtNumero(especies.length, 0)} especies
      </p>

      {notaCobertura && (
        <p style={{ margin: '0 0 8px', fontSize: 11, color: 'var(--dim)' }}>{notaCobertura}</p>
      )}

      {especies.length === 0 ? (
        <p style={{ margin: '18px 0', fontSize: 12.5, color: 'var(--dim)' }}>
          No hay {etiqueta} en el universo de hoy.
        </p>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: PLANTILLA_COLUMNAS_RV, gap: 0 }}>
            <Cabecera campo="ticker" orden={orden} onClick={alternarOrden}>ticker</Cabecera>
            <Cabecera campo="precio" orden={orden} onClick={alternarOrden} alinear="right">precio</Cabecera>
            <Cabecera campo="variacion" orden={orden} onClick={alternarOrden} alinear="right">variación</Cabecera>
            <Cabecera campo="volumen_usd" orden={orden} onClick={alternarOrden} alinear="right">volumen USD</Cabecera>
            <Cabecera campo="px_bid" orden={orden} onClick={alternarOrden} alinear="right">compra</Cabecera>
            <Cabecera campo="px_ask" orden={orden} onClick={alternarOrden} alinear="right">venta</Cabecera>
            <Cabecera campo="operaciones" orden={orden} onClick={alternarOrden} alinear="right">operaciones</Cabecera>
            {/* Relleno: la cabecera son botones con fondo y borde propios, así que la columna vacía
                necesita su celda para que la línea del header llegue pareja hasta el final. */}
            <div aria-hidden style={{ background: 'var(--pan2)', borderBottom: '1px solid var(--lin)' }} />
          </div>

          <div ref={contenedorRef} style={{ height: ALTO_CONTENEDOR, overflow: 'auto', position: 'relative', borderTop: '1px solid var(--lin)' }}>
            <div style={{ height: virtualizador.getTotalSize(), position: 'relative' }}>
              {virtualizador.getVirtualItems().map((fila) => {
                const especie = filasOrdenadas[fila.index]
                return (
                  <FilaRentaVariable
                    key={especie.ticker}
                    especie={especie}
                    top={fila.start}
                    alto={fila.size}
                    onClick={() => onAbrirTicker(especie.ticker)}
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
      }}
    >
      {children}
      {indicador}
    </button>
  )
}

/** La fila suelta, exportada para que F-026 pueda componerla distinto. */
export function FilaRentaVariable({
  especie,
  top,
  alto,
  onClick,
}: {
  especie: EspecieRentaVariable
  top: number
  alto: number
  onClick: () => void
}) {
  const variacionPct = especie.variacion === null ? null : especie.variacion * 100
  const colorVariacion = variacionPct === null ? 'var(--tx)' : variacionPct > 0 ? 'var(--pos)' : variacionPct < 0 ? 'var(--neg)' : 'var(--tx)'
  const textoVariacion =
    variacionPct === null ? SIN_DATO : `${variacionPct > 0 ? '+' : ''}${fmtPct(variacionPct)}`

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') onClick()
      }}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: alto,
        transform: `translateY(${top}px)`,
        display: 'grid',
        gridTemplateColumns: PLANTILLA_COLUMNAS_RV,
        alignItems: 'center',
        borderBottom: '1px solid var(--lin)',
        cursor: 'pointer',
      }}
    >
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, whiteSpace: 'nowrap' }}>
        {especie.ticker}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.precio)}
        {especie.moneda_cotizacion && <span style={{ color: 'var(--dim)' }}> {especie.moneda_cotizacion}</span>}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right', color: colorVariacion }}>
        {textoVariacion}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtCompacto(especie.volumen_usd)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.px_bid)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.px_ask)}
      </span>
      <span className="mono" style={{ padding: '0 8px', fontSize: 12, textAlign: 'right' }}>
        {fmtNumero(especie.operaciones, 0)}
      </span>
    </div>
  )
}
