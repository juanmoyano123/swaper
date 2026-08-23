/**
 * "Revaluar a hoy" (GWT-2) — se monta recién cuando el asesor lo pide, para que el detalle por
 * defecto (`VistaCongelada`) no dispare ningún pedido de mercado (GWT-1). Las dos puntas se miden
 * con los mismos servicios que el resto de la aplicación: `useCarteraCargadaValuada` para el
 * origen cargada (el mismo hook del pipeline vivo, sobre las mismas posiciones crudas guardadas),
 * el universo y el tipo de cambio de hoy para el origen armador.
 */

import { useMemo, useState } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { useCarteraCargadaValuada } from '@/features/cartera-diagnostico/hooks/useCarteraCargadaValuada'
import { useEspeciesUniverso } from '@/lib/cartera/hooks/useEspeciesUniverso'
import { useTipoDeCambio } from '@/lib/cartera/hooks/useTipoDeCambio'
import { useFondosFci } from '@/lib/fci'
import { fmtFechaHora, fmtMonto, fmtNumero, SIN_DATO } from '@/lib/fmt'
import { useRentaVariable } from '@/lib/rentaVariable'

import type { SnapshotArmador, SnapshotCargada, SnapshotCartera } from '../lib/esquemaSnapshot'
import {
  comparablesDesdeSnapshotArmador,
  comparablesDesdeSnapshotCargada,
  comparablesDesdeValuacionHoy,
  compararValuaciones,
  revaluarResueltasHoy,
  type ComparacionValuaciones,
} from '../lib/revaluacion'
import { Boton } from './Boton'

export function Revaluacion({ snapshot, snapshotEn }: { snapshot: SnapshotCartera; snapshotEn: string }) {
  const [activo, setActivo] = useState(false)

  if (!activo) {
    return (
      <Boton onClick={() => setActivo(true)} aria-label="Revaluar a hoy">
        Revaluar a hoy
      </Boton>
    )
  }

  return snapshot.origen === 'cargada' ? (
    <RevaluacionCargada snapshot={snapshot} snapshotEn={snapshotEn} />
  ) : (
    <RevaluacionArmador snapshot={snapshot} snapshotEn={snapshotEn} />
  )
}

function RevaluacionCargada({ snapshot, snapshotEn }: { snapshot: SnapshotCargada; snapshotEn: string }) {
  const { valuacion, tipoDeCambio, porTicker, cargando, error } = useCarteraCargadaValuada(snapshot.posiciones)

  const comparacion = useMemo(() => {
    if (!valuacion) return null
    const congeladas = comparablesDesdeSnapshotCargada(snapshot)
    const hoy = comparablesDesdeValuacionHoy(snapshot.posiciones, valuacion, porTicker)
    return compararValuaciones(congeladas, hoy)
  }, [snapshot, valuacion, porTicker])

  if (cargando) return <EstadoCarga que="los precios de hoy" />
  if (error) return <EstadoError error={error} />
  if (!comparacion) return null

  return (
    <TablaComparacion
      comparacion={comparacion}
      snapshotEn={snapshotEn}
      tcGuardado={snapshot.tipoDeCambio}
      tcHoy={tipoDeCambio}
    />
  )
}

