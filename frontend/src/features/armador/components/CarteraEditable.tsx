/**
 * El panel donde vive la cartera en construcción — diseño A8, F-018.
 *
 * Tabla editable: peso pedido, peso real, VN e invertido, calendario de pagos. La ponderación
 * pedida y la real **no se hacen coincidir en pantalla**: si no suman 100 o si la lámina obliga a
 * redondear, eso se muestra tal cual (reglas 1 y 3 del dominio).
 *
 * Precio, moneda y emisor salen de `/emisiones/especies` (F-038), pedido entero y sin filtro de
 * segmento — no hay un endpoint "dame estas N especies" y el número de posiciones de una cartera
 * es chico. La lámina real viaja desde ahí (F-024, de `condiciones_emision` vía la base común de
 * la tanda 8b): `null` es no informada, y la fila y la cabecera lo declaran en vez de asumir un
 * valor.
 *
 * **Desvío contra el plan**: `moneda_cotizacion` llega del backend en mayúsculas ("ARS"/"USD",
 * `BYMA` sin traducir — ver `backend/app/ingesta/byma/normalizacion.py`), mientras que
 * `EntradaResolver.monedaCotizacion` compara contra los literales en minúscula `'usd'/'ars'`
 * (así lo especifica el plan y así lo cubren los tests de `resolver.ts`, con fixtures en
 * minúscula). Comparar sin normalizar dejaría toda posición en ARS/USD reales sin resolver. Se
 * normaliza acá, en el borde donde `Especie` se convierte a `EntradaResolver` — es un ajuste de
 * casing, no una regla de negocio nueva.
 */

import { useMemo, type ReactNode } from 'react'

