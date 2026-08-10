/**
 * F-036 — el panel "en vivo" de la cartera propuesta: qué se aceptó, el calendario y los seis ejes
 * de la cartera resultante, y Deshacer.
 *
 * GWT-2 y GWT-3 de la spec (`plan.md:1708`). Se apoya en lo que ya existe en vez de construir una
 * pantalla nueva: el calendario reusa `Cordillera` (extraído de `DiagnosticoCartera` en esta misma
 * tanda) y los seis ejes reusan `SeccionRiesgo` (F-031) directamente con `posicionesAcumuladas` — el
 * mismo componente que muestra el vector de la cartera actual, mostrando ahora el de la propuesta.
 *
 * **Deshacer es LIFO puro**: sólo la última aceptada tiene botón. Las aceptaciones se encadenan (el
 * destino de una puede ser el origen de la siguiente), así que deshacer una del medio dejaría a las
 * posteriores con un origen que ya no está en la cartera — el store documenta la misma decisión.
 */

import { Cordillera } from '@/components/Cordillera'
import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { SeccionRiesgo } from '@/features/cartera-diagnostico/components/SeccionRiesgo'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { useCalendarioCartera } from '@/lib/cartera/hooks/useCalendarioCartera'
import { columnasDeCordillera } from '@/lib/cartera/renta'
import { fmtCompacto, fmtMonto, fmtPct } from '@/lib/fmt'
import { claveCandidata } from '@/lib/rotaciones/ejes'
import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'

import { NotaCosto } from './compartidos'
import { usePlanRotacion, usePlanRotacionAcciones } from '../store/planRotacionStore'

export function PlanDeRotacion({ montos, perfil }: { montos: PosicionConMonto[]; perfil: NombreDePerfil }) {
  const plan = usePlanRotacion()
  const acciones = usePlanRotacionAcciones()
  const calendario = useCalendarioCartera(montos)

  if (plan.aceptadas.length === 0) return null

  return (
    <section
      style={{ marginTop: 16, background: 'var(--pan)', border: '1px solid var(--ac)', borderRadius: 4, padding: '12px 16px', display: 'grid', gap: 14 }}
      aria-label="Cartera propuesta"
    >
      <header>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          Cartera propuesta — {plan.aceptadas.length} {plan.aceptadas.length === 1 ? 'rotación aceptada' : 'rotaciones aceptadas'}
        </div>
      </header>

      <ListaAceptadas aceptadas={plan.aceptadas} onDeshacerUltima={acciones.deshacerUltima} />

      {calendario.isPending && <EstadoCarga que="el calendario de la cartera propuesta" />}
      {calendario.isError && <EstadoError error={calendario.error} onRetry={() => void calendario.refetch()} />}
      {calendario.data && <CalendarioPropuesto calendario={calendario.data} />}

      <SeccionRiesgo posiciones={plan.posicionesAcumuladas} perfil={perfil} />
    </section>
  )
}

function ListaAceptadas({
  aceptadas,
  onDeshacerUltima,
}: {
  aceptadas: Candidata[]
  onDeshacerUltima: () => void
}) {
  return (
    <div style={{ display: 'grid', gap: 6 }}>
      <ul role="list" aria-label="Rotaciones aceptadas" style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
        {aceptadas.map((candidata, indice) => {
          const esUltima = indice === aceptadas.length - 1
          return (
            <li
              key={claveCandidata(candidata)}
              role="listitem"
              style={{ background: 'var(--pan2)', border: '1px solid var(--lin)', borderRadius: 4, padding: '8px 10px', display: 'grid', gap: 3 }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', fontSize: 12 }}>
                <span className="mono" style={{ color: 'var(--tx)' }}>
                  {candidata.origen.ticker} → {candidata.destino.ticker}
                </span>
                <span className="mono" style={{ color: 'var(--ac)' }}>
                  Δ rendimiento {fmtPct(candidata.delta.rendimiento_pp, 2)}
                </span>
              </div>
              <NotaCosto costo={candidata.costo} />
              {esUltima && (
                <button
                  type="button"
                  onClick={onDeshacerUltima}
                  style={{ font: 'inherit', fontSize: 11, padding: '4px 10px', borderRadius: 3, cursor: 'pointer', border: '1px solid var(--lin)', background: 'transparent', color: 'var(--dim)', justifySelf: 'start' }}
                >
                  Deshacer
                </button>
              )}
            </li>
          )
        })}
      </ul>
      {aceptadas.length > 1 && (
        <p style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
          Se deshace en orden, de la última a la primera.
        </p>
      )}
    </div>
  )
}

function CalendarioPropuesto({ calendario }: { calendario: ReturnType<typeof useCalendarioCartera>['data'] }) {
  if (!calendario) return null
  const { meses, alertas, resumen } = calendario
  const columnasUsd = columnasDeCordillera(meses, 'usd')
  const columnasArs = columnasDeCordillera(meses, 'ars')
  const hayPosicionesEnPesos = resumen.monedas.includes('ars')

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <Cordillera
        titulo="Renta mensual en dólares — cartera propuesta"
        columnas={columnasUsd}
        alto={120}
        colorBarra="var(--ac)"
        formatoMonto={(v) => fmtMonto(v, 'usd', 0)}
        leyenda="Renta (cupón) en dólares, con las rotaciones aceptadas ya aplicadas."
      />

      {hayPosicionesEnPesos && (
        <Cordillera
          titulo="Renta mensual en pesos — cartera propuesta"
          columnas={columnasArs}
          alto={80}
          colorBarra="var(--ac2)"
          formatoMonto={(v) => `$ ${fmtCompacto(v)}`}
          leyenda="Escala propia, en pesos. Nunca se suma a los dólares ni se convierte para el total."
        />
      )}

      {alertas.length > 0 && (
        <div role="list" aria-label="Alertas del calendario propuesto" style={{ display: 'grid', gap: 4 }}>
          {alertas.map((alerta, indice) => (
            <p
              role="listitem"
              key={`${alerta.codigo}:${indice}`}
              style={{ margin: 0, fontSize: 10.5, color: alerta.severidad === 'error' ? 'var(--neg)' : 'var(--ac2)', textWrap: 'pretty' }}
            >
              {alerta.mensaje}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
