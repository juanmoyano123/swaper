/**
 * El bloque separado de renta variable — F-026, mockup A4 del design system.
 *
 * Acciones (69 verificadas) y CEDEARs (683 verificados), con subtotal propio, que suma al monto
 * total de la cartera y **queda afuera de todo cálculo de renta fija**: sin TIR, sin duración, sin
 * cupón, sin participar de ninguno de los cuatro rendimientos por naturaleza de tasa (regla 2 del
 * dominio). `posicionesRentaFija` (store, base común de la Tanda 9) ya excluye estas posiciones del
 * resolver de bonos y del calendario de cupones — este componente no repite esa frontera, la usa.
 *
 * ## Dos ausencias deliberadas contra el mockup, no dos olvidos
 *
 * 1. **Sin distribución por país ni por rubro.** El mockup A4 y la spec (F-026) piden esas dos
 *    distribuciones, pero `EspecieRentaVariable` (backend, F-052) sólo trae ticker, precio, moneda,
 *    cierre anterior, variación, volumen, puntas y operaciones — ni país, ni rubro, ni el nombre de
 *    la empresa. Construir la distribución hoy sería una pantalla con "país no informado" en el
 *    100% de las especies (regla 1: nunca inventar un dato, ni derivarlo del ticker). Queda para
 *    F-053, que trae la ficha de instrumento con esos datos recopilados aparte. Anotado en
 *    `claude-docs/planning/plan-ejecucion-tandas.md`, duda de solape 6.
 *
 *    La misma ausencia de datos deja sin "nombre/emisor" a la tarjeta del mockup: donde el diseño
 *    pide el emisor, acá va la clase (`Acción` / `CEDEAR`), que es el único dato descriptivo que
 *    existe hoy — no se inventa un nombre a partir del ticker.
 *
 * 2. **"Div. est." siempre en `SIN_DATO`.** No hay fuente de dividendos en el universo consolidado.
 *    Mostrar un estimado sería inventar un dato (regla 1); se declara `s/d` con una nota, siempre.
 *    Por la misma razón no se dibuja el calendario de doce celdas de balances/dividendos del
 *    mockup: es de F-027 (calendario de balances), que todavía no corrió.
 *
 * ## Selección de peso
 *
 * `PosicionArmador.peso` es el pedido sobre la cartera **entera** (store, `alternarRentaVariable`),
 * el mismo eje que usa la renta fija — así el 100% es del total y no de cada bloque. Acá se muestra
 * además el **peso real dentro del bloque** (`resolverRentaVariable`, distinto de `pesoReal` de
 * `resolver.ts`, que reparte sobre el total de la cartera): es la cifra que importa para juzgar el
 * bloque de renta variable en sí mismo.
 */

import { type ReactNode, useMemo, useState } from 'react'

import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'
import { fmtMonto, fmtPct, SIN_DATO } from '@/lib/fmt'
import { type EspecieRentaVariable, useRentaVariable } from '@/lib/rentaVariable'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useTipoDeCambio } from '../hooks/useTipoDeCambio'
import { resolverRentaVariable, subtotalRentaVariableUsd, type PosicionRvResuelta } from '../lib/resolverRentaVariable'
import { posicionesRentaVariable, useArmador, useArmadorAcciones } from '../store/carteraStore'

const CLASES: { clave: 'accion' | 'cedear'; etiqueta: string }[] = [
  { clave: 'accion', etiqueta: 'Acciones' },
  { clave: 'cedear', etiqueta: 'CEDEARs' },
]

