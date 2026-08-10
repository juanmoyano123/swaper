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
 * **El pipeline de resolución ya no vive acá**: se extrajo a `hooks/useCarteraResuelta` en la base
 * común de la Tanda 9, porque F-020 y F-021 necesitan los mismos números. Ahí también quedó
 * documentado el ajuste de casing de `moneda_cotizacion` y el filtro por clase que deja la renta
 * variable afuera del resolver de bonos.
 */

import { useState, type ReactNode } from 'react'

import { MiniCalendario, type CeldaMes } from '@/components/MiniCalendario'
import { fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import { AlertasCalendario } from './AlertasCalendario'
import { useCalendarioCartera } from '../hooks/useCalendarioCartera'
import { useCargarLamina } from '../hooks/useCargarLamina'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { mixPedido } from '../lib/mix'
import type { Especie } from '../lib/schema'
import { type PosicionResuelta, type ResumenAjuste } from '../lib/resolver'
import {
  posicionesRentaFija,
  useArmador,
  useArmadorAcciones,
  type PosicionArmador,
} from '../store/carteraStore'

/** Tolerancia de la cabecera: por debajo no vale la pena teñir el total en `--ac2`. */
const TOLERANCIA_SUMA_PESOS = 0.05
/** A partir de acá, la diferencia entre pedido y real se marca (design system, sección A8). */
const TOLERANCIA_DIFERENCIA_FILA = 0.6

export function CarteraEditable() {
  const { pos, montoTotal } = useArmador()
  const { fijarPeso, fijarMontoTotal, equiponderar, vaciar } = useArmadorAcciones()

  const {
    resueltas,
    ajuste,
    posicionesParaCalendario,
    porTicker,
    totalInvertidoUsd: sumaInvertidoUsd,
    hayAlgunaResuelta,
  } = useCarteraResuelta()

  const calendario = useCalendarioCartera(posicionesParaCalendario)

  // La tabla lista renta fija y FCI: la renta variable tiene su propio bloque con subtotal aparte
  // (F-026), y mezclarlas acá haría que una acción apareciera con columnas de VN y lámina.
  const posiciones = posicionesRentaFija(pos)
  // El 100% del que habla esta cabecera es el de la cartera ENTERA (`peso` se pide así, ver
  // `carteraStore.tsx`) — comparar sólo la suma de esta tabla contra 100 mentía apenas había
  // renta variable cargada: el ámbar se prendía o se apagaba sin que el pedido real cambiara.
  const mix = mixPedido(pos)
  const sumaPesoPedidoTotal = mix.rf + mix.rv

  function onVaciar() {
    if (pos.length > 0 && !window.confirm('¿Vaciar la cartera en construcción?')) return
    vaciar()
  }

  return (
    <div>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 14,
          marginBottom: 10,
        }}
      >
        <Campo etiqueta="Σ pedida total (incl. RV)">
          <span
            className="mono"
            style={{
              color: Math.abs(sumaPesoPedidoTotal - 100) > TOLERANCIA_SUMA_PESOS ? 'var(--ac2)' : 'var(--tx)',
            }}
          >
            {fmtPct(sumaPesoPedidoTotal)}
          </span>
          {mix.rv > 0 && (
            <span className="mono" style={{ marginLeft: 6, fontSize: 10.5, color: 'var(--dim)' }}>
              (RF {fmtPct(mix.rf, 1)} · RV {fmtPct(mix.rv, 1)})
            </span>
          )}
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
        {posiciones.length > 0 && (
          <span style={{ flexBasis: '100%', fontSize: 11, color: 'var(--dim)' }}>
            {leyendaAjuste(ajuste)}
          </span>
        )}
      </header>

      {posiciones.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Sin posiciones. Elegí papeles en la grilla de arriba para empezar a armar la cartera.
        </p>
      ) : (
        <div
          role="table"
          aria-label="Cartera en construcción"
          style={{ display: 'grid', gap: 4, overflowX: 'auto' }}
        >
          <EncabezadosDeColumna />
          {posiciones.map((posicion) => (
            <FilaCartera
              key={posicion.ticker}
              posicion={posicion}
              especie={porTicker.get(posicion.ticker) ?? null}
              resuelta={resueltas.find((r) => r.ticker === posicion.ticker) ?? null}
              meses={calendario.data?.meses ?? null}
              onFijarPeso={(peso) => fijarPeso(posicion.ticker, peso)}
            />
          ))}
          <LeyendaDeColumnas />
        </div>
      )}

      {calendario.data && <AlertasCalendario alertas={calendario.data.alertas} />}
    </div>
  )
}

