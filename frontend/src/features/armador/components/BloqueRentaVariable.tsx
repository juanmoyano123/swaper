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
 *
 * **Etapa 3 del rediseño**: hasta acá el peso pedido de una acción sólo se podía cambiar con
 * "Equiponderar" o agregando/sacando papeles — `fijarPeso` del store ya era agnóstico de clase,
 * pero `CarteraEditable` (su único llamador) filtra la renta variable, así que nunca llegaba un
 * input. La tarjeta gana su propio "% pedido", con el mismo trato visual que el de
 * `CarteraEditable.tsx` (mono, `--ac`, resaltado si difiere del real más de
 * `TOLERANCIA_DIFERENCIA_FILA`). La cabecera suma el mix pedido y el mix real (sobre lo
 * efectivamente invertido) — dos cuentas distintas que pueden no coincidir, y las dos se muestran.
 */

import { type ReactNode, useMemo, useState } from 'react'

import { useAbrirInstrumento } from '@/features/instrumento/useAbrirInstrumento'
import { fmtFecha, fmtMonto, fmtPct, SIN_DATO } from '@/lib/fmt'
import { type EspecieRentaVariable, useRentaVariable } from '@/lib/rentaVariable'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useTipoDeCambio } from '../hooks/useTipoDeCambio'
import { sumaPesos } from '../lib/mix'
import { resolverRentaVariable, subtotalRentaVariableUsd, type PosicionRvResuelta } from '../lib/resolverRentaVariable'
import {
  posicionesRentaVariable,
  useArmador,
  useArmadorAcciones,
  type PosicionArmador,
} from '../store/carteraStore'

/** Mismo umbral que `CarteraEditable.tsx` (design system, sección A8): a partir de acá la
 *  diferencia entre pedido y real se marca, no antes. */
const TOLERANCIA_DIFERENCIA_FILA = 0.6

const CLASES: { clave: 'accion' | 'cedear'; etiqueta: string }[] = [
  { clave: 'accion', etiqueta: 'Acciones' },
  { clave: 'cedear', etiqueta: 'CEDEARs' },
]

const estiloSelectPicker = {
  minWidth: 140,
  font: 'inherit',
  fontSize: 12,
  padding: '4px 8px',
  borderRadius: 3,
  border: '1px solid var(--lin)',
  background: 'var(--pan2)',
  color: 'var(--tx)',
} as const

