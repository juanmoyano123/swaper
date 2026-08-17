/**
 * F-034 — modo "subir la TIR declarando la contrapartida": las rotaciones que suben el rendimiento,
 * cada una con los ejes que empeoran nombrados en su propia unidad, en la misma fila.
 *
 * La regla 8 del dominio se sostiene en el render, no sólo en la lib: `FilaSubirTir` siempre dibuja
 * la línea de contrapartida — con lo que empeora, o con la declaración explícita de que no empeora
 * nada. Nunca queda un espacio en blanco donde debería estar lo que se resigna.
 *
 * La lib pura vive en `@/lib/rotaciones/subirTir`; este componente sólo la conecta con
 * `useSubirTir` y la dibuja. Sección hermana de `SeccionBajarRiesgo`: los dos modos parten de las
 * mismas candidatas y las particionan sin solaparse, así que conviven apiladas en vez de
 * esconderse detrás de un toggle.
 *
 * **F-036** suma la decisión y el efecto de calendario, igual que en `SeccionBajarRiesgo` — ver el
 * docstring de ese archivo para el criterio de `excluir`.
 */

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'
import { fmtPct, SIN_DATO } from '@/lib/fmt'
import { NOMBRES_EJE } from '@/lib/rotaciones/ejes'
import { useSubirTir } from '@/lib/rotaciones/hooks/useSubirTir'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'
import { contrapartidasDe, type EvaluacionEje, type PropuestaSubirTir, type ResultadoSubirTir } from '@/lib/rotaciones/subirTir'

import { BotonesDecision, EfectoCalendarioNota, formatoValor, NotaCosto, ResumenDescartes } from './compartidos'

export function SeccionSubirTir({
  posiciones,
  perfil,
  excluir,
  montos = [],
  monedaDe = () => null,
  tipoDeCambio = null,
  noConvertibles = [],
}: {
  posiciones: PosicionConPeso[]
  perfil: NombreDePerfil
  excluir?: ReadonlySet<string>
  montos?: PosicionConMonto[]
  monedaDe?: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio?: number | null
  noConvertibles?: string[]
}) {
  const { cargando, error, resultado, excluidasPorDecision } = useSubirTir(posiciones, perfil, excluir)

  if (posiciones.length === 0) return null

  return (
    <section
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}
      aria-label="Subir la TIR declarando la contrapartida"
    >
      <header style={{ marginBottom: 10 }}>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Subir la TIR declarando la contrapartida
        </div>
      </header>

      <p style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
        Rotaciones que suben el rendimiento del segmento. Cada una nombra qué eje empeora y en
        cuánto, y qué mes del calendario se llena o se vacía si se acepta.
      </p>
      {excluidasPorDecision > 0 && (
        <p className="mono" style={{ margin: '0 0 10px', fontSize: 10.5, color: 'var(--sd)' }}>
          {excluidasPorDecision} {excluidasPorDecision === 1 ? 'rotación no se propone' : 'rotaciones no se proponen'}:
          ya decidida en esta sesión (descartada, o inversa de una aceptada).
        </p>
      )}

      {cargando && <EstadoCarga que="las rotaciones que suben el rendimiento" />}
      {!cargando && error && <EstadoError error={error} />}
      {!cargando && !error && resultado && (
        <Veredicto resultado={resultado} montos={montos} monedaDe={monedaDe} tipoDeCambio={tipoDeCambio} noConvertibles={noConvertibles} />
      )}
    </section>
  )
}

function Veredicto({
  resultado,
  montos,
  monedaDe,
  tipoDeCambio,
  noConvertibles,
}: {
  resultado: ResultadoSubirTir
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
  noConvertibles: string[]
}) {
  if (!resultado.hayPropuesta && resultado.evaluadas === 0) {
    return (
      <p role="status" style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
        El motor no encontró rotaciones que suban el rendimiento en esta cartera.
      </p>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      {resultado.hayPropuesta ? (
        <ul role="list" aria-label="Rotaciones que suben el rendimiento" style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 8 }}>
          {resultado.propuestas.map((propuesta) => (
            <FilaSubirTir
              key={`${propuesta.candidata.origen.ticker}->${propuesta.candidata.destino.ticker}`}
              propuesta={propuesta}
              montos={montos}
              monedaDe={monedaDe}
              tipoDeCambio={tipoDeCambio}
              noConvertible={noConvertibles.includes(propuesta.candidata.destino.ticker)}
            />
          ))}
        </ul>
      ) : (
        <p role="status" style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
          No hay propuesta: ninguna de las rotaciones que suben el rendimiento pudo mostrarse con su
          contrapartida completa.
        </p>
      )}
      <ResumenDescartes descartes={resultado.descartes} encabezado={encabezadoDescartes(resultado)} />
    </div>
  )
}

/**
 * El recuento de lo evaluado contra lo mostrado. Los plurales van escritos enteros y no como un
 * sufijo concatenado: "rotación" + "es" da *rotaciónes*, que está mal acentuado — el plural pierde
 * la tilde porque la palabra pasa de aguda a grave.
 */