/** Encabezados de columna del `GRID_FILA` — no existían antes del refinamiento visual, y sin ellos
 *  "% real" y el minicalendario no se entendían de un vistazo. */
function EncabezadosDeColumna() {
  const estiloCabecera = {
    fontSize: 9.5,
    color: 'var(--dim)',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.06em',
    minWidth: 0,
  }
  return (
    <div
      role="row"
      style={{
        display: 'grid',
        gridTemplateColumns: GRID_FILA,
        gap: 8,
        padding: '0 2px 4px',
        borderBottom: '1px solid var(--lin)',
      }}
    >
      <span role="columnheader" style={estiloCabecera}>
        Papel
      </span>
      <span role="columnheader" style={estiloCabecera}>
        Emisor · VN · invertido
      </span>
      <span role="columnheader" style={{ ...estiloCabecera, textAlign: 'right' }}>
        % pedido
      </span>
      <span
        role="columnheader"
        style={{ ...estiloCabecera, textAlign: 'right', cursor: 'help' }}
        title="Ponderación efectiva tras redondear a lámina, con precio y tipo de cambio del día. s/d: falta precio o tipo de cambio."
      >
        % real
      </span>
      <span
        role="columnheader"
        style={{ ...estiloCabecera, cursor: 'help' }}
        title="Meses de la ventana de 12 en que el papel paga renta."
      >
        Paga en
      </span>
      <span role="columnheader" aria-hidden style={estiloCabecera} />
    </div>
  )
}

/** Qué significa lo que la tabla acaba de mostrar — el "s/d" y el minicalendario no se explican
 *  solos (regla 11: lo que falta se declara, no se deja mudo). */
