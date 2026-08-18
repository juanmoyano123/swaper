/**
 * El contenido de la ficha, compartido por las dos formas en que se la puede ver: el drawer
 * superpuesto y la página completa. Lo que cambia entre una y otra es el contenedor, no el dato.
 *
 * F-039: tres queries independientes (`useFichaInstrumento`, `useCondicionesInstrumento`,
 * `useCronogramaInstrumento`), cada una con su propio loading/error — así una falla en el
 * cronograma no tumba la ficha de precios, que es justamente el punto de tenerlas separadas.
 */

import { useState, type ReactNode } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { EstadoVacio } from '@/components/EstadoVacio'
import { Panel } from '@/components/Panel'
import { nombreSegmento, unidadDeNaturaleza } from '@/components/SelectorSegmento'
import { apiFetchBlob } from '@/lib/api/client'
import { ApiError } from '@/lib/api/errors'
import { etiquetaClase } from '@/lib/claseActivo'
import { fmtCompacto, fmtFecha, fmtMonto, fmtNumero, fmtPct, NO_APLICA, SIN_DATO } from '@/lib/fmt'
import { colorDeParidad } from '@/lib/paridad'

import { useCondicionesInstrumento } from './hooks/useCondicionesInstrumento'
import { useCronogramaInstrumento } from './hooks/useCronogramaInstrumento'
import { useFichaInstrumento } from './hooks/useFichaInstrumento'
import { useProspectoInstrumento } from './hooks/useProspectoInstrumento'
import { useSensibilidadInstrumento } from './hooks/useSensibilidadInstrumento'
import type { CondicionesDetalle, EspecieFicha, ResumenCronograma } from './lib/schema'

/**
 * "no informado" es distinto de `SIN_DATO` ('s/d'): un campo de condiciones ausente no es un dato
 * que la fuente no trajo hoy, es un campo que nunca se curó — el matiz que pide GWT-2 (no vacío ni
 * inferido de la clase del emisor).
 */
const NO_INFORMADO = 'no informado'

const CLASES_RENTA_VARIABLE = new Set(['accion', 'cedear'])

/** F-072: el bloque de prospecto sólo tiene sentido para una obligación negociable. */
const CLASE_ON = 'on_corporativo'

/**
 * Experimento data912: el primer término de `fuente` ("data912-arrastre+calculo" → "arrastre") es
 * de dónde salió el precio. Se traduce a texto humano acá porque el rótulo interno compone origen
 * y cálculo con `+`, que no es lo que el asesor necesita leer — sólo el origen del precio.
 */
function textoFuente(fuente: string | null): string {
  if (fuente === null) return SIN_DATO
  const origen = fuente.split('+')[0]
  if (origen === 'data912-arrastre') return 'precio arrastrado de sesión anterior (data912)'
  if (origen === 'data912') return 'data912'
  if (origen === 'byma') return 'BYMA'
  return origen
}

export function FichaInstrumento({ ticker }: { ticker: string | undefined }) {
  const fichaQuery = useFichaInstrumento(ticker)
  const condicionesQuery = useCondicionesInstrumento(ticker)
  const cronogramaQuery = useCronogramaInstrumento(ticker)
  const sensibilidadQuery = useSensibilidadInstrumento(ticker)
  const prospectoQuery = useProspectoInstrumento(ticker)

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

      <Panel rotulo="Sensibilidad">
        <BloqueSensibilidad query={sensibilidadQuery} />
      </Panel>

      {especie.clase_activo === CLASE_ON && (
        <Panel rotulo="Prospecto de emisión">
          <BloqueProspecto query={prospectoQuery} />
        </Panel>
      )}
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
    ['Tipo', etiquetaClase(especie.clase_activo)],
    ['Segmento', nombreSegmento(especie.segmento)],
    [`Rendimiento (${unidad})`, esRentaVariable ? NO_APLICA : fmtPct(rendimientoPct)],
    ['Duración', esRentaVariable ? NO_APLICA : fmtNumero(especie.duracion, 2)],
    ['Paridad', fmtNumero(especie.paridad, 3)],
    ['Moneda de cotización', especie.moneda_cotizacion ?? SIN_DATO],
    ['Volumen', fmtCompacto(especie.volumen)],
    ['Ley', especie.ley ?? SIN_DATO],
    ['Vencimiento', fmtFecha(especie.vencimiento)],
    ['Fuente del precio', textoFuente(especie.fuente)],
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
    const items: { fecha: string; tipo: string; monto: number; residual: number | null }[] = []
    if (pago.interes > 0) {
      items.push({ fecha: pago.fecha, tipo: 'renta', monto: pago.interes, residual: pago.residual })
    }
    if (pago.amortizacion > 0) {
      items.push({
        fecha: pago.fecha,
        tipo: 'amortización',
        monto: pago.amortizacion,
        residual: pago.residual,
      })
    }
    return items
  })

  return (
    <div>
      <LecturaValorTecnico resumen={query.data.resumen} />
      <table className="mono" style={{ width: '100%', fontSize: 11.5, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--dim)', textAlign: 'left' }}>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px 0' }}>fecha</th>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px' }}>tipo</th>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px', textAlign: 'right' }}>
              monto / 100 VN
            </th>
            <th style={{ fontWeight: 400, padding: '2px 0 4px', textAlign: 'right' }}>residual</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((fila, indice) => (
            <tr key={`${fila.fecha}-${fila.tipo}-${indice}`} style={{ borderTop: '1px solid var(--lin)' }}>
              <td style={{ padding: '3px 6px 3px 0' }}>{fmtFecha(fila.fecha)}</td>
              <td style={{ padding: '3px 6px', textTransform: 'capitalize' }}>{fila.tipo}</td>
              <td style={{ padding: '3px 6px', textAlign: 'right' }}>{fmtNumero(fila.monto, 4)}</td>
              <td style={{ padding: '3px 0', textAlign: 'right' }}>{fmtNumero(fila.residual, 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 8, textWrap: 'pretty' }}>
        Montos y residual por cada 100 de valor nominal; el flujo en plata del cliente depende del
        nominal que tenga asignado.
      </p>
    </div>
  )
}

