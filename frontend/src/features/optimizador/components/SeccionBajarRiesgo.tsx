/**
 * F-033 — modo "mantener la TIR y bajar el riesgo": el asesor elige un eje de los seis de F-031 y
 * el sistema propone rotaciones (F-032) que lo mejoran sin empeorar ninguno de los otros cinco,
 * dentro de la banda de rendimiento de ±0,5pp. La lib pura vive en `@/lib/rotaciones/bajarRiesgo`;
 * este componente sólo la conecta con `useBajarRiesgo` y la dibuja.
 *
 * **Alcance de esta sección, declarado a propósito**: esto es sólo la propuesta. No hay botón de
 * aceptar (llega con F-036) y no toca el calendario de cupones ni ninguna otra pantalla. Lo que sí
 * cambió desde F-034: **cada fila declara el costo real de rotar** (arancel y spread de las dos
 * patas, F-035), o dice que no es verificable cuando falta una punta. Mostrar una rotación como
 * "gratis" sería la regla 8 del dominio rota: toda mejora que se propone nombra qué se resigna.
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
import type { IdDeEje } from '@/lib/cartera/riesgo'

import { formatoValor, NotaCosto, ResumenDescartes } from './compartidos'

export function SeccionBajarRiesgo({
  posiciones,
  perfil,
}: {
  posiciones: PosicionConPeso[]
  perfil: NombreDePerfil
}) {
  const { ejePrimario, setEjePrimario, cargando, error, resultado } = useBajarRiesgo(posiciones, perfil)

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
        Sólo propuesta: no hay botón de aceptar, no toca el calendario ni ninguna otra pantalla.
        Cada fila declara el costo real de rotar —arancel y spread de las dos patas— o avisa cuando
        no es verificable porque falta una punta de mercado.
      </p>

      {cargando && <EstadoCarga que="las rotaciones candidatas" />}
      {!cargando && error && <EstadoError error={error} />}
      {!cargando && !error && resultado && <Veredicto resultado={resultado} ejePrimario={ejePrimario} />}
    </section>
  )
}

function Veredicto({
  resultado,
  ejePrimario,
}: {
  resultado: { hayPropuesta: boolean; noMedible: boolean; motivo: string | null; propuestas: PropuestaBajarRiesgo[]; descartes: DescarteCandidata[] }
  ejePrimario: IdDeEje
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
          <FilaPropuesta key={`${propuesta.candidata.origen.ticker}->${propuesta.candidata.destino.ticker}`} propuesta={propuesta} />
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

function FilaPropuesta({ propuesta }: { propuesta: PropuestaBajarRiesgo }) {
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
    </li>
  )
}

function formatoDelta(propuesta: PropuestaBajarRiesgo): string {
  return `${formatoValor(propuesta.valorActual, propuesta.unidad)} → ${formatoValor(propuesta.valorSimulado, propuesta.unidad)}`
}
