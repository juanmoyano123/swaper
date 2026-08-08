/**
 * La ficha de una acción o un CEDEAR — F-053.
 *
 * Dos orígenes en una pantalla, y cada bloque dice de dónde salió. **El bloque propio es BYMA** y es
 * el que sostiene la ficha: precio, cierre anterior, variación, puntas y operaciones. **El bloque
 * externo es Yahoo Finance**, con la hora en que se lo capturó, y puede faltar entero sin que la
 * pantalla se rompa — cuando falta, se declara y lo nuestro se muestra igual.
 *
 * Lo que no está, y no es un olvido:
 *
 * - **No hay recomendación de analistas, ni precio objetivo, ni consenso.** Yahoo los publica; son
 *   opinión de terceros y la regla 6 del dominio mantiene el análisis determinístico. El backend no
 *   los trae y acá no hay dónde ponerlos.
 * - **No hay rendimiento, ni duración, ni paridad.** Una acción no tiene ninguna de las tres y no se
 *   pone nada en su lugar (regla 2).
 * - **Los valores de Yahoo no se traducen.** "Financial Services" y "Banks - Regional" se muestran
 *   como la fuente los declara (regla 11); traducirlos sería mostrar nuestra interpretación en el
 *   lugar del dato.
 * - **El precio no lleva símbolo de moneda.** La moneda de cotización se muestra al lado, tal como
 *   la declara la fuente — incluido `EXT`, que BYMA no documenta y que no se toma por dólares.
 */

import type { ReactNode } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { EstadoVacio } from '@/components/EstadoVacio'
import { Panel } from '@/components/Panel'
import { fmtCompacto, fmtFecha, fmtFechaHora, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'

import { useFichaRentaVariable } from './hooks/useFichaRentaVariable'
import type {
  BloqueExterno,
  BloquePropio,
  CotizacionExterna,
  PerfilExterno,
  PuntoHistorico,
} from './lib/schemaRentaVariable'

export function FichaRentaVariable({ ticker }: { ticker: string }) {
  const query = useFichaRentaVariable(ticker)

  if (query.isPending) {
    return (
      <Panel rotulo="Ficha">
        <EstadoCarga que={`la ficha de ${ticker}`} />
      </Panel>
    )
  }

  if (query.isError) {
    return (
      <Panel rotulo="Ficha">
        <EstadoError error={query.error} onRetry={() => void query.refetch()} />
      </Panel>
    )
  }

  const { propio, externo } = query.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Panel rotulo="El activo">
        <Cabecera propio={propio} externo={externo} />
      </Panel>

      <Panel rotulo="La rueda de hoy · BYMA">
        <BloqueDeLaRueda propio={propio} />
      </Panel>

      <Panel rotulo={`Resumen · ${externo.fuente}`}>
        <BloqueResumen externo={externo} />
      </Panel>

      <Panel rotulo={`Perfil de la empresa · ${externo.fuente}`}>
        <BloquePerfil externo={externo} />
      </Panel>

      <Panel rotulo={`Cierres del último año · ${externo.fuente}`}>
        <BloqueHistorico externo={externo} />
      </Panel>
    </div>
  )
}

// --- Piezas compartidas -----------------------------------------------------------------------

function Campo({ etiqueta, valor }: { etiqueta: string; valor: ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: 'var(--dim)' }}>{etiqueta}</div>
      <div className="mono" style={{ fontSize: 13 }}>
        {valor}
      </div>
    </div>
  )
}

function Grilla({ campos }: { campos: [string, ReactNode][] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px 16px' }}>
      {campos.map(([etiqueta, valor]) => (
        <Campo key={etiqueta} etiqueta={etiqueta} valor={valor} />
      ))}
    </div>
  )
}

function Leyenda({ children }: { children: ReactNode }) {
  return (
    <p style={{ fontSize: 10.5, color: 'var(--dim)', marginTop: 10, textWrap: 'pretty' }}>
      {children}
    </p>
  )
}

/** El bloque externo no vino: se dice por qué y no se muestra nada más. */
function ExternoAusente({ externo }: { externo: BloqueExterno }) {
  return (
    <EstadoVacio
      titulo={`${externo.fuente} no está disponible para ${externo.simbolo_consultado}.`}
      detalle={
        externo.motivo ??
        'La fuente externa no respondió. Lo que muestra esta ficha de BYMA no depende de ella.'
      }
    />
  )
}

/** Un rango publicado como par mínimo–máximo. Falta cualquiera de los dos y no hay rango. */
function rango(minimo: number | null, maximo: number | null): string {
  if (minimo === null || maximo === null) return SIN_DATO
  return `${fmtNumero(minimo, 2)} – ${fmtNumero(maximo, 2)}`
}