export function BloqueRentaVariable() {
  const { pos, montoTotal } = useArmador()
  const { alternarRentaVariable } = useArmadorAcciones()
  const abrirInstrumento = useAbrirInstrumento()

  const acciones = useRentaVariable('accion')
  const cedears = useRentaVariable('cedear')
  const tipoDeCambio = useTipoDeCambio()
  // Sólo lectura: F-021/F-020 ya extrajeron este hook para no repetir el pipeline. Se usa acá
  // únicamente para declarar cómo se compone el monto total (GWT-4) — este bloque no recalcula
  // nada de renta fija.
  const { totalInvertidoUsd: subtotalRfUsd, hayAlgunaResuelta: hayRfResuelta } = useCarteraResuelta()

  const [clasePicker, setClasePicker] = useState<'accion' | 'cedear'>('accion')
  const [busqueda, setBusqueda] = useState('')

  const porTicker = useMemo(() => {
    const mapa = new Map<string, EspecieRentaVariable>()
    for (const especie of acciones.data ?? []) mapa.set(especie.ticker, especie)
    for (const especie of cedears.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [acciones.data, cedears.data])

  const posicionesRv = posicionesRentaVariable(pos)
  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const resueltas = useMemo(() => {
    const entradas = posicionesRv.map((p) => {
      const especie = porTicker.get(p.ticker)
      return {
        ticker: p.ticker,
        peso: p.peso,
        precio: especie?.precio ?? null,
        monedaCotizacion: especie?.moneda_cotizacion ?? null,
      }
    })
    return resolverRentaVariable(entradas, montoTotal, tcValor)
  }, [posicionesRv, porTicker, montoTotal, tcValor])

  const subtotalRvUsd = subtotalRentaVariableUsd(resueltas)
  const hayAlgunaRvResuelta = resueltas.some((r) => r.invertidoUsd !== null)

  // GWT-4: el monto total incluye las dos porciones, cada una con su subtotal identificado. Sin
  // ninguna de las dos resuelta no hay total que declarar — no es 0, es sin dato.
  const totalUsd =
    hayRfResuelta || hayAlgunaRvResuelta ? (hayRfResuelta ? subtotalRfUsd : 0) + (subtotalRvUsd ?? 0) : null

  const yaEnCartera = new Set(posicionesRv.map((p) => p.ticker))
  const listaPicker = (clasePicker === 'accion' ? acciones.data : cedears.data) ?? []
  const cargandoPicker = clasePicker === 'accion' ? acciones.isPending : cedears.isPending
  const erroresPicker = clasePicker === 'accion' ? acciones.isError : cedears.isError
  const filtradaPicker =
    busqueda.trim() === ''
      ? listaPicker
      : listaPicker.filter((e) => e.ticker.toLowerCase().includes(busqueda.trim().toLowerCase()))

  return (
    <div>
      <header style={{ marginBottom: 8 }}>
        <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>
          Acciones y CEDEARs. Fuera del cálculo de renta fija, de la TIR, la duración y los cuatro
          rendimientos por naturaleza de tasa.
        </p>
      </header>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, marginBottom: 12 }}>
        <Campo etiqueta="Renta fija (USD)">{hayRfResuelta ? fmtMonto(subtotalRfUsd, 'usd') : SIN_DATO}</Campo>
        <Campo etiqueta="Renta variable (USD)">{subtotalRvUsd !== null ? fmtMonto(subtotalRvUsd, 'usd') : SIN_DATO}</Campo>
        <Campo etiqueta="Total de la cartera (USD)">{totalUsd !== null ? fmtMonto(totalUsd, 'usd') : SIN_DATO}</Campo>
      </div>

      {posicionesRv.length === 0 ? (
        <p style={{ margin: '0 0 12px', fontSize: 12, color: 'var(--sd)' }}>
          Sin acciones ni CEDEARs en la cartera. Buscá un ticker abajo para sumarlo.
        </p>
      ) : (
        <div
          role="list"
          aria-label="Renta variable en la cartera"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))',
            gap: 10,
            background: 'var(--pan2)',
            padding: 10,
            borderRadius: 4,
            marginBottom: 14,
          }}
        >
          {posicionesRv.map((posicion) => (
            <TarjetaRentaVariable
              key={posicion.ticker}
              especie={porTicker.get(posicion.ticker) ?? null}
              resuelta={resueltas.find((r) => r.ticker === posicion.ticker) ?? null}
              onAbrir={() => abrirInstrumento(posicion.ticker)}
              onQuitar={() => alternarRentaVariable(posicion.ticker)}
            />
          ))}
        </div>
      )}

      <div role="radiogroup" aria-label="Clase de renta variable a buscar" style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
        {CLASES.map(({ clave, etiqueta }) => {
          const activa = clave === clasePicker
          return (
            <button
              key={clave}
              type="button"
              role="radio"
              aria-checked={activa}
              onClick={() => setClasePicker(clave)}
              style={{
                font: `${activa ? 600 : 400} 12px/1 inherit`,
                color: activa ? 'var(--bg)' : 'var(--dim)',
                background: activa ? 'var(--ac)' : 'transparent',
                border: `1px solid ${activa ? 'var(--ac)' : 'var(--lin)'}`,
                borderRadius: 3,
                padding: '5px 10px',
                cursor: 'pointer',
              }}
            >
              {etiqueta}
            </button>
          )
        })}
        <input
          type="text"
          value={busqueda}
          onChange={(evento) => setBusqueda(evento.target.value)}
          placeholder="Buscar ticker…"
          aria-label="Buscar acción o CEDEAR por ticker"
          className="mono"
          style={{
            marginLeft: 8,
            flex: 1,
            minWidth: 120,
            fontSize: 12,
            color: 'var(--tx)',
            background: 'var(--pan2)',
            border: '1px solid var(--lin)',
            borderRadius: 3,
            padding: '4px 8px',
          }}
        />
      </div>

      {cargandoPicker && <p style={{ fontSize: 11.5, color: 'var(--dim)' }}>Cargando especies…</p>}
      {erroresPicker && <p style={{ fontSize: 11.5, color: 'var(--neg)' }}>No se pudo traer el universo de renta variable.</p>}
      {!cargandoPicker && !erroresPicker && (
        <div
          role="list"
          aria-label={`Resultados de ${clasePicker === 'accion' ? 'acciones' : 'CEDEARs'}`}
          style={{ maxHeight: 176, overflowY: 'auto', border: '1px solid var(--lin)', borderRadius: 4 }}
        >
          {filtradaPicker.length === 0 ? (
            <p style={{ margin: 0, padding: '8px 10px', fontSize: 11.5, color: 'var(--dim)' }}>
              Ningún ticker coincide con la búsqueda.
            </p>
          ) : (
            filtradaPicker.map((especie) => (
              <FilaPicker
                key={especie.ticker}
                especie={especie}
                enCartera={yaEnCartera.has(especie.ticker)}
                onAbrir={() => abrirInstrumento(especie.ticker)}
                onAlternar={() => alternarRentaVariable(especie.ticker)}
              />
            ))
          )}
        </div>
      )}
    </div>
  )
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </span>
      <span className="mono" style={{ fontSize: 14, color: 'var(--tx)' }}>
        {children}
      </span>
    </div>
  )
}

