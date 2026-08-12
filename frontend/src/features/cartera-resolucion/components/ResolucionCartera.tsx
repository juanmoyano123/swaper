/**
 * Qué resolvió la cartera cargada y qué no — F-029 en pantalla.
 *
 * Muestra tres cosas y ninguna más: qué instrumento es cada ticker declarado, cuáles no se
 * reconocieron, y qué porcentaje del monto representan esos que no.
 *
 * **Lo no reconocido se muestra, no se esconde.** Una posición que no resolvió ocupa su fila con su
 * monto y su motivo, en el mismo lugar que las demás. Filtrarlas a un panel aparte —o peor, no
 * mostrarlas— haría que la cartera se vea más completa de lo que es, que es exactamente lo que el
 * diagnóstico de cobertura existe para impedir.
 *
 * **Lo que acá NO va, y va en F-030** (`Valuación y diagnóstico de la cartera cargada`): el precio
 * de cada posición y el valor de la cartera, la renta mes a mes contra el calendario, los
 * rendimientos abiertos por naturaleza de tasa, el plazo promedio y la concentración por emisor y
 * por sector. Todo eso consume `Resolucion.posiciones`, que es lo que esta pantalla ya tiene.
 */

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { fmtNumero, fmtPct } from '@/lib/fmt'

import type { PosicionCruda } from '@/features/cartera-ingreso/types'

import { useResolucionCartera } from '../hooks/useResolucionCartera'
import type { AlertaResolucion, Cobertura, PosicionResuelta } from '../lib/schema'

const filaBase = {
  display: 'flex',
  alignItems: 'center',
  gap: 10,
  padding: '5px 8px',
  borderRadius: 3,
  background: 'var(--pan2)',
} as const

const listaBase = { listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 4 } as const