// --- Cabecera ---------------------------------------------------------------------------------

function Cabecera({ propio, externo }: { propio: BloquePropio; externo: BloqueExterno }) {
  // El nombre de la empresa es lo único de la cabecera que sale de Yahoo. Sin Yahoo la ficha
  // arranca con el ticker de BYMA y nada inventado en su lugar.
  const nombre = externo.cotizacion?.nombre_largo ?? externo.cotizacion?.nombre_corto ?? null
  const variacion = propio.variacion
  const color =
    variacion === null || variacion === 0 ? 'var(--tx)' : variacion > 0 ? 'var(--pos)' : 'var(--neg)'

  return (
    <div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--tx)', textWrap: 'pretty' }}>
        {nombre ?? `${propio.ticker} — nombre no disponible`}
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginTop: 8 }}>
        <span className="mono" style={{ fontSize: 24 }}>
          {fmtNumero(propio.precio, 2)}
        </span>
        <span style={{ fontSize: 11.5, color: 'var(--dim)' }}>
          {propio.moneda_cotizacion ?? SIN_DATO}
        </span>
        <span className="mono" style={{ fontSize: 14, color, marginLeft: 'auto' }}>
          {variacion === null ? SIN_DATO : fmtPct(variacion * 100)}
        </span>
      </div>
      <Leyenda>
        Precio y variación: {propio.fuente}. El nombre de la empresa
        {nombre === null ? ' no lo entregó ' : ' lo declara '}
        {externo.fuente}. La moneda es la que declara la fuente, sin convertir.
      </Leyenda>
    </div>
  )
}

// --- Lo nuestro -------------------------------------------------------------------------------

function BloqueDeLaRueda({ propio }: { propio: BloquePropio }) {
  const campos: [string, ReactNode][] = [
    ['Cierre anterior', fmtNumero(propio.cierre_anterior, 2)],
    ['Variación', propio.variacion === null ? SIN_DATO : fmtPct(propio.variacion * 100)],
    ['Compra', fmtNumero(propio.px_bid, 2)],
    ['Venta', fmtNumero(propio.px_ask, 2)],
    ['Operaciones', fmtNumero(propio.operaciones, 0)],
    ['Volumen (USD)', fmtCompacto(propio.volumen_usd)],
  ]

  return (
    <div>
      <Grilla campos={campos} />
      <Leyenda>
        Todo en esta grilla sale del universo consolidado de {propio.fuente}. El volumen se muestra
        en dólares sólo cuando la moneda declarada permite convertirlo; con EXT, que BYMA no
        documenta, queda {SIN_DATO}.
      </Leyenda>
    </div>
  )
}

// --- Yahoo: resumen ---------------------------------------------------------------------------

function BloqueResumen({ externo }: { externo: BloqueExterno }) {
  if (externo.cotizacion === null) return <ExternoAusente externo={externo} />

  const c: CotizacionExterna = externo.cotizacion
  const campos: [string, ReactNode][] = [
    ['Último', fmtNumero(c.precio, 2)],
    ['Cierre previo', fmtNumero(c.cierre_previo, 2)],
    ['Rango del día', rango(c.minimo_dia, c.maximo_dia)],
    ['Rango 52 semanas', rango(c.minimo_52_semanas, c.maximo_52_semanas)],
    ['Volumen', fmtCompacto(c.volumen)],
    ['Moneda', c.moneda ?? SIN_DATO],
  ]

  return (
    <div>
      <Grilla campos={campos} />
      <Leyenda>
        {externo.fuente} · símbolo {c.simbolo} · bolsa {c.bolsa_nombre ?? c.bolsa} · capturado el{' '}
        {fmtFechaHora(c.capturado_en)}. Son los números de otra fuente para el mismo papel: no
        reemplazan los de BYMA ni se promedian con ellos.
      </Leyenda>
    </div>
  )
}

// --- Yahoo: perfil ----------------------------------------------------------------------------

