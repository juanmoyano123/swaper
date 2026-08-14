/**
 * La ficha de una acción o un CEDEAR — F-053, rediseñada el 13/08/2026 con la pausa de Yahoo.
 *
 * Tres orígenes en una pantalla, y cada bloque dice de dónde salió. **El bloque propio** sostiene
 * la ficha: precio, cierre anterior, variación, puntas, operaciones, OHLC del día y —desde el
 * 13/08/2026— la clasificación de la SEC (a qué se dedica, rubro, eslabón productivo, y la
 * estrategia si es un fondo). Desde el experimento data912 (rama `experimento/data912`) el precio
 * ya no es siempre BYMA — `propio.fuente` declara la procedencia real de cada corrida, ver
 * `textoFuentePropia()` acá abajo — pero el OHLC sí es siempre de BYMA, el overlay no lo toca.
 *
 * **El histórico de cierres es de data912**, no de Yahoo: cubre más papeles y más años que Yahoo
 * daba, y no depende de si Yahoo está pausado.
 *
 * **El bloque externo es Yahoo Finance**, pausado desde el 13/08/2026 (`Settings.yahoo_habilitado`,
 * default `False`: la fuente limita toda esta conexión). Mientras dure la pausa, valuación y perfil
 * de Yahoo se muestran declarados ausentes con el motivo — igual que ante cualquier otro fallo de
 * la fuente, la pantalla no distingue los dos casos.
 *
 * Lo que no está, y no es un olvido:
 *
 * - **No hay recomendación de analistas, ni precio objetivo, ni consenso.** Yahoo los publica; son
 *   opinión de terceros y la regla 6 del dominio mantiene el análisis determinístico. El backend no
 *   los trae y acá no hay dónde ponerlos.
 * - **No hay rendimiento, ni duración, ni paridad.** Una acción no tiene ninguna de las tres y no se
 *   pone nada en su lugar (regla 2).
 * - **Los valores de Yahoo y los de la SEC no se traducen.** "Financial Services" tanto como
 *   "Office of Energy & Transportation" se muestran como la fuente los declara (regla 11);
 *   traducirlos sería mostrar nuestra interpretación en el lugar del dato.
 * - **El precio no lleva símbolo de moneda.** La moneda de cotización se muestra al lado, tal como
 *   la declara la fuente — incluido `EXT`, que BYMA no documenta y que no se toma por dólares.
 * - **Ningún monto de la valuación se muestra sin su moneda.** En un CEDEAR, Yahoo expresa el EPS y
 *   el valor de empresa en la moneda de la especie local, no en la del subyacente: el EPS de
 *   `MSFT.BA` son pesos. Un monto que llegó sin moneda declarada queda vacío y se dice cuál fue
 *   (regla 11); los ratios —PER, precio sobre valor libro, beta— son adimensionales y se muestran
 *   siempre.
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
  MontoExterno,
  PerfilExterno,
  PuntoHistorico,
  ValuacionExterna,
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

  const { propio, externo, historico } = query.data

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

      <Panel rotulo={`Valuación · ${externo.fuente}`}>
        <BloqueValuacion externo={externo} />
      </Panel>

      <Panel rotulo={`Perfil de la empresa · ${externo.fuente}`}>
        <BloquePerfil externo={externo} />
      </Panel>

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

// --- Yahoo: valuación ---------------------------------------------------------------------------

/**
 * Un monto de la fuente con su moneda al lado, siempre. Nunca lleva símbolo: la moneda se escribe
 * como la fuente la declara, igual que el precio de BYMA — un CEDEAR puede traer la valuación en
 * pesos y ponerle "US$" sería equivocar la magnitud por mil.
 */
function Monto({ monto }: { monto: MontoExterno | null }) {
  if (monto === null) return <>{SIN_DATO}</>
  return (
    <>
      {fmtCompacto(monto.valor)}{' '}
      <span style={{ fontSize: 10.5, color: 'var(--dim)' }}>{monto.moneda}</span>
    </>
  )
}

function BloqueValuacion({ externo }: { externo: BloqueExterno }) {
  if (externo.cotizacion === null) return <ExternoAusente externo={externo} />

  if (externo.valuacion === null) {
    return (
      <EstadoVacio
        titulo="La valuación no está disponible."
        detalle={
          externo.perfil_motivo ?? `${externo.fuente} no publica valuación para este símbolo.`
        }
      />
    )
  }

  const v: ValuacionExterna = externo.valuacion
  const campos: [string, ReactNode][] = [
    ['PER (trailing)', fmtNumero(v.per_trailing, 2)],
    ['PER (forward)', fmtNumero(v.per_forward, 2)],
    ['Precio / valor libro', fmtNumero(v.precio_sobre_libros, 2)],
    ['Beta', fmtNumero(v.beta, 3)],
    ['Ganancia por acción', <Monto key="eps" monto={v.ganancia_por_accion} />],
    ['Capitalización', <Monto key="cap" monto={v.capitalizacion} />],
    ['Valor de empresa', <Monto key="ev" monto={v.valor_empresa} />],
  ]

  return (
    <div>
      <Grilla campos={campos} />
      {v.montos_sin_moneda.length > 0 && (
        <p style={{ fontSize: 10.5, color: 'var(--neg)', marginTop: 10, textWrap: 'pretty' }}>
          {v.montos_sin_moneda.length} campo(s) llegaron con número pero sin moneda declarada
          ({v.montos_sin_moneda.join(', ')}) y por eso quedan vacíos. No se los expresa en la moneda
          de cotización: la fuente no dice que sea la misma.
        </p>
      )}
      <Leyenda>
        Cocientes y montos de {externo.fuente}, capturados el {fmtFechaHora(v.capturado_en)}. El PER,
        el precio sobre valor libro y la beta son adimensionales; los montos llevan siempre la moneda
        que la fuente declara para ellos, que en un CEDEAR es la de la especie local y no la del
        subyacente.
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