export function BloqueRentaVariable() {
  const { pos, montoTotal } = useArmador()
  const { alternarRentaVariable, fijarPeso } = useArmadorAcciones()
  const abrirInstrumento = useAbrirInstrumento()

  const acciones = useRentaVariable('accion')
  const cedears = useRentaVariable('cedear')
  const tipoDeCambio = useTipoDeCambio()
  // Sólo lectura: F-021/F-020 ya extrajeron este hook para no repetir el pipeline. Se usa acá
  // únicamente para declarar cómo se compone el monto total (GWT-4) — este bloque no recalcula
  // nada de renta fija.
  const { totalInvertidoUsd: subtotalRfUsd, hayAlgunaResuelta: hayRfResuelta } = useCarteraResuelta()

  const [clasePicker, setClasePickerCrudo] = useState<'accion' | 'cedear'>('accion')
  const [busqueda, setBusqueda] = useState('')
  const [sectorFiltro, setSectorFiltro] = useState<string | null>(null)
  const [industriaFiltro, setIndustriaFiltro] = useState<string | null>(null)

  // Sector y rubro son del perfil de empresa (Etapa 5): las opciones de una clase no tienen por
  // qué existir en la otra, así que cambiar de Acciones a CEDEARs limpia la selección en vez de
  // dejar un filtro activo que no matchea nada sin que se entienda por qué.
  function setClasePicker(clase: 'accion' | 'cedear') {
    setClasePickerCrudo(clase)
    setSectorFiltro(null)
    setIndustriaFiltro(null)
  }

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

  // Mix pedido: sobre `peso` (puntos porcentuales sobre la cartera entera), sin pasar por precio
  // ni tipo de cambio — siempre calculable si hay posiciones.
  const pesoRvPedido = sumaPesos(posicionesRv)
  const pesoRfPedido = sumaPesos(pos) - pesoRvPedido

  // Mix real: sobre lo efectivamente invertido en dólares. Es otra cuenta — puede no coincidir
  // con el mix pedido si falta precio, tipo de cambio o si el redondeo por lámina movió algo — y
  // sin `totalUsd` no hay de qué ser un porcentaje.
  const mixRealRf = totalUsd !== null && totalUsd > 0 && hayRfResuelta ? (subtotalRfUsd / totalUsd) * 100 : null
  const mixRealRv =
    totalUsd !== null && totalUsd > 0 && subtotalRvUsd !== null ? (subtotalRvUsd / totalUsd) * 100 : null

  const yaEnCartera = new Set(posicionesRv.map((p) => p.ticker))
  const listaPicker = (clasePicker === 'accion' ? acciones.data : cedears.data) ?? []
  const cargandoPicker = clasePicker === 'accion' ? acciones.isPending : cedears.isPending
  const erroresPicker = clasePicker === 'accion' ? acciones.isError : cedears.isError

  // Opciones del filtro: sólo las que de verdad aparecen en esta clase, ordenadas alfabéticamente
  // (orden de presentación — sector/rubro no tienen jerarquía propia que ordenar por otro criterio).
  const sectoresPicker = [
    ...new Set(listaPicker.map((e) => e.sector).filter((s): s is string => s !== null)),
  ].sort()
  const industriasPicker = [
    ...new Set(listaPicker.map((e) => e.industria).filter((i): i is string => i !== null)),
  ].sort()

  const busquedaNormalizada = busqueda.trim().toLowerCase()
  const filtradaPicker = listaPicker.filter((e) => {
    if (sectorFiltro !== null && e.sector !== sectorFiltro) return false
    if (industriaFiltro !== null && e.industria !== industriaFiltro) return false
    if (busquedaNormalizada === '') return true
    // Ticker o nombre (corto o largo, de Yahoo) — sin perfil todavía, sólo matchea por ticker.
    return (
      e.ticker.toLowerCase().includes(busquedaNormalizada) ||
      (e.nombre_corto?.toLowerCase().includes(busquedaNormalizada) ?? false) ||
      (e.nombre_largo?.toLowerCase().includes(busquedaNormalizada) ?? false)
    )
  })

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
        <Campo etiqueta="Σ pedido RV">{pos.length > 0 ? fmtPct(pesoRvPedido, 1) : SIN_DATO}</Campo>
        <Campo etiqueta="Mix pedido RF/RV">
          {pos.length > 0 ? `${fmtPct(pesoRfPedido, 1)} / ${fmtPct(pesoRvPedido, 1)}` : SIN_DATO}
        </Campo>
        <Campo etiqueta="Mix real RF/RV (sobre invertido)">
          {mixRealRf !== null && mixRealRv !== null ? `${fmtPct(mixRealRf, 1)} / ${fmtPct(mixRealRv, 1)}` : SIN_DATO}
        </Campo>
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
              posicion={posicion}
              especie={porTicker.get(posicion.ticker) ?? null}
              resuelta={resueltas.find((r) => r.ticker === posicion.ticker) ?? null}
              onAbrir={() => abrirInstrumento(posicion.ticker)}
              onQuitar={() => alternarRentaVariable(posicion.ticker)}
              onFijarPeso={(peso) => fijarPeso(posicion.ticker, peso)}
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
          placeholder="Buscar ticker o nombre…"
          aria-label="Buscar acción o CEDEAR por ticker o nombre"
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

      {/* Sector y rubro: del perfil de empresa (Etapa 5), vacíos hasta que el job de
          enriquecimiento pase por estos tickers. Sin especies con el dato todavía, los selects
          quedan con la única opción "todos" y no estorban. */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {/* "(empresa)" en la etiqueta visible, no sólo en el aria-label: el filtro de sector de la
            grilla de renta fija (más arriba en la misma página) ya se llama "Sector" a secas —
            dos selects con el mismo texto visible confundirían tanto a la vista como a un lector
            de pantalla. */}
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
          Sector (empresa)
          <select
            value={sectorFiltro ?? ''}
            onChange={(evento) => setSectorFiltro(evento.target.value === '' ? null : evento.target.value)}
            style={estiloSelectPicker}
          >
            <option value="">todos</option>
            {sectoresPicker.map((sector) => (
              <option key={sector} value={sector}>
                {sector}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11, color: 'var(--dim)' }}>
          Rubro (empresa)
          <select
            value={industriaFiltro ?? ''}
            onChange={(evento) => setIndustriaFiltro(evento.target.value === '' ? null : evento.target.value)}
            style={estiloSelectPicker}
          >
            <option value="">todos</option>
            {industriasPicker.map((industria) => (
              <option key={industria} value={industria}>
                {industria}
              </option>
            ))}
          </select>
        </label>
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
      {especie.nombre_corto && (
        <span
          style={{
            fontSize: 11,
            color: 'var(--dim)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
          title={especie.nombre_largo ?? especie.nombre_corto}
        >
          {especie.nombre_corto}
        </span>
      )}
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
  posicion,
  especie,
  resuelta,
  onAbrir,
  onQuitar,
  onFijarPeso,
}: {
  posicion: PosicionArmador
  especie: EspecieRentaVariable | null
  resuelta: PosicionRvResuelta | null
  onAbrir: () => void
  onQuitar: () => void
  onFijarPeso: (peso: number) => void
}) {
  const variacionPct = especie?.variacion == null ? null : especie.variacion * 100
  const colorVariacion =
    variacionPct === null ? 'var(--ac2)' : variacionPct > 0 ? 'var(--pos)' : variacionPct < 0 ? 'var(--neg)' : 'var(--tx)'
  const textoVariacion = variacionPct === null ? SIN_DATO : `${variacionPct > 0 ? '+' : ''}${fmtPct(variacionPct)}`
  const ticker = especie?.ticker ?? resuelta?.ticker ?? posicion.ticker

  const pesoReal = resuelta?.pesoReal ?? null
  const difiere = pesoReal !== null && Math.abs(pesoReal - posicion.peso) > TOLERANCIA_DIFERENCIA_FILA

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
        <span
          style={{
            fontSize: 10.5,
            color: 'var(--dim)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            minWidth: 0,
          }}
          title={
            especie?.nombre_corto
              ? `Empresa según Yahoo Finance · capturado ${fmtFecha(especie.perfil_capturado_en)}`
              : undefined
          }
        >
          {/* Con perfil de empresa (Etapa 5): nombre + clase. Sin él, sólo la clase — es lo único
              descriptivo que hay hasta que el job de enriquecimiento pase por este ticker. */}
          {especie?.nombre_corto
            ? `${especie.nombre_corto} · ${especie.clase_activo === 'accion' ? 'Acción' : 'CEDEAR'}`
            : especie
              ? especie.clase_activo === 'accion'
                ? 'Acción'
                : 'CEDEAR'
              : SIN_DATO}
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

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 6, marginTop: 8 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ fontSize: 9.5, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            % pedido
          </span>
          <input
            type="number"
            className="mono"
            value={posicion.peso}
            step={0.1}
            onChange={(evento) => onFijarPeso(Number(evento.target.value) || 0)}
            aria-label={`ponderación pedida de ${ticker}`}
            style={{
              width: '100%',
              textAlign: 'right',
              font: 'inherit',
              fontSize: 12,
              color: 'var(--ac)',
              background: 'var(--pan2)',
              border: '1px solid var(--lin)',
              borderRadius: 3,
              padding: '2px 4px',
            }}
          />
        </div>
        <Metrica etiqueta="% real" nota="Ponderación efectiva dentro del bloque de renta variable, sobre lo invertido.">
          <span style={{ color: difiere ? 'var(--ac2)' : 'var(--tx)' }}>
            {pesoReal !== null ? fmtPct(pesoReal) : SIN_DATO}
          </span>
        </Metrica>
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
