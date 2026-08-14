/**
 * La ficha de una acción o un CEDEAR — F-053, sin los paneles de Yahoo (14/08/2026).
 *
 * Cada bloque dice de dónde salió. **El bloque propio** sostiene la ficha: precio, cierre
 * anterior, variación, puntas, operaciones, OHLC del día y la clasificación de la SEC (a qué se
 * dedica, rubro, eslabón productivo, y la estrategia si es un fondo). `propio.fuente` declara la
 * procedencia real del precio de cada corrida (BYMA o data912), ver `textoFuentePropia()` acá
 * abajo — el OHLC sí es siempre de BYMA, el overlay no lo toca.
 *
 * **El histórico de cierres es de data912.** **El paquete de estados contables es de la SEC**,
 * sólo para CEDEARs: activos, pasivos, patrimonio, ROE, márgenes y links a los filings reales.
 *
 * **Los paneles de Yahoo Finance (valuación y perfil) se sacaron de la ficha (14/08/2026):
 * decisión del dueño del producto, no los va a usar.** El backend sigue pidiéndole a Yahoo el
 * bloque `externo` — `Cabecera` todavía lo usa como último fallback del nombre de la empresa
 * cuando ni BYMA ni la SEC lo tienen — pero ninguna pantalla vuelve a mostrar su valuación ni su
 * perfil.
 *
 * Lo que no está, y no es un olvido:
 *
 * - **No hay recomendación de analistas, ni precio objetivo, ni consenso.** Eran de Yahoo; son
 *   opinión de terceros y la regla 6 del dominio mantiene el análisis determinístico.
 * - **No hay rendimiento, ni duración, ni paridad.** Una acción no tiene ninguna de las tres y no se
 *   pone nada en su lugar (regla 2).
 * - **Los valores de la SEC no se traducen.** "Office of Energy & Transportation" se muestra como
 *   la fuente lo declara (regla 11); traducirlo sería mostrar nuestra interpretación en el lugar
 *   del dato.
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
  BloqueHistorico as TipoBloqueHistorico,
  BloquePropio,
  BloqueSec,
  PuntoHistorico,
  RatioSec,
} from './lib/schemaRentaVariable'

/** Cómo se lee cada estrategia en pantalla. Espejo de las claves de `app/renta_variable/etfs.py`.
 *  Duplicado a propósito de `BloqueRentaVariable.tsx` del armador: son fichas de features
 *  distintas y no comparten módulo, mismo criterio que ya usa `textoFuentePropia`. */
const ETIQUETA_ESTRATEGIA: Record<string, string> = {
  indice_amplio: 'índice amplio',
  equiponderado: 'equiponderado',
  factor: 'por factor',
  geografico: 'geográfico',
  sectorial: 'sectorial',
  activo_fisico: 'activo físico',
  cripto: 'cripto',
  esg: 'ESG',
  sin_clasificar: 'sin clasificar',
}

/**
 * Experimento data912: `propio.fuente` compone origen y cálculo con `+`
 * ("data912-arrastre+calculo"); acá sólo interesa el origen del precio, en texto humano. Mismo
 * criterio que `textoFuente()` de `FichaInstrumento.tsx`, duplicado a propósito: son fichas de
 * clases de activo distintas y no comparten módulo.
 */
function textoFuentePropia(fuente: string): string {
  const origen = fuente.split('+')[0]
  if (origen === 'data912-arrastre') return 'precio arrastrado de sesión anterior (data912)'
  if (origen === 'data912') return 'data912'
  if (origen === 'byma') return 'BYMA'
  return origen
}

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

  const { propio, externo, historico, sec } = query.data

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <Panel rotulo="El activo">
        <Cabecera propio={propio} externo={externo} />
      </Panel>

      <Panel rotulo={`La rueda de hoy · ${textoFuentePropia(propio.fuente)}`}>
        <BloqueDeLaRueda propio={propio} />
      </Panel>

      <Panel rotulo="La empresa · SEC">
        <BloqueEmpresa propio={propio} />
      </Panel>

      {sec !== undefined && (
        <Panel rotulo={`Estados contables · ${sec.fuente}`}>
          <BloqueEstadosContablesSec sec={sec} />
        </Panel>
      )}

      <Panel rotulo={`Cierres del último año · ${historico.fuente}`}>
        <BloqueHistorico historico={historico} />
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

/** Un rango publicado como par mínimo–máximo. Falta cualquiera de los dos y no hay rango. */
function rango(minimo: number | null, maximo: number | null): string {
  if (minimo === null || maximo === null) return SIN_DATO
  return `${fmtNumero(minimo, 2)} – ${fmtNumero(maximo, 2)}`
}

