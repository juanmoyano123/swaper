/**
 * El contenido de la ficha, compartido por las dos formas en que se la puede ver: el drawer
 * superpuesto y la página completa. Lo que cambia entre una y otra es el contenedor, no el dato.
 *
 * F-039: tres queries independientes (`useFichaInstrumento`, `useCondicionesInstrumento`,
 * `useCronogramaInstrumento`), cada una con su propio loading/error — así una falla en el
 * cronograma no tumba la ficha de precios, que es justamente el punto de tenerlas separadas.
 */

import type { ReactNode } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { EstadoVacio } from '@/components/EstadoVacio'
import { Panel } from '@/components/Panel'
import { nombreSegmento, unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { ApiError } from '@/lib/api/errors'
import { fmtCompacto, fmtFecha, fmtMonto, fmtNumero, fmtPct, NO_APLICA, SIN_DATO } from '@/lib/fmt'

import { useCondicionesInstrumento } from './hooks/useCondicionesInstrumento'
import { useCronogramaInstrumento } from './hooks/useCronogramaInstrumento'
import { useFichaInstrumento } from './hooks/useFichaInstrumento'
import type { CondicionesDetalle, EspecieFicha } from './lib/schema'

/**
 * "no informado" es distinto de `SIN_DATO` ('s/d'): un campo de condiciones ausente no es un dato
 * que la fuente no trajo hoy, es un campo que nunca se curó — el matiz que pide GWT-2 (no vacío ni
 * inferido de la clase del emisor).
 */
const NO_INFORMADO = 'no informado'

const CLASES_RENTA_VARIABLE = new Set(['accion', 'cedear'])

export function FichaInstrumento({ ticker }: { ticker: string | undefined }) {
  const fichaQuery = useFichaInstrumento(ticker)
  const condicionesQuery = useCondicionesInstrumento(ticker)
  const cronogramaQuery = useCronogramaInstrumento(ticker)

  if (ticker === undefined) {
    return (
      <Panel rotulo="Ficha">
        <EstadoVacio
          titulo="No hay datos de este instrumento todavía."
          detalle="La ficha completa la construye F-039 y se alimenta del universo consolidado que puebla la ingesta."
        />
      </Panel>
    )
  }

  if (fichaQuery.isPending) {
    return (
      <Panel rotulo="Ficha">
        <EstadoCarga que={`la ficha de ${ticker}`} />
      </Panel>
    )
  }

  if (fichaQuery.isError) {
    const noEstaEnElUniverso =
      fichaQuery.error instanceof ApiError && fichaQuery.error.status === 404
    return (
      <Panel rotulo="Ficha">
        {noEstaEnElUniverso ? (
          <EstadoVacio
            titulo={`${ticker} no está en el universo de hoy.`}
            detalle="No aparece en la corrida más reciente: puede haber dejado de operarse o de listarse."
          />
        ) : (
          <EstadoError error={fichaQuery.error} onRetry={() => void fichaQuery.refetch()} />
        )}
      </Panel>
    )
  }

  const { especie, hermanas } = fichaQuery.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Panel rotulo="El mismo papel en las tres monedas">
        <BloqueMonedas ticker={ticker} especie={especie} hermanas={hermanas} />
      </Panel>

      <Panel rotulo="Ficha">
        <GrillaFicha especie={especie} />
      </Panel>

      <Panel rotulo="Condiciones de emisión">
        <BloqueCondiciones query={condicionesQuery} />
      </Panel>

      <Panel rotulo="Cronograma">
        <BloqueCronograma query={cronogramaQuery} />
      </Panel>
    </div>
  )
}

// --- "El mismo papel en las tres monedas" ---------------------------------------------------------

function BloqueMonedas({
  ticker,
  especie,
  hermanas,
}: {
  ticker: string
  especie: EspecieFicha
  hermanas: EspecieFicha[]
}) {
  const especies = [especie, ...hermanas]

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {especies.map((esp) => (
          <TarjetaEspecie key={esp.ticker} especie={esp} esPedida={esp.ticker === ticker} />
        ))}
      </div>
      <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 10, textWrap: 'pretty' }}>
        Tres tickers del mismo instrumento: no se suman ni se convierten entre sí.
      </p>
    </div>
  )
}

function TarjetaEspecie({ especie, esPedida }: { especie: EspecieFicha; esPedida: boolean }) {
  const monedaFmt = especie.moneda_cotizacion?.toLowerCase() === 'ars' ? 'ars' : 'usd'

  return (
    <div
      style={{
        flex: '1 1 130px',
        minWidth: 130,
        border: `1px solid ${esPedida ? 'var(--ac)' : 'var(--lin)'}`,
        borderRadius: 4,
        padding: '10px 12px',
      }}
    >
      <div className="mono" style={{ fontSize: 15, fontWeight: 600 }}>
        {especie.ticker}
      </div>
      <div className="mono" style={{ fontSize: 13, textAlign: 'right', marginTop: 4 }}>
        {fmtMonto(especie.precio, monedaFmt)}
      </div>
      <div style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 2 }}>
        {especie.moneda_cotizacion ?? SIN_DATO} · vol {fmtCompacto(especie.volumen)}
      </div>
      <div
        className="mono"
        title="las puntas no viajan por la fuente hoy"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
          marginTop: 6,
          color: 'var(--dim)',
        }}
      >
        <span>compra {SIN_DATO}</span>
        <span>venta {SIN_DATO}</span>
      </div>
    </div>
  )
}

// --- Ficha: grilla de dos columnas ------------------------------------------------------------------