function RevaluacionArmador({ snapshot, snapshotEn }: { snapshot: SnapshotArmador; snapshotEn: string }) {
  const rentaFija = useEspeciesUniverso()
  const acciones = useRentaVariable('accion')
  const cedears = useRentaVariable('cedear')
  const tipoDeCambio = useTipoDeCambio()
  // `null` trae todos los fondos (F-046): un mandato guardado puede tener un FCI de cualquier tipo
  // de renta, y no hay de dónde sacar el segmento sin volver a resolver la cartera entera.
  const fondosFci = useFondosFci(null)

  const cargando =
    rentaFija.isPending || acciones.isPending || cedears.isPending || tipoDeCambio.isPending || fondosFci.isPending
  const error = rentaFija.error ?? acciones.error ?? cedears.error ?? tipoDeCambio.error ?? fondosFci.error ?? null

  const porTickerHoy = useMemo(() => {
    const mapa = new Map<string, { precio: number | null; moneda_cotizacion: string | null }>()
    for (const e of rentaFija.data ?? []) mapa.set(e.ticker, { precio: e.precio, moneda_cotizacion: e.moneda_cotizacion })
    for (const e of acciones.data ?? []) mapa.set(e.ticker, { precio: e.precio, moneda_cotizacion: e.moneda_cotizacion })
    for (const e of cedears.data ?? []) mapa.set(e.ticker, { precio: e.precio, moneda_cotizacion: e.moneda_cotizacion })
    return mapa
  }, [rentaFija.data, acciones.data, cedears.data])

  const porCodigoCafciHoy = useMemo(() => {
    const mapa = new Map<string, { vcp: number | null; moneda: string }>()
    for (const f of fondosFci.data ?? []) mapa.set(f.codigo_cafci, { vcp: f.vcp, moneda: f.moneda })
    return mapa
  }, [fondosFci.data])

  const tcHoy = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const comparacion = useMemo(() => {
    if (cargando) return null
    const congeladas = comparablesDesdeSnapshotArmador(snapshot)
    const hoy = revaluarResueltasHoy(snapshot.resueltas, porTickerHoy, tcHoy, porCodigoCafciHoy)
    return compararValuaciones(congeladas, hoy)
  }, [snapshot, porTickerHoy, tcHoy, porCodigoCafciHoy, cargando])

  if (cargando) return <EstadoCarga que="los precios de hoy" />
  if (error) return <EstadoError error={error} />
  if (!comparacion) return null

  return (
    <TablaComparacion
      comparacion={comparacion}
      snapshotEn={snapshotEn}
      tcGuardado={snapshot.tipoDeCambio}
      tcHoy={tcHoy}
    />
  )
}

function colorDelta(delta: number | null): string {
  if (delta === null) return 'var(--sd)'
  if (delta > 0) return 'var(--pos)'
  if (delta < 0) return 'var(--neg)'
  return 'var(--sd)'
}

function TablaComparacion({
  comparacion,
  snapshotEn,
  tcGuardado,
  tcHoy,
}: {
  comparacion: ComparacionValuaciones
  snapshotEn: string
  tcGuardado: number | null
  tcHoy: number | null
}) {
  const esParcial = comparacion.excluidosDelTotal.length > 0

  return (
    <div aria-label="Revaluación a hoy" style={{ display: 'grid', gap: 10, marginTop: 8 }}>
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
        Guardada: {fmtFechaHora(snapshotEn)} · TC {tcGuardado !== null ? fmtNumero(tcGuardado, 2) : SIN_DATO}
        {' — '}
        Hoy · TC {tcHoy !== null ? fmtNumero(tcHoy, 2) : SIN_DATO}
      </p>

      <ul role="list" aria-label="Delta por posición" style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 4 }}>
        {comparacion.posiciones.map((p) => (
          <li
            key={p.ticker}
            role="listitem"
            className="mono"
            style={{ fontSize: 11, color: colorDelta(p.delta) }}
          >
            {p.ticker}: {p.invertidoGuardado !== null && p.monedaGuardada ? fmtMonto(p.invertidoGuardado, p.monedaGuardada) : SIN_DATO}
            {' → '}
            {p.invertidoHoy !== null && p.monedaHoy ? fmtMonto(p.invertidoHoy, p.monedaHoy) : SIN_DATO}
            {p.delta !== null && ` (Δ ${p.delta > 0 ? '+' : ''}${fmtNumero(p.delta, 2)})`}
            {p.motivo && ` — ${p.motivo}`}
          </li>
        ))}
      </ul>

      <p className="mono" style={{ margin: 0, fontSize: 13, fontWeight: 600, color: colorDelta(comparacion.deltaTotalUsd) }}>
        Total: {fmtMonto(comparacion.totalUsdGuardado, 'usd')} → {fmtMonto(comparacion.totalUsdHoy, 'usd')}
        {' '}
        (Δ {comparacion.deltaTotalUsd > 0 ? '+' : ''}
        {fmtMonto(comparacion.deltaTotalUsd, 'usd')})
        {esParcial && ' (parcial)'}
      </p>

      {esParcial && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--ac2)' }}>
          No entran al total: {comparacion.excluidosDelTotal.map((e) => `${e.ticker} (${e.motivo})`).join(', ')}.
        </p>
      )}
    </div>
  )
}