/**
 * Residual vigente, valor técnico y paridad, todos abiertos — nunca una etiqueta ("caro"/"barato").
 * El color del porcentaje es el mismo criterio del monitor (`lib/paridad.ts`): un dato duro hecho
 * legible de un vistazo, no un juicio sobre el papel.
 */
function LecturaValorTecnico({ resumen }: { resumen: ResumenCronograma }) {
  if (resumen.residual_vigente === null) {
    return (
      <p style={{ fontSize: 11.5, color: 'var(--dim)', marginBottom: 10 }}>
        Valor técnico: {SIN_DATO}
        {resumen.motivo_ausente && ` — ${resumen.motivo_ausente}.`}
      </p>
    )
  }

  return (
    <p className="mono" style={{ fontSize: 11.5, marginBottom: 10 }}>
      <span style={{ color: 'var(--dim)' }}>Residual vigente:</span>{' '}
      {fmtNumero(resumen.residual_vigente, 1)} de 100
      {' · '}
      <span style={{ color: 'var(--dim)' }}>Valor técnico:</span>{' '}
      {fmtNumero(resumen.valor_tecnico, 2)}
      {resumen.paridad !== null ? (
        <>
          {' · '}
          <span style={{ color: 'var(--dim)' }}>cotiza al</span>{' '}
          <span style={{ color: colorDeParidad(resumen.paridad) }}>
            {fmtPct(resumen.paridad * 100)}
          </span>{' '}
          <span style={{ color: 'var(--dim)' }}>del técnico</span>
        </>
      ) : (
        resumen.motivo_ausente && (
          <span style={{ color: 'var(--dim)' }}> · sin paridad: {resumen.motivo_ausente}</span>
        )
      )}
    </p>
  )
}

// --- Sensibilidad -----------------------------------------------------------------------------

function fmtDeltaBps(delta: number): string {
  if (delta === 0) return '0 bps'
  const signo = delta > 0 ? '+' : '−'
  return `${signo}${Math.abs(delta)} bps`
}

function BloqueSensibilidad({ query }: { query: ReturnType<typeof useSensibilidadInstrumento> }) {
  if (query.isPending) return <EstadoCarga que="la sensibilidad del precio" />
  if (query.isError) {
    return <EstadoError error={query.error} onRetry={() => void query.refetch()} />
  }

  const data = query.data
  if (!data.calculable) {
    return (
      <EstadoVacio titulo="No se puede calcular la sensibilidad." detalle={data.motivo ?? undefined} />
    )
  }

  const unidad = unidadDeNaturaleza(data.naturaleza ?? '')

  return (
    <div>
      <table className="mono" style={{ width: '100%', fontSize: 11.5, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: 'var(--dim)', textAlign: 'left' }}>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px 0' }}>movimiento</th>
            <th style={{ fontWeight: 400, padding: '2px 6px 4px', textAlign: 'right' }}>
              TIR escenario ({unidad})
            </th>
            <th style={{ fontWeight: 400, padding: '2px 0 4px', textAlign: 'right' }}>
              retorno del precio
            </th>
          </tr>
        </thead>
        <tbody>
          {data.escenarios.map((esc) => (
            <tr key={esc.delta_bps} style={{ borderTop: '1px solid var(--lin)' }}>
              <td style={{ padding: '3px 6px 3px 0' }}>{fmtDeltaBps(esc.delta_bps)}</td>
              <td style={{ padding: '3px 6px', textAlign: 'right' }}>
                {fmtPct(esc.tir_escenario * 100)}
              </td>
              <td style={{ padding: '3px 0', textAlign: 'right' }}>{fmtPct(esc.retorno * 100)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 8, textWrap: 'pretty' }}>
        Repricing completo del cashflow contractual a la TIR de cada escenario — no es la
        aproximación lineal por duración.
      </p>
      {data.omitidos_bps.length > 0 && (
        <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 4, textWrap: 'pretty' }}>
          {data.omitidos_bps.length} escenarios omitidos: la TIR resultante quedaría en −99 % o
          menos y el descuento degenera.
        </p>
      )}
    </div>
  )
}