function GrillaFicha({ especie }: { especie: EspecieFicha }) {
  const esRentaVariable = CLASES_RENTA_VARIABLE.has(especie.clase_activo)
  const unidad = unidadDeNaturaleza(especie.naturaleza)
  const rendimientoPct = especie.rendimiento === null ? null : especie.rendimiento * 100

  const campos: [string, ReactNode][] = [
    ['Segmento', nombreSegmento(especie.segmento)],
    [`Rendimiento (${unidad})`, esRentaVariable ? NO_APLICA : fmtPct(rendimientoPct)],
    ['Duración', esRentaVariable ? NO_APLICA : fmtNumero(especie.duracion, 2)],
    ['Paridad', fmtNumero(especie.paridad, 3)],
    ['Moneda de cotización', especie.moneda_cotizacion ?? SIN_DATO],
    ['Volumen', fmtCompacto(especie.volumen)],
    ['Ley', especie.ley ?? SIN_DATO],
    ['Vencimiento', fmtFecha(especie.vencimiento)],
  ]

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
      {campos.map(([etiqueta, valor]) => (
        <div key={etiqueta}>
          <div style={{ fontSize: 10.5, color: 'var(--dim)' }}>{etiqueta}</div>
          <div className="mono" style={{ fontSize: 13 }}>
            {valor}
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Condiciones de emisión --------------------------------------------------------------------------

type ClaveCondicion = 'ley' | 'moneda_pago' | 'lamina' | 'calificacion' | 'sector' | 'underlying'

const CAMPOS_CONDICIONES: { etiqueta: string; campo: ClaveCondicion }[] = [
  { etiqueta: 'Calificación', campo: 'calificacion' },
  { etiqueta: 'Sector', campo: 'sector' },
  { etiqueta: 'Lámina', campo: 'lamina' },
  { etiqueta: 'Moneda de pago', campo: 'moneda_pago' },
  { etiqueta: 'Ley', campo: 'ley' },
  { etiqueta: 'Emisor', campo: 'underlying' },
]

function BloqueCondiciones({
  query,
}: {
  query: ReturnType<typeof useCondicionesInstrumento>
}) {
  if (query.isPending) return <EstadoCarga que="las condiciones de emisión" />
  if (query.isError) {
    return <EstadoError error={query.error} onRetry={() => void query.refetch()} />
  }

  const detalle = query.data.condiciones

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      {CAMPOS_CONDICIONES.map(({ etiqueta, campo }) => {
        const { valor, origen, fecha } = campoDeCondicion(detalle, campo)
        const texto =
          valor === null
            ? NO_INFORMADO
            : typeof valor === 'number'
              ? fmtNumero(valor, 0)
              : String(valor)
        const explicacion = origen ? `${origen} · ${fmtFecha(fecha)}` : undefined

        return (
          <div
            key={campo}
            style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, gap: 10 }}
          >
            <span style={{ color: 'var(--dim)' }}>{etiqueta}</span>
            <span className="mono" title={explicacion}>
              {texto}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function campoDeCondicion(
  detalle: CondicionesDetalle | null,
  campo: ClaveCondicion,
): { valor: string | number | null; origen: string | null; fecha: string | null } {
  if (detalle === null) return { valor: null, origen: null, fecha: null }
  const origenClave = `${campo}_origen` as keyof CondicionesDetalle
  const fechaClave = `${campo}_fecha` as keyof CondicionesDetalle
  return {
    valor: detalle[campo],
    origen: detalle[origenClave] as string | null,
    fecha: detalle[fechaClave] as string | null,
  }
}

// --- Cronograma -----------------------------------------------------------------------------------

function BloqueCronograma({ query }: { query: ReturnType<typeof useCronogramaInstrumento> }) {
  if (query.isPending) return <EstadoCarga que="el cronograma de pagos" />
  if (query.isError) {
    return <EstadoError error={query.error} onRetry={() => void query.refetch()} />
  }

  const pagos = query.data.pagos
  if (pagos.length === 0) {
    return <EstadoVacio titulo="Sin cronograma cargado para esta emisión." />
  }

  const filas = pagos.flatMap((pago) => {
    const items: { fecha: string; tipo: string; monto: number }[] = []
    if (pago.interes > 0) items.push({ fecha: pago.fecha, tipo: 'renta', monto: pago.interes })
    if (pago.amortizacion > 0) {
      items.push({ fecha: pago.fecha, tipo: 'amortización', monto: pago.amortizacion })
    }
    return items
  })

  return (
    <div>
      <table className="mono" style={{ width: '100%', fontSize: 11.5, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--dim)', textAlign: 'left' }}>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px 0' }}>fecha</th>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px' }}>tipo</th>
            <th style={{ fontWeight: 400, padding: '2px 0 4px', textAlign: 'right' }}>
              monto / 100 VN
            </th>
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={`${fila.fecha}-${fila.tipo}-${indice}`} style={{ borderTop: '1px solid var(--lin)' }}>
              <td style={{ padding: '3px 6px 3px 0' }}>{fmtFecha(fila.fecha)}</td>
              <td style={{ padding: '3px 6px', textTransform: 'capitalize' }}>{fila.tipo}</td>
              <td style={{ padding: '3px 0', textAlign: 'right' }}>{fmtNumero(fila.monto, 4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 8, textWrap: 'pretty' }}>
        Montos por cada 100 de valor nominal; el flujo en plata del cliente depende del nominal que
        tenga asignado.
      </p>
    </div>
  )
}