import { MiniCalendario, type CeldaMes } from '@/components/MiniCalendario'
import { fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import { AlertasCalendario } from './AlertasCalendario'
import { useCalendarioCartera } from '../hooks/useCalendarioCartera'
import { useEspeciesUniverso } from '../hooks/useEspeciesUniverso'
import { useTipoDeCambio } from '../hooks/useTipoDeCambio'
import type { Especie } from '../lib/schema'
import {
  resolver,
  resumenAjuste,
  type EntradaResolver,
  type PosicionResuelta,
  type ResumenAjuste,
} from '../lib/resolver'
import { useArmador, useArmadorAcciones, type PosicionArmador } from '../store/carteraStore'

/** Tolerancia de la cabecera: por debajo no vale la pena teñir el total en `--ac2`. */
const TOLERANCIA_SUMA_PESOS = 0.05
/** A partir de acá, la diferencia entre pedido y real se marca (design system, sección A8). */
const TOLERANCIA_DIFERENCIA_FILA = 0.6

export function CarteraEditable() {
  const { pos, montoTotal } = useArmador()
  const { fijarPeso, fijarMontoTotal, equiponderar, vaciar } = useArmadorAcciones()

  const especies = useEspeciesUniverso()
  const tipoDeCambio = useTipoDeCambio()

  const porTicker = useMemo(() => {
    const mapa = new Map<string, Especie>()
    for (const especie of especies.data ?? []) mapa.set(especie.ticker, especie)
    return mapa
  }, [especies.data])

  const tcValor = tipoDeCambio.data?.tipo_de_cambio.valor ?? null

  const resueltas = useMemo(() => {
    const entradas: EntradaResolver[] = pos.map((p) => {
      const especie = porTicker.get(p.ticker)
      // Normalizado a minúscula acá — ver nota del módulo sobre el casing real de BYMA.
      const monedaCotizacion = especie?.moneda_cotizacion?.toLowerCase() ?? null
      // Sin moneda declarada no hay con qué decidir si conviene TC: se declara sin precio en vez
      // de asumir una moneda (regla 1 del proyecto), aunque la especie sí traiga un precio.
      const sinBase = p.esFci || monedaCotizacion === null
      return {
        ticker: p.ticker,
        peso: p.peso,
        precio: sinBase ? null : (especie?.precio ?? null),
        monedaCotizacion: monedaCotizacion ?? 'usd', // irrelevante: `resolver` no la usa con precio null
        // F-024: la lámina real, de condiciones_emision vía /especies. `null` = no informada: el
        // resolver no redondea y la fila lo declara. Jamás un default (regla 1 del proyecto).
        lamina: p.esFci ? null : (especie?.lamina ?? null),
        esFci: p.esFci,
      }
    })
    return resolver(entradas, montoTotal, tcValor)
  }, [pos, porTicker, montoTotal, tcValor])

  const ajuste = useMemo(() => resumenAjuste(resueltas), [resueltas])

  const posicionesParaCalendario = useMemo(
    () =>
      resueltas
        .filter(
          (r): r is PosicionResuelta & { invertido: number } => r.invertido !== null && r.invertido > 0,
        )
        .map((r) => ({ ticker: r.ticker, monto: r.invertido })),
    [resueltas],
  )
  const calendario = useCalendarioCartera(posicionesParaCalendario)

  const sumaPesoPedido = pos.reduce((acumulado, p) => acumulado + p.peso, 0)
  const sumaInvertidoUsd = resueltas.reduce((acumulado, r) => acumulado + (r.invertidoUsd ?? 0), 0)
  const hayAlgunaResuelta = resueltas.some((r) => r.invertidoUsd !== null)

  function onVaciar() {
    if (pos.length > 0 && !window.confirm('¿Vaciar la cartera en construcción?')) return
    vaciar()
  }

  return (
    <div style={{ marginTop: 16 }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 14,
          marginBottom: 10,
        }}
      >
        <Campo etiqueta="Σ ponderación pedida">
          <span
            className="mono"
            style={{
              color: Math.abs(sumaPesoPedido - 100) > TOLERANCIA_SUMA_PESOS ? 'var(--ac2)' : 'var(--tx)',
            }}
          >
            {fmtPct(sumaPesoPedido)}
          </span>
        </Campo>
        <Campo etiqueta="Invertido">
          <span className="mono" style={{ color: 'var(--tx)' }}>
            {hayAlgunaResuelta ? fmtMonto(sumaInvertidoUsd, 'usd') : SIN_DATO}
          </span>
        </Campo>
        <Campo etiqueta="Invertido ajustado">
          <span className="mono" style={{ color: 'var(--tx)' }}>
            {ajuste.totalAjustadoUsd !== null ? fmtMonto(ajuste.totalAjustadoUsd, 'usd') : SIN_DATO}
          </span>
        </Campo>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)' }}>
          Monto total (USD)
          <input
            type="number"
            className="mono"
            value={montoTotal === 0 ? '' : montoTotal}
            placeholder="0"
            min={0}
            onChange={(evento) => fijarMontoTotal(Number(evento.target.value) || 0)}
            style={{
              width: 94,
              textAlign: 'right',
              font: 'inherit',
              fontSize: 12,
              color: 'var(--tx)',
              background: 'var(--pan2)',
              border: '1px solid var(--lin)',
              borderRadius: 3,
              padding: '3px 6px',
            }}
          />
        </label>
        <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
          <BotonAccion onClick={equiponderar} disabled={pos.length === 0}>
            Equiponderar
          </BotonAccion>
          <BotonAccion onClick={onVaciar} disabled={pos.length === 0}>
            Vaciar
          </BotonAccion>
        </div>
        {pos.length > 0 && (
          <span style={{ flexBasis: '100%', fontSize: 11, color: 'var(--dim)' }}>
            {leyendaAjuste(ajuste)}
          </span>
        )}
      </header>

      {pos.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Sin posiciones. Elegí papeles en la grilla de arriba para empezar a armar la cartera.
        </p>
      ) : (
        <div role="table" aria-label="Cartera en construcción" style={{ display: 'grid', gap: 4 }}>
          {pos.map((posicion) => (
            <FilaCartera
              key={posicion.ticker}
              posicion={posicion}
              especie={porTicker.get(posicion.ticker) ?? null}
              resuelta={resueltas.find((r) => r.ticker === posicion.ticker) ?? null}
              meses={calendario.data?.meses ?? null}
              onFijarPeso={(peso) => fijarPeso(posicion.ticker, peso)}
            />
          ))}
        </div>
      )}

      {calendario.data && <AlertasCalendario alertas={calendario.data.alertas} />}
    </div>
  )
}

/** El texto de la leyenda de cobertura de la cabecera — F-024. Un cero se explica, no se acepta:
 *  cero sin lámina es cobertura total declarada, no la ausencia de la leyenda. */
function leyendaAjuste(ajuste: ResumenAjuste): string {
  if (ajuste.sinLamina > 0) {
    const cierre =
      ajuste.pctSinAjustar === null
        ? 'porcentaje sin calcular: posiciones sin resolver'
        : `${fmtPct(ajuste.pctSinAjustar)} de la cartera fuera del total ajustado`
    return `${ajuste.sinLamina} de ${ajuste.ajustables} posiciones sin lámina informada — ${cierre}`
  }
  if (ajuste.ajustables > 0) return 'todas las posiciones con lámina informada: el total ajustado cubre la cartera'
  return 'sólo FCI en la cartera: no hay nominales que redondear'
}

function Campo({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
      <span style={{ fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </span>
      <span style={{ fontSize: 14 }}>{children}</span>
    </div>
  )
}

function BotonAccion({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        font: 'inherit',
        fontSize: 11.5,
        padding: '5px 10px',
        borderRadius: 3,
        border: '1px solid var(--lin)',
        background: 'transparent',
        color: disabled ? 'var(--sd)' : 'var(--tx)',
        cursor: disabled ? 'default' : 'pointer',
      }}
    >
      {children}
    </button>
  )
}