function encabezadoDescartes(resultado: ResultadoSubirTir): string {
  const { evaluadas, propuestas, descartes } = resultado
  const rotaciones = evaluadas === 1 ? '1 rotación que sube' : `${evaluadas} rotaciones que suben`
  const mostradas = propuestas.length === 1 ? '1 mostrada' : `${propuestas.length} mostradas`
  return `${rotaciones} el rendimiento; ${mostradas}, ${descartes.length} sin mostrar:`
}

function FilaSubirTir({
  propuesta,
  montos,
  monedaDe,
  tipoDeCambio,
  noConvertible,
}: {
  propuesta: PropuestaSubirTir
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
  noConvertible: boolean
}) {
  const { candidata } = propuesta
  const contrapartidas = contrapartidasDe(propuesta)
  const conCoberturaParcial = propuesta.ejes.filter((e) => e.cobertura?.parcial && e.estado === 'empeora')

  return (
    <li
      role="listitem"
      style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '10px 12px', display: 'grid', gap: 4 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', fontSize: 12.5 }}>
        <span className="mono" style={{ color: 'var(--tx)' }}>
          {candidata.origen.ticker} → {candidata.destino.ticker}
        </span>
        {/* "Δ rendimiento" y no "TIR": el modo se llama así por la ficha, pero una tasa real sobre
            CER o una TNA en pesos no son una TIR en dólares, y el motor rota dentro del segmento
            (regla 2 — no se etiqueta con la unidad de otra naturaleza). */}
        <span className="mono" style={{ color: 'var(--ac)' }}>
          Δ rendimiento +{fmtPct(candidata.delta.rendimiento_pp, 2)}
        </span>
      </div>

      <p style={{ margin: 0, fontSize: 11.5, color: 'var(--tx)', textWrap: 'pretty' }}>
        {propuesta.ningunEjeEmpeora ? (
          'Ningún eje empeora: la mejora de rendimiento no tiene contrapartida en los seis ejes.'
        ) : (
          <>
            <span style={{ color: 'var(--dim)' }}>Contrapartida: </span>
            {contrapartidas.map((eje, indice) => (
              <span key={eje.eje}>
                {indice > 0 && ' · '}
                {textoContrapartida(eje)}
              </span>
            ))}
          </>
        )}
      </p>

      {conCoberturaParcial.length > 0 && (
        <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
          {conCoberturaParcial.map((eje) => textoCobertura(eje)).join(' · ')}
        </p>
      )}

      <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>{candidata.riesgo_nota}</p>
      <NotaCosto costo={candidata.costo} />
      <EfectoCalendarioNota candidata={candidata} montos={montos} monedaDe={monedaDe} tipoDeCambio={tipoDeCambio} />
      <BotonesDecision
        candidata={candidata}
        deshabilitado={noConvertible}
        motivoDeshabilitado={
          noConvertible
            ? `No hay tipo de cambio para llevar el monto de ${candidata.origen.ticker} a la moneda de ${candidata.destino.ticker}.`
            : null
        }
      />
    </li>
  )
}

/**
 * Un eje que empeora, en su unidad. Legislación nunca se dice "sube" o "baja" a secas: su valor es
 * el peso bajo ley extranjera, y nombrarlo así evita que se lea como un puntaje (regla 7). El
 * cambio de ley se muestra con los literales de la fuente (regla 11).
 */
function textoContrapartida(eje: EvaluacionEje): string {
  if (eje.eje === 'credito') return eje.nota ?? NOMBRES_EJE.credito

  const nombre = eje.eje === 'legislacion' ? 'peso bajo ley extranjera' : NOMBRES_EJE[eje.eje].toLowerCase()
  const movimiento = `${formatoValor(eje.valorActual, eje.unidad)} → ${formatoValor(eje.valorSimulado, eje.unidad)}`
  return eje.nota ? `${nombre} ${movimiento} (${eje.nota})` : `${nombre} ${movimiento}`
}

/** GWT-4: el delta se muestra, y al lado se declara sobre qué parte de la cartera está medido.
 *
 * Un porcentaje sin medir es `SIN_DATO`, nunca "0%": un 0% real diría que no hay cobertura, y acá
 * lo que hay es la ausencia de la medición misma. */
function textoCobertura(eje: EvaluacionEje): string {
  const nombre = NOMBRES_EJE[eje.eje].toLowerCase()
  const actual = eje.cobertura?.pctActual
  const simulada = eje.cobertura?.pctSimulada
  const actualTexto = actual !== null && actual !== undefined ? `${actual}%` : SIN_DATO
  const simuladaTexto = simulada !== null && simulada !== undefined ? `${simulada}%` : SIN_DATO
  return `cobertura parcial: ${nombre} medida sobre el ${actualTexto} del peso actual y el ${simuladaTexto} del simulado`
}