function BloquePerfil({ externo }: { externo: BloqueExterno }) {
  if (externo.cotizacion === null) return <ExternoAusente externo={externo} />

  if (externo.perfil === null) {
    return (
      <EstadoVacio
        titulo="El perfil de la empresa no está disponible."
        detalle={
          externo.perfil_motivo ??
          `${externo.fuente} entregó la cotización pero no los datos de la empresa.`
        }
      />
    )
  }

  const p: PerfilExterno = externo.perfil
  const campos: [string, ReactNode][] = [
    ['País', p.pais ?? SIN_DATO],
    ['Sector', p.sector ?? SIN_DATO],
    ['Industria', p.industria ?? SIN_DATO],
    ['Empleados', fmtNumero(p.empleados, 0)],
  ]

  return (
    <div>
      <Grilla campos={campos} />
      {p.sitio !== null && (
        <div style={{ marginTop: 10, fontSize: 11.5 }}>
          <a href={p.sitio} target="_blank" rel="noreferrer" style={{ color: 'var(--ac2)' }}>
            {p.sitio}
          </a>
        </div>
      )}
      <Leyenda>
        País, sector e industria se muestran <strong>tal como {externo.fuente} los declara</strong>,
        sin traducir: son su vocabulario, no una clasificación nuestra. Capturado el{' '}
        {fmtFechaHora(p.capturado_en)}.
      </Leyenda>
    </div>
  )
}

// --- Yahoo: histórico -------------------------------------------------------------------------

const ANCHO = 300
const ALTO = 72

/**
 * Los cierres diarios como línea, sin ejes ni grilla: es una silueta de la serie, no un gráfico
 * para leer valores. Los números que sí se pueden leer van escritos abajo, en texto.
 *
 * Dos decisiones que conviene saber al mirarlo: **el eje horizontal es el orden de las ruedas, no
 * el calendario** —un feriado no deja hueco— y **los días sin cierre publicado no están en la
 * serie**: la fuente no los trae y no se interpolan.
 */
function Sparkline({ puntos }: { puntos: PuntoHistorico[] }) {
  const cierres = puntos.map((p) => p.cierre)
  const minimo = Math.min(...cierres)
  const maximo = Math.max(...cierres)
  const amplitud = maximo - minimo

  const coordenadas = puntos.map((punto, indice) => {
    const x = (indice / (puntos.length - 1)) * ANCHO
    // Serie plana: sin amplitud, la línea va al medio en vez de dividir por cero.
    const y = amplitud === 0 ? ALTO / 2 : ALTO - ((punto.cierre - minimo) / amplitud) * ALTO
    return `${x.toFixed(1)},${y.toFixed(1)}`
  })

  const primero = puntos[0]
  const ultimo = puntos[puntos.length - 1]

  return (
    <svg
      role="img"
      aria-label={
        `Cierres diarios desde ${fmtFecha(primero.fecha)} hasta ${fmtFecha(ultimo.fecha)}: ` +
        `mínimo ${fmtNumero(minimo, 2)}, máximo ${fmtNumero(maximo, 2)}, ` +
        `último ${fmtNumero(ultimo.cierre, 2)}.`
      }
      viewBox={`0 0 ${ANCHO} ${ALTO}`}
      preserveAspectRatio="none"
      style={{ width: '100%', height: ALTO, display: 'block' }}
    >
      <polyline
        points={coordenadas.join(' ')}
        fill="none"
        stroke="var(--ac)"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
        // Sin esto, el escalado horizontal del viewBox deforma el grosor del trazo.
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  )
}

function BloqueHistorico({ externo }: { externo: BloqueExterno }) {
  if (externo.cotizacion === null) return <ExternoAusente externo={externo} />

  const puntos = externo.cotizacion.historico
  if (puntos.length < 2) {
    return (
      <EstadoVacio
        titulo="No hay serie de cierres para dibujar."
        detalle={`${externo.fuente} devolvió ${puntos.length} cierre(s) publicado(s) para este símbolo.`}
      />
    )
  }

  const cierres = puntos.map((p) => p.cierre)
  const primero = puntos[0]
  const ultimo = puntos[puntos.length - 1]

  return (
    <div>
      <Sparkline puntos={puntos} />
      <div
        className="mono"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 10.5,
          color: 'var(--dim)',
          marginTop: 4,
        }}
      >
        <span>{fmtFecha(primero.fecha)}</span>
        <span>{fmtFecha(ultimo.fecha)}</span>
      </div>
      <div style={{ marginTop: 10 }}>
        <Grilla
          campos={[
            ['Mínimo de la serie', fmtNumero(Math.min(...cierres), 2)],
            ['Máximo de la serie', fmtNumero(Math.max(...cierres), 2)],
            ['Primer cierre', fmtNumero(primero.cierre, 2)],
            ['Último cierre', fmtNumero(ultimo.cierre, 2)],
          ]}
        />
      </div>
      <Leyenda>
        {puntos.length} cierres publicados por {externo.fuente} en{' '}
        {externo.cotizacion.moneda ?? SIN_DATO}. El eje horizontal es el orden de las ruedas, no el
        calendario, y los días sin cierre publicado no están en la serie: no se interpolan.
      </Leyenda>
    </div>
  )
}