// --- Prospecto de emisión (F-072) --------------------------------------------------------------

/** Igual patrón que `features/carteras/lib/exportar/descargar.ts` (F-042): `createObjectURL` + un
 *  `<a download>` sintético, sin dependencias nuevas. Duplicado acá porque esa carpeta es de otra
 *  feature — mismo criterio de aislamiento que ya aplica `features/monitor/` para ésta. */
function descargarBlob(blob: Blob, nombreArchivo: string): void {
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombreArchivo
  document.body.appendChild(enlace)
  enlace.click()
  document.body.removeChild(enlace)
  URL.revokeObjectURL(url)
}

function BloqueProspecto({ query }: { query: ReturnType<typeof useProspectoInstrumento> }) {
  const [descargando, setDescargando] = useState<string | null>(null)
  const [errorDescarga, setErrorDescarga] = useState<string | null>(null)

  if (query.isPending) return <EstadoCarga que="el prospecto de emisión" />
  if (query.isError) {
    return <EstadoError error={query.error} onRetry={() => void query.refetch()} />
  }

  const data = query.data

  async function descargar(ticker: string, uuid: string, nombreFallback: string) {
    setErrorDescarga(null)
    setDescargando(uuid)
    try {
      const { blob, nombreArchivo } = await apiFetchBlob(
        `/api/v1/instrumentos/${ticker}/prospecto/${uuid}/archivo`,
      )
      descargarBlob(blob, nombreArchivo ?? `${nombreFallback}.pdf`)
    } catch {
      setErrorDescarga('No se pudo descargar el PDF. Probá el link a la CNV.')
    } finally {
      setDescargando(null)
    }
  }

  return (
    <div>
      {data.grupos.length === 0 ? (
        <EstadoVacio
          titulo="Sin documentos para mostrar."
          detalle={data.motivo_ausente ?? undefined}
        />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {data.grupos.map((grupo) => (
            <div key={grupo.grupo}>
              <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 6 }}>{grupo.grupo}</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {grupo.documentos.map((doc) => (
                  <div
                    key={doc.uuid}
                    style={{
                      display: 'flex',
                      alignItems: 'baseline',
                      gap: 8,
                      fontSize: 12,
                      borderTop: '1px solid var(--lin)',
                      paddingTop: 6,
                    }}
                  >
                    <span className="mono" style={{ color: 'var(--dim)', flexShrink: 0 }}>
                      {fmtFecha(doc.fecha)}
                    </span>
                    <span
                      title={doc.descripcion}
                      style={{
                        flex: 1,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {doc.descripcion}
                    </span>
                    <button
                      type="button"
                      className="mono"
                      disabled={descargando === doc.uuid}
                      onClick={() => void descargar(data.ticker, doc.uuid, doc.descripcion)}
                      style={{ fontSize: 11, flexShrink: 0, cursor: 'pointer' }}
                    >
                      {descargando === doc.uuid ? 'descargando…' : 'Descargar PDF'}
                    </button>
                    <a
                      href={doc.url_publicview}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mono"
                      style={{ fontSize: 11, flexShrink: 0 }}
                    >
                      Ver en CNV
                    </a>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {errorDescarga && (
        <p role="alert" style={{ fontSize: 11, color: 'var(--neg)', marginTop: 8 }}>
          {errorDescarga}
        </p>
      )}
      {data.url_emisor_cnv && (
        <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 10, textWrap: 'pretty' }}>
          Fuente: {data.fuente}
          {' · '}
          <a href={data.url_emisor_cnv} target="_blank" rel="noopener noreferrer">
            Ver todos los documentos del emisor en CNV
          </a>
        </p>
      )}
    </div>
  )
}