// --- Cabecera ---------------------------------------------------------------------------------

function Cabecera({ propio, externo }: { propio: BloquePropio; externo: BloqueExterno }) {
  // El nombre sale primero de lo nuestro (SEC o la lista de CEDEARs de BYMA, ver `perfil_fuente`)
  // y sólo cae a Yahoo si lo propio no lo tiene: con Yahoo pausado la cabecera no se queda sin
  // nombre para los papeles que la SEC ya clasificó.
  const nombre =
    propio.nombre_largo ??
    propio.nombre_corto ??
    externo.cotizacion?.nombre_largo ??
    externo.cotizacion?.nombre_corto ??
    null
  const fuenteDelNombre =
    propio.nombre_largo !== null || propio.nombre_corto !== null
      ? (propio.perfil_fuente ?? 'una corrida anterior')
      : externo.fuente
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
        Precio y variación: {textoFuentePropia(propio.fuente)}. El nombre de la empresa
        {nombre === null ? ' no lo entregó ' : ' lo declara '}
        {nombre === null ? externo.fuente : fuenteDelNombre}. La moneda es la que declara la
        fuente, sin convertir.
      </Leyenda>
    </div>
  )
}

// --- Lo nuestro -------------------------------------------------------------------------------

function BloqueDeLaRueda({ propio }: { propio: BloquePropio }) {
  const campos: [string, ReactNode][] = [
    ['Apertura', fmtNumero(propio.precio_apertura, 2)],
    ['Rango del día', rango(propio.precio_minimo, propio.precio_maximo)],
    ['VWAP', fmtNumero(propio.vwap, 2)],
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
        Todo en esta grilla sale del universo consolidado. Apertura, rango del día y VWAP son
        siempre de BYMA, incluso en las filas donde el último precio vino de data912 — la fuente no
        los pisa. El volumen se muestra en dólares sólo cuando la moneda declarada permite
        convertirlo; con EXT, que BYMA no documenta, queda {SIN_DATO}.
      </Leyenda>
    </div>
  )
}

// --- La empresa: la clasificación de la SEC -----------------------------------------------------

function BloqueEmpresa({ propio }: { propio: BloquePropio }) {
  const esFondo = propio.estrategia_etf !== null
  const sinNadaQueMostrar =
    propio.sic_titulo === null &&
    propio.sic_oficina === null &&
    propio.division_cadena === null &&
    propio.ratio_conversion === null &&
    propio.mercado_origen === null &&
    !esFondo

  if (sinNadaQueMostrar) {
    return (
      <EstadoVacio
        titulo="Todavía no se clasificó este papel."
        detalle={
          'La SEC cubre el 74 % de los CEDEARs y el 9 % de las acciones argentinas (13/08/2026); ' +
          'el resto espera a la CNV. No se completa por analogía con otra empresa.'
        }
      />
    )
  }

  const campos: [string, ReactNode][] = [
    ['Actividad', propio.sic_titulo ?? SIN_DATO],
    ['Rubro (SEC)', propio.sic_oficina ?? SIN_DATO],
    ['Eslabón productivo', propio.division_cadena ?? SIN_DATO],
    ['Mercado de origen', propio.mercado_origen ?? SIN_DATO],
    ['Ratio de conversión', propio.ratio_conversion ?? SIN_DATO],
  ]
  if (esFondo) {
    campos.push([
      'Estrategia',
      ETIQUETA_ESTRATEGIA[propio.estrategia_etf ?? ''] ?? propio.estrategia_etf,
    ])
  }

  return (
    <div>
      <Grilla campos={campos} />
      <Leyenda>
        Actividad, rubro y eslabón productivo son de la SEC (código {propio.sic_codigo ?? SIN_DATO},
        la llave de auditoría), sin traducir (regla 11). El eslabón sale de la división del SIC
        Manual, no de una interpretación nuestra. Mercado y ratio son de la tabla oficial de
        CEDEARs de BYMA cuando el papel es un CEDEAR.
        {propio.perfil_capturado_en !== null &&
          ` Clasificado el ${fmtFechaHora(propio.perfil_capturado_en)}.`}
      </Leyenda>
    </div>
  )
}

// --- SEC: estados contables (14/08/2026) -------------------------------------------------------