function FilaPicker({
  especie,
  enCartera,
  onAbrir,
  onAlternar,
}: {
  especie: EspecieRentaVariable
  enCartera: boolean
  onAbrir: () => void
  onAlternar: () => void
}) {
  return (
    <div
      role="listitem"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '5px 8px',
        borderBottom: '1px solid var(--lin)',
      }}
    >
      <button
        type="button"
        onClick={onAbrir}
        className="mono"
        style={{
          font: 'inherit',
          fontSize: 12,
          color: 'var(--tx)',
          background: 'transparent',
          border: 'none',
          textDecoration: 'underline',
          textUnderlineOffset: 2,
          cursor: 'pointer',
          padding: 0,
        }}
      >
        {especie.ticker}
      </button>
      <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)', marginLeft: 'auto' }}>
        {especie.precio !== null ? especie.precio : SIN_DATO}
      </span>
      <button
        type="button"
        onClick={onAlternar}
        aria-label={enCartera ? `sacar ${especie.ticker} de la cartera` : `agregar ${especie.ticker} a la cartera`}
        style={{
          font: 'inherit',
          fontSize: 12,
          color: enCartera ? 'var(--ac)' : 'var(--dim)',
          background: 'transparent',
          border: `1px solid ${enCartera ? 'var(--ac)' : 'var(--lin)'}`,
          borderRadius: 3,
          padding: '2px 7px',
          cursor: 'pointer',
        }}
      >
        {enCartera ? '✓' : '+'}
      </button>
    </div>
  )
}