export function ResolucionCartera({ posiciones }: { posiciones: PosicionCruda[] }) {
  const consulta = useResolucionCartera(posiciones)

  // Sin posiciones no hay consulta —el hook la deja deshabilitada— y por lo tanto tampoco hay
  // "cargando": mostrar el estado de carga de algo que nunca se pidió sería una espera eterna.
  if (posiciones.length === 0) return null

  if (consulta.isPending) {
    return (
      <>
        <EstadoCarga que="la resolución contra el universo" />
        <ListaDeclarada posiciones={posiciones} />
      </>
    )
  }

  if (consulta.isError) {
    return (
      <>
        <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
        <div style={{ marginTop: 12 }}>
          <ListaDeclarada posiciones={posiciones} />
        </div>
      </>
    )
  }

  const { cobertura, alertas, posiciones: resueltas } = consulta.data

  return (
    <div>
      <ResumenCobertura cobertura={cobertura} />

      <ul style={listaBase}>
        {resueltas.map((p) => (
          <FilaResuelta key={p.id} posicion={p} />
        ))}
      </ul>

      {alertas.length > 0 && (
        <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
          {alertas.map((a) => (
            <AlertaEnPantalla key={a.codigo} alerta={a} />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * Cuántas resolvieron y cuánto pesa lo que no, **con la base del porcentaje al lado**.
 *
 * El porcentaje nunca se muestra solo: un número sin decir sobre cuántas posiciones se calculó se
 * lee como si fuera de toda la cartera. Y cuando no hay base se muestra `s/d` y no `0,0%` — no
 * poder calcularlo es un estado distinto de que dé cero.
 */
function ResumenCobertura({ cobertura }: { cobertura: Cobertura }) {
  const hayFueraDeLaBase = cobertura.posiciones_sin_monto > 0

  return (
    <div style={{ margin: '0 0 10px' }}>
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--dim)' }}>
        <span style={{ color: 'var(--tx)' }}>
          {cobertura.resueltas} de {cobertura.posiciones}
        </span>{' '}
        {cobertura.posiciones === 1 ? 'posición resuelta' : 'posiciones resueltas'} contra el
        universo
        {cobertura.no_resueltas > 0 && (
          <>
            {' · '}
            <span style={{ color: 'var(--neg)' }}>
              {cobertura.no_resueltas} sin resolver, {fmtPct(cobertura.porcentaje_no_resuelto, 1)}{' '}
              del monto
            </span>
          </>
        )}
      </p>

      {hayFueraDeLaBase && (
        <p style={{ margin: '4px 0 0', fontSize: 11.5, color: 'var(--ac2)' }}>
          El porcentaje se calculó sobre {cobertura.posiciones_con_monto} de{' '}
          {cobertura.posiciones} posiciones: las otras {cobertura.posiciones_sin_monto} no declaran
          monto y no se las cuenta como cero.
        </p>
      )}

      {/* El monto viaja sin moneda: F-028 lee el número que el resumen de cuenta escribió y el
          resumen no declara la moneda columna por columna. Se muestra sin símbolo a propósito —
          ponerle "US$" sería declarar una moneda que nadie declaró. La valuación con moneda por
          especie es F-030. */}
      <p className="mono" style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--sd)' }}>
        monto declarado {fmtNumero(cobertura.monto_declarado)} · sin resolver{' '}
        {fmtNumero(cobertura.monto_no_resuelto)} (en la moneda en que vino el resumen, que no se
        declara)
      </p>
    </div>
  )
}

function FilaResuelta({ posicion }: { posicion: PosicionResuelta }) {
  return (
    <li style={filaBase}>
      <span className="mono" style={{ fontSize: 12, minWidth: 90 }}>
        {posicion.ticker_declarado.trim() || '(sin ticker)'}
      </span>

      <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)', flex: 1 }}>
        {posicion.resuelta ? <DatosResueltos posicion={posicion} /> : <NoReconocida posicion={posicion} />}
      </span>

      <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)' }}>
        <Tenencia nominal={posicion.nominal} monto={posicion.monto} />
      </span>
    </li>
  )
}

/**
 * La emisión, la especie y el plazo de liquidación de una posición resuelta.
 *
 * El plazo se muestra con el código de BYMA sin traducir (`plazo 2`). Ninguna fuente del proyecto
 * publica qué plazo es cada código, así que escribir "48hs" sería inventar la equivalencia; cuando
 * el dato no está se muestra `s/d` y el backend lo alerta.
 */
function DatosResueltos({ posicion }: { posicion: PosicionResuelta }) {
  return (
    <>
      <span style={{ color: 'var(--tx)' }}>{posicion.ticker}</span>
      {posicion.emision && posicion.emision !== posicion.ticker && (
        <> · emisión {posicion.emision}</>
      )}
      {' · plazo '}
      {posicion.plazo_liquidacion ?? 's/d'}
      {posicion.dato_sano === false && (
        <span style={{ color: 'var(--ac2)' }}> · dato de mercado descartado</span>
      )}
    </>
  )
}

/** No se reconoció: se dice por qué y **no se propone ningún reemplazo**. */
function NoReconocida({ posicion }: { posicion: PosicionResuelta }) {
  return (
    <span style={{ color: 'var(--neg)' }}>
      no reconocida{posicion.motivo_descripcion ? ` · ${posicion.motivo_descripcion}` : ''}
    </span>
  )
}

function Tenencia({ nominal, monto }: { nominal: number | null; monto: number | null }) {
  return (
    <>
      {nominal !== null && `nominal ${fmtNumero(nominal)}`}
      {nominal !== null && monto !== null && ' · '}
      {monto !== null && `monto ${fmtNumero(monto)}`}
      {nominal === null && monto === null && 'sin nominal ni monto'}
    </>
  )
}

/** Mientras la resolución está en vuelo o falló, la cartera declarada se sigue viendo entera. */
function ListaDeclarada({ posiciones }: { posiciones: PosicionCruda[] }) {
  return (
    <ul style={listaBase}>
      {posiciones.map((p) => (
        <li key={p.id} style={filaBase}>
          <span className="mono" style={{ fontSize: 12, minWidth: 90 }}>
            {p.tickerDeclarado || '(sin ticker)'}
          </span>
          <span className="mono" style={{ fontSize: 11.5, color: 'var(--dim)', flex: 1 }}>
            <Tenencia nominal={p.nominal} monto={p.monto} />
          </span>
          {!p.valida && <span style={{ fontSize: 11, color: 'var(--neg)' }}>{p.motivo}</span>}
        </li>
      ))}
    </ul>
  )
}

/**
 * Una alerta del backend, con su acción requerida.
 *
 * El mensaje se muestra tal como lo mandó el backend y no se reescribe acá: la alerta ya está
 * redactada para que se sepa qué hacer, y una segunda redacción en la pantalla haría que el mismo
 * hecho se cuente de dos formas distintas según por dónde se lo mire.
 */
function AlertaEnPantalla({ alerta }: { alerta: AlertaResolucion }) {
  const color = alerta.severidad === 'error' ? 'var(--neg)' : 'var(--ac2)'

  return (
    <div
      role="alert"
      style={{
        border: '1px solid var(--lin)',
        borderLeft: `3px solid ${color}`,
        borderRadius: 3,
        background: 'var(--pan)',
        padding: '8px 10px',
        maxWidth: '72ch',
      }}
    >
      <p style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
        {alerta.mensaje}
      </p>
      {alerta.accion_requerida && (
        <p style={{ margin: '5px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>
          {alerta.accion_requerida}
        </p>
      )}
    </div>
  )
}
