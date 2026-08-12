/**
 * F-033 — modo "mantener la TIR y bajar el riesgo": el asesor elige un eje de los seis de F-031 y
 * el sistema propone rotaciones (F-032) que lo mejoran sin empeorar ninguno de los otros cinco,
 * dentro de la banda de rendimiento de ±0,5pp. La lib pura vive en `@/lib/rotaciones/bajarRiesgo`;
 * este componente sólo la conecta con `useBajarRiesgo` y la dibuja.
 *
 * **F-036 suma la decisión.** Cada fila declara el costo real de rotar (F-035) y ahora también qué
 * mes del calendario se llena o se vacía si se acepta, y trae Aceptar/Descartar. `excluir` son las
 * claves que el plan ya decidió en esta sesión (descartadas, o inversas de una rotación aceptada):
 * se filtran antes de evaluar y se declaran aparte, nunca como un descarte por eje.
 */

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import type { PosicionConPeso } from '@/lib/cartera/hooks/useConcentracion'
import { fmtPct } from '@/lib/fmt'
import { useBajarRiesgo } from '@/lib/rotaciones/hooks/useBajarRiesgo'
import {
  BANDA_RENDIMIENTO_PP,
  NOMBRES_EJE,
  TODOS_LOS_EJES,
  type DescarteCandidata,
  type PropuestaBajarRiesgo,
} from '@/lib/rotaciones/bajarRiesgo'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'
import type { IdDeEje } from '@/lib/cartera/riesgo'

import { BotonesDecision, EfectoCalendarioNota, formatoValor, NotaCosto, ResumenDescartes } from './compartidos'

export function SeccionBajarRiesgo({
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
  const { ejePrimario, setEjePrimario, cargando, error, resultado, excluidasPorDecision } = useBajarRiesgo(
    posiciones,
    perfil,
    excluir,
  )

  if (posiciones.length === 0) return null

  return (
    <section
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}
      aria-label="Mantener la TIR y bajar el riesgo"
    >
      <header style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 10 }}>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Mantener la TIR y bajar el riesgo
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)' }}>
          Eje a mejorar
          <select
            value={ejePrimario}
            onChange={(evento) => setEjePrimario(evento.target.value as IdDeEje)}
            style={{ font: 'inherit', fontSize: 12, color: 'var(--tx)', background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 3, padding: '3px 6px' }}
          >
            {TODOS_LOS_EJES.map((eje) => (
              <option key={eje} value={eje}>
                {NOMBRES_EJE[eje]}
              </option>
            ))}
          </select>
        </label>
      </header>

      <p style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
        Cada fila declara el costo real de rotar —arancel y spread de las dos patas— y qué mes del
        calendario se llena o se vacía si se acepta.
      </p>
      {excluidasPorDecision > 0 && (
        <p className="mono" style={{ margin: '0 0 10px', fontSize: 10.5, color: 'var(--sd)' }}>
          {excluidasPorDecision} {excluidasPorDecision === 1 ? 'rotación no se propone' : 'rotaciones no se proponen'}:
          ya decidida en esta sesión (descartada, o inversa de una aceptada).
        </p>
      )}

      {cargando && <EstadoCarga que="las rotaciones candidatas" />}
      {!cargando && error && <EstadoError error={error} />}
      {!cargando && !error && resultado && (
        <Veredicto
          resultado={resultado}
          ejePrimario={ejePrimario}
          montos={montos}
          monedaDe={monedaDe}
          tipoDeCambio={tipoDeCambio}
          noConvertibles={noConvertibles}
        />
      )}
    </section>
  )
}

function Veredicto({
  resultado,
  ejePrimario,
  montos,
  monedaDe,
  tipoDeCambio,
  noConvertibles,
}: {
  resultado: { hayPropuesta: boolean; noMedible: boolean; motivo: string | null; propuestas: PropuestaBajarRiesgo[]; descartes: DescarteCandidata[] }
  ejePrimario: IdDeEje
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
  noConvertibles: string[]
}) {
  if (resultado.noMedible) {
    return (
      <p role="status" style={{ margin: 0, fontSize: 12, color: 'var(--sd)', textWrap: 'pretty' }}>
        {resultado.motivo}
      </p>
    )
  }

  if (!resultado.hayPropuesta) {
    return (
      <div style={{ display: 'grid', gap: 8 }}>
        <p role="status" style={{ margin: 0, fontSize: 12, color: 'var(--tx)', textWrap: 'pretty' }}>
          No hay propuesta: ninguna candidata de rotación mejora {NOMBRES_EJE[ejePrimario].toLowerCase()} sin
          empeorar alguno de los otros cinco ejes, dentro de la banda de ±{fmtPct(BANDA_RENDIMIENTO_PP, 1)} de
          rendimiento.
        </p>
        <ResumenDescartes descartes={resultado.descartes} />
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 10 }}>
      <ul role="list" aria-label="Propuestas de rotación" style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 8 }}>
        {resultado.propuestas.map((propuesta) => (
          <FilaPropuesta
            key={`${propuesta.candidata.origen.ticker}->${propuesta.candidata.destino.ticker}`}
            propuesta={propuesta}
            montos={montos}
            monedaDe={monedaDe}
            tipoDeCambio={tipoDeCambio}
            noConvertible={noConvertibles.includes(propuesta.candidata.destino.ticker)}
          />
        ))}
      </ul>
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        Banda de rendimiento aplicada: ±{fmtPct(BANDA_RENDIMIENTO_PP, 1)} — misma banda con la que el motor
        ordena destinos parejos.
      </p>
      {resultado.descartes.length > 0 && <ResumenDescartes descartes={resultado.descartes} />}
    </div>
  )
}

function FilaPropuesta({
  propuesta,
  montos,
  monedaDe,
  tipoDeCambio,
  noConvertible,
}: {
  propuesta: PropuestaBajarRiesgo
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
  noConvertible: boolean
}) {
  const { candidata } = propuesta
  return (
    <li
      role="listitem"
      style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '10px 12px', display: 'grid', gap: 4 }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', fontSize: 12.5 }}>
        <span className="mono" style={{ color: 'var(--tx)' }}>
          {candidata.origen.ticker} → {candidata.destino.ticker}
        </span>
        <span className="mono" style={{ color: 'var(--ac)' }}>
          {formatoDelta(propuesta)}
        </span>
      </div>
      <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>{candidata.riesgo_nota}</p>
      <p className="mono" style={{ margin: 0, fontSize: 10.5, color: 'var(--sd)' }}>
        Δ rendimiento {fmtPct(candidata.delta.rendimiento_pp, 2)}
      </p>
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

function formatoDelta(propuesta: PropuestaBajarRiesgo): string {
  return `${formatoValor(propuesta.valorActual, propuesta.unidad)} → ${formatoValor(propuesta.valorSimulado, propuesta.unidad)}`
}