function TarjetaRentaVariable({
  especie,
  resuelta,
  onAbrir,
  onQuitar,
}: {
  especie: EspecieRentaVariable | null
  resuelta: PosicionRvResuelta | null
  onAbrir: () => void
  onQuitar: () => void
}) {
  const variacionPct = especie?.variacion == null ? null : especie.variacion * 100
  const colorVariacion =
    variacionPct === null ? 'var(--ac2)' : variacionPct > 0 ? 'var(--pos)' : variacionPct < 0 ? 'var(--neg)' : 'var(--tx)'
  const textoVariacion = variacionPct === null ? SIN_DATO : `${variacionPct > 0 ? '+' : ''}${fmtPct(variacionPct)}`
  const ticker = especie?.ticker ?? resuelta?.ticker ?? ''

  return (
    <article
      aria-label={ticker}
      style={{
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: '8px 10px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <button
          type="button"
          onClick={onAbrir}
          className="mono"
          style={{
            font: '600 14px inherit',
            color: 'var(--tx)',
            background: 'transparent',
            border: 'none',
            textDecoration: 'underline',
            textUnderlineOffset: 2,
            cursor: 'pointer',
            padding: 0,
          }}
        >
          {ticker}
        </button>
        <span style={{ fontSize: 10.5, color: 'var(--dim)' }}>
          {/* Sin emisor en el dato (ver comentario del módulo): la clase es lo único descriptivo. */}
          {especie ? (especie.clase_activo === 'accion' ? 'Acción' : 'CEDEAR') : SIN_DATO}
        </span>
        <span className="mono" style={{ marginLeft: 'auto', fontSize: 12, color: colorVariacion }}>
          {textoVariacion}
        </span>
        <button
          type="button"
          onClick={onQuitar}
          aria-label={`sacar ${ticker} de la cartera`}
          style={{ font: 'inherit', fontSize: 13, border: 'none', background: 'transparent', color: 'var(--dim)', cursor: 'pointer' }}
        >
          ×
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, marginTop: 8 }}>
        <Metrica etiqueta="Peso">{resuelta?.pesoReal !== null && resuelta?.pesoReal !== undefined ? fmtPct(resuelta.pesoReal) : SIN_DATO}</Metrica>
        <Metrica etiqueta="Invertido">
          {resuelta?.invertidoUsd !== null && resuelta?.invertidoUsd !== undefined ? fmtMonto(resuelta.invertidoUsd, 'usd') : SIN_DATO}
        </Metrica>
        {/* Siempre s/d: no hay fuente de dividendos en el universo consolidado. Nunca se estima
            (regla 1 del dominio) — ver comentario del módulo. */}
        <Metrica etiqueta="Div. est." nota="Sin fuente de dividendos: nunca se estima.">
          {SIN_DATO}
        </Metrica>
      </div>
    </article>
  )
}

function Metrica({ etiqueta, nota, children }: { etiqueta: string; nota?: string; children: ReactNode }) {
  return (
    <div title={nota} style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: 9.5, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {etiqueta}
      </span>
      <span className="mono" style={{ fontSize: 12, color: 'var(--tx)' }}>
        {children}
      </span>
    </div>
  )
}