function LeyendaDeColumnas() {
  return (
    <p style={{ margin: '6px 0 0', fontSize: 10.5, color: 'var(--dim)', display: 'flex', flexWrap: 'wrap', gap: '4px 14px' }}>
      <span>
        <span className="mono" style={{ color: 'var(--sd)' }}>
          s/d
        </span>
        : sin precio o sin tipo de cambio — el dato falta, no es cero.
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <span style={{ display: 'inline-block', width: 7, height: 12, borderRadius: 2, background: 'var(--pos)' }} />
        mes en que el papel paga renta
      </span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <span
          style={{ display: 'inline-block', width: 7, height: 12, borderRadius: 2, border: '1px solid var(--lin)' }}
        />
        mes sin pago (dato, no ausencia)
      </span>
    </p>
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
  meses: { nombre: string; instrumentos: { ticker: string; pct_renta: number }[] }[] | null
  onFijarPeso: (peso: number) => void
}) {
  const { alternarPapel } = useArmadorAcciones()

  const mesesQuePaga: string[] = []
  const celdas: CeldaMes[] = Array.from({ length: 12 }, (_, indice) => {
    const mes = meses?.[indice]
    if (!mes) return null
    const paga = mes.instrumentos.find((i) => i.ticker === posicion.ticker)
    if (!paga || paga.pct_renta <= 0) return null
    mesesQuePaga.push(mes.nombre)
    return 'renta'
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
          {posicion.clase === 'fci' ? 'FCI' : (especie?.moneda_cotizacion ?? SIN_DATO)}
        </span>
      </div>

      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 11.5, color: 'var(--tx)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {posicion.clase === 'fci' ? posicion.ticker : (especie?.emisor ?? especie?.ticker ?? posicion.ticker)}
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
          {resuelta?.laminaConocida === false && posicion.clase !== 'fci' && (
            <>
              {' · '}
              <InputLamina ticker={posicion.ticker} />
            </>
          )}
          {posicion.clase !== 'fci' && (
            <>
              {' · calif. '}
              {especie?.calificacion ?? 'sin calif.'}
            </>
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
          color: pesoReal === null ? 'var(--sd)' : difiere ? 'var(--ac2)' : 'var(--tx)',
          borderBottom: pesoReal === null ? '1px dotted var(--sd)' : undefined,
          cursor: pesoReal === null ? 'help' : undefined,
        }}
      >
        {fmtPct(pesoReal)}
      </span>

      {meses === null ? (
        <span
          className="mono"
          title="calendario aún sin calcular"
          style={{ fontSize: 11, color: 'var(--sd)' }}
        >
          {SIN_DATO}
        </span>
      ) : (
        <MiniCalendario
          meses={celdas}
          etiqueta={
            mesesQuePaga.length > 0
              ? `${posicion.ticker}: paga en ${mesesQuePaga.join(', ')}`
              : `${posicion.ticker}: no paga en ningún mes de la ventana`
          }
        />
      )}

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

/** Carga asistida de lámina, in situ — F-025. Reemplaza el "lámina no informada" de la fila con un
 *  input chico: sin salir del armador, el asesor tipea el valor y la propagación por emisión la
 *  resuelve el backend. En éxito no hay estado que limpiar acá — `useCargarLamina` invalida el
 *  universo y la fila deja de pedir este componente sola, porque `laminaConocida` pasa a `true`. */
function InputLamina({ ticker }: { ticker: string }) {
  const [texto, setTexto] = useState('')
  const cargarLamina = useCargarLamina()
  const conflicto =
    cargarLamina.data && !cargarLamina.data.guardado ? cargarLamina.data.conflicto : null

  function confirmar() {
    const valor = Number(texto)
    if (!texto || !Number.isFinite(valor) || valor <= 0) return
    cargarLamina.mutate(
      { ticker, valor },
      { onSuccess: (resultado) => resultado.guardado && setTexto('') },
    )
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
      <input
        type="number"
        className="mono num-sin-flechas"
        value={texto}
        disabled={cargarLamina.isPending}
        placeholder="lámina"
        min={0}
        onChange={(evento) => setTexto(evento.target.value)}
        onKeyDown={(evento) => {
          if (evento.key === 'Enter') confirmar()
        }}
        aria-label={`cargar lámina de ${ticker}`}
        style={{
          width: 54,
          font: 'inherit',
          fontSize: 10,
          color: 'var(--tx)',
          background: 'var(--pan2)',
          border: '1px solid var(--lin)',
          borderRadius: 3,
          padding: '1px 3px',
        }}
      />
      <button
        type="button"
        onClick={confirmar}
        disabled={cargarLamina.isPending}
        aria-label={`confirmar lámina de ${ticker}`}
        style={{
          font: 'inherit',
          fontSize: 10,
          border: 'none',
          background: 'transparent',
          color: cargarLamina.isPending ? 'var(--sd)' : 'var(--dim)',
          cursor: cargarLamina.isPending ? 'default' : 'pointer',
          padding: 0,
        }}
      >
        ✓
      </button>
      {conflicto && (
        <span
          role="alert"
          style={{ color: 'var(--ac2)' }}
          title="el sistema no elige entre valores de distinto origen: reintentá con el valor correcto"
        >
          conflicto:{' '}
          {Object.entries(conflicto.valores)
            .map(([tkr, val]) => `${tkr}=${val}`)
            .join(' vs ')}
        </span>
      )}
    </span>
  )
}