// Columnas, en orden: ticker+moneda · emisor+VN/invertido/lámina · peso pedido · peso real ·
// minicalendario · quitar.
// F-020 (tanda 9): para agregar columnas, extender GRID_FILA y FilaCartera acá — no crear otra fila.
const GRID_FILA = 'minmax(70px,86px) 1fr 52px 62px 52px 22px'

function FilaCartera({
  posicion,
  especie,
  resuelta,
  meses,
  onFijarPeso,
}: {
  posicion: PosicionArmador
  especie: Especie | null
  resuelta: PosicionResuelta | null
  meses: { instrumentos: { ticker: string; pct_renta: number }[] }[] | null
  onFijarPeso: (peso: number) => void
}) {
  const { alternarPapel } = useArmadorAcciones()

  const celdas: CeldaMes[] = Array.from({ length: 12 }, (_, indice) => {
    const mes = meses?.[indice]
    if (!mes) return null
    const paga = mes.instrumentos.find((i) => i.ticker === posicion.ticker)
    return paga && paga.pct_renta > 0 ? 'renta' : null
  })

  const pesoReal = resuelta?.pesoReal ?? null
  const difiere = pesoReal !== null && Math.abs(pesoReal - posicion.peso) > TOLERANCIA_DIFERENCIA_FILA
  const motivoDiferencia = resuelta?.laminaConocida ? 'redondeado a lámina conocida' : 'lámina no informada'

  return (
    <div
      role="row"
      aria-label={posicion.ticker}
      style={{
        display: 'grid',
        gridTemplateColumns: GRID_FILA,
        alignItems: 'center',
        gap: 8,
        padding: '4px 2px',
        borderBottom: '1px solid var(--lin)',
      }}
    >
      <div>
        <span className="mono" style={{ fontSize: 12.5, color: 'var(--tx)' }}>
          {posicion.ticker}
        </span>
        <span style={{ display: 'block', fontSize: 9.5, color: 'var(--dim)' }}>
          {posicion.esFci ? 'FCI' : (especie?.moneda_cotizacion ?? SIN_DATO)}
        </span>
      </div>

      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 11.5, color: 'var(--tx)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {posicion.esFci ? posicion.ticker : (especie?.emisor ?? especie?.ticker ?? posicion.ticker)}
        </div>
        <div className="mono" style={{ fontSize: 10, color: 'var(--sd)' }}>
          VN {resuelta?.vn !== null && resuelta?.vn !== undefined ? fmtNumero(resuelta.vn, 0) : SIN_DATO}
          {' · '}
          {resuelta?.invertido !== null && resuelta?.invertido !== undefined
            ? fmtMonto(resuelta.invertido, especie?.moneda_cotizacion === 'ARS' ? 'ars' : 'usd')
            : SIN_DATO}
          {resuelta?.laminaConocida === true && especie?.lamina != null && (
            <> · lám. {fmtNumero(especie.lamina, 0)}</>
          )}
          {resuelta?.laminaConocida === false && !posicion.esFci && (
            <span style={{ color: 'var(--ac2)' }}> · lámina no informada</span>
          )}
        </div>
      </div>

      <input
        type="number"
        className="mono"
        value={posicion.peso}
        step={0.1}
        onChange={(evento) => onFijarPeso(Number(evento.target.value) || 0)}
        aria-label={`ponderación pedida de ${posicion.ticker}`}
        style={{
          width: '100%',
          textAlign: 'right',
          font: 'inherit',
          fontSize: 12,
          color: 'var(--ac)',
          background: 'var(--pan2)',
          border: '1px solid var(--lin)',
          borderRadius: 3,
          padding: '3px 4px',
        }}
      />

      <span
        className="mono"
        title={pesoReal === null ? 'sin precio o sin tipo de cambio' : motivoDiferencia}
        style={{
          fontSize: 12,
          textAlign: 'right',
          color: difiere ? 'var(--ac2)' : 'var(--tx)',
        }}
      >
        {fmtPct(pesoReal)}
      </span>

      <MiniCalendario meses={celdas} etiqueta={`${posicion.ticker}: meses en que paga`} />

      <button
        type="button"
        onClick={() => alternarPapel(posicion.ticker)}
        aria-label={`sacar ${posicion.ticker} de la cartera`}
        style={{
          font: 'inherit',
          fontSize: 13,
          border: 'none',
          background: 'transparent',
          color: 'var(--dim)',
          cursor: 'pointer',
        }}
      >
        ×
      </button>
    </div>
  )
}
