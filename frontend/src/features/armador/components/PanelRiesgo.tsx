/**
 * Vector de riesgo de seis ejes de la cartera en construcción — F-031 (tanda 12).
 *
 * Mismo patrón que `PanelConcentracion.tsx`: posiciones sobre `pesoReal ?? peso`, perfil propio en
 * `useState`, y `useConcentracion(posiciones, perfil)` con la misma firma que `PanelConcentracion`
 * — cache-hit garantizado de TanStack Query cuando el mismo asesor tiene los dos paneles montados
 * a la vez, así que este panel no duplica el POST de concentración.
 *
 * El eje de concentración de `vectorDeRiesgo()` sólo *lee* ese resultado — no recalcula nada acá
 * (regla del plan: "F-031 es un servicio único consumido por los tres" perfiles, `plan.md:2774`).
 */
import { useMemo, useState } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Panel } from '@/components/Panel'
import { VectorDeRiesgo } from '@/components/VectorDeRiesgo'
import { PERFILES, type NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { especieDeRiesgo, vectorDeRiesgo, type EspecieRiesgo } from '@/lib/cartera/riesgo'

import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { useConcentracion } from '../hooks/useConcentracion'

export function PanelRiesgo() {
  const [perfil, setPerfil] = useState<NombreDePerfil>('moderado')
  const { resueltas, porTicker: porTickerEspecie } = useCarteraResuelta()

  // Mismo criterio que `PanelConcentracion`: el peso real cuando se pudo calcular, el pedido si no.
  const posiciones = useMemo(
    () => resueltas.map((r) => ({ ticker: r.ticker, peso: r.pesoReal ?? r.peso })),
    [resueltas],
  )
  const conPesoReal = resueltas.filter((r) => r.pesoReal !== null).length

  const consulta = useConcentracion(posiciones, perfil)

  const porTicker = useMemo(() => {
    const mapa = new Map<string, EspecieRiesgo>()
    for (const especie of porTickerEspecie.values()) mapa.set(especie.ticker, especieDeRiesgo(especie))
    return mapa
  }, [porTickerEspecie])

  const ejes = useMemo(
    () => vectorDeRiesgo(posiciones, porTicker, consulta.data ?? null),
    [posiciones, porTicker, consulta.data],
  )

  return (
    <Panel
      ariaLabel="Vector de riesgo"
      rotulo="Riesgo"
      titulo="Vector de seis ejes"
      acciones={
        <label
          style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11.5, color: 'var(--dim)' }}
        >
          Perfil
          <select
            value={perfil}
            onChange={(evento) => setPerfil(evento.target.value as NombreDePerfil)}
            style={{
              font: 'inherit',
              fontSize: 12,
              color: 'var(--tx)',
              background: 'var(--pan2)',
              border: '1px solid var(--lin)',
              borderRadius: 3,
              padding: '3px 6px',
            }}
          >
            {PERFILES.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {posiciones.length === 0 ? (
        <p style={{ margin: 0, fontSize: 12, color: 'var(--sd)' }}>
          Sin posiciones de renta fija. El vector se mide cuando haya al menos una.
        </p>
      ) : (
        <>
          <p style={{ margin: '0 0 10px', fontSize: 11, color: 'var(--dim)', textWrap: 'pretty' }}>
            {leyendaDelPeso(conPesoReal, posiciones.length)}
          </p>
          {consulta.isPending && <EstadoCarga que="el vector de riesgo" />}
          {consulta.isError && (
            <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
          )}
          {!consulta.isPending && !consulta.isError && <VectorDeRiesgo ejes={ejes} />}
        </>
      )}
    </Panel>
  )
}

/** Qué peso se midió, dicho antes de mostrar cualquier número — calcado de `PanelConcentracion`. */
function leyendaDelPeso(conPesoReal: number, total: number): string {
  if (conPesoReal === total)
    return `Medido sobre el peso real de las ${total} posiciones (invertido sobre el total invertido), no sobre la ponderación pedida.`
  if (conPesoReal === 0)
    return `Medido sobre la ponderación pedida de las ${total} posiciones: ninguna se pudo resolver a peso real por falta de precio o de tipo de cambio.`
  return `Medido sobre el peso real en ${conPesoReal} de ${total} posiciones; en las otras ${total - conPesoReal}, sobre la ponderación pedida (sin precio o sin tipo de cambio).`
}