/**
 * Cómo se lee cada ratio: `pct` para los que son variación o proporción de resultado (ROE, margen,
 * crecimiento), `x` para los de estructura de capital (deuda/patrimonio, liquidez, que se leen como
 * veces), `monto` para el único que lleva moneda propia (EPS). El período va siempre debajo del
 * valor — regla 11: ningún número sin decir de qué fecha es.
 */
function ValorRatioSec({ ratio, tipo }: { ratio: RatioSec | null; tipo: 'pct' | 'x' | 'monto' }) {
  if (ratio === null) return <>{SIN_DATO}</>
  return (
    <>
      <div>
        {tipo === 'pct' && fmtPct(ratio.valor * 100)}
        {tipo === 'x' && `${fmtNumero(ratio.valor, 2)}x`}
        {tipo === 'monto' && (
          <>
            {fmtNumero(ratio.valor, 2)}{' '}
            <span style={{ fontSize: 10.5, color: 'var(--dim)' }}>{ratio.unidad ?? SIN_DATO}</span>
          </>
        )}
      </div>
      <div style={{ fontSize: 9.5, color: 'var(--dim)', marginTop: 2 }}>{fmtFecha(ratio.periodo)}</div>
    </>
  )
}

function BloqueEstadosContablesSec({ sec }: { sec: BloqueSec }) {
  if (!sec.disponible) {
    return (
      <EstadoVacio
        titulo={`${sec.fuente} no tiene estados contables disponibles para este papel.`}
        detalle={
          sec.motivo_ausente ?? 'La fuente no respondió. El resto de la ficha no depende de esto.'
        }
      />
    )
  }

  const r = sec.ratios
  const campos: [string, ReactNode][] = [
    ['ROE', <ValorRatioSec key="roe" ratio={r?.roe ?? null} tipo="pct" />],
    ['Margen operativo', <ValorRatioSec key="mo" ratio={r?.margen_operativo ?? null} tipo="pct" />],
    [
      'Crecimiento de ingresos i.a.',
      <ValorRatioSec key="ci" ratio={r?.crecimiento_ingresos ?? null} tipo="pct" />,
    ],
    ['Ganancia por acción', <ValorRatioSec key="eps" ratio={r?.eps ?? null} tipo="monto" />],
    ['Deuda / patrimonio', <ValorRatioSec key="dp" ratio={r?.deuda_patrimonio ?? null} tipo="x" />],
    [
      'Liquidez corriente',
      <ValorRatioSec key="lc" ratio={r?.liquidez_corriente ?? null} tipo="x" />,
    ],
  ]

  return (
    <div>
      {sec.solo_anual && sec.nota_solo_anual !== null && (
        <p style={{ fontSize: 10.5, color: 'var(--dim)', marginBottom: 10, textWrap: 'pretty' }}>
          {sec.nota_solo_anual}
        </p>
      )}
      <Grilla campos={campos} />
      {sec.filings.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {sec.filings.map((f) => (
            <a
              key={f.url_documento}
              href={f.url_documento}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 11.5, color: 'var(--ac2)' }}
            >
              {f.form} · {fmtFecha(f.fecha)}
            </a>
          ))}
        </div>
      )}
      <Leyenda>
        Estados contables de {sec.fuente}
        {sec.cik !== null && ` (CIK ${sec.cik})`}. Cada ratio se calcula sobre el mismo ejercicio
        fiscal, y el período va debajo del número. El crecimiento de ingresos compara contra el
        ejercicio anterior; PER queda fuera de este paquete porque cruzaría el precio de BYMA con
        el EPS de la SEC en otra moneda.
      </Leyenda>
    </div>
  )
}

// --- data912: histórico -------------------------------------------------------------------------

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

function BloqueHistorico({ historico }: { historico: TipoBloqueHistorico }) {
  if (!historico.disponible) {
    return (
      <EstadoVacio
        titulo={`${historico.fuente} no tiene serie histórica para este símbolo.`}
        detalle={historico.motivo ?? 'La fuente no respondió. El resto de la ficha no depende de esto.'}
      />
    )
  }

  const puntos = historico.puntos
  if (puntos.length < 2) {
    return (
      <EstadoVacio
        titulo="No hay serie de cierres para dibujar."
        detalle={`${historico.fuente} devolvió ${puntos.length} cierre(s) publicado(s) para este símbolo.`}
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
        {puntos.length} cierres publicados por {historico.fuente}. {historico.fuente} no declara la
        moneda de la serie: se muestra tal como la fuente los publica. El eje horizontal es el orden
        de las ruedas, no el calendario, y los días sin cierre publicado no están en la serie: no se
        interpolan.
      </Leyenda>
    </div>
  )
}
