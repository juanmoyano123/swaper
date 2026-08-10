/**
 * Vector de riesgo de seis ejes de la cartera cargada — F-031 (tanda 12).
 *
 * El criterio de aceptación (R12, `plan.md:2774`) es que la misma composición cargada acá y
 * armada en `/armador` muestre el mismo vector: por eso recibe `{ticker, peso}[]`, la misma forma
 * con la que el armador arma sus posiciones, y llama exactamente la misma lib y el mismo
 * componente que `PanelRiesgo` — no hay una segunda implementación que pueda divergir.
 *
 * `useEspeciesUniverso()` y `useConcentracion(posiciones, perfil)` deduplican por TanStack contra
 * lo que `DiagnosticoCartera` ya pidió para `SeccionConcentracion` (misma firma de peso y perfil):
 * este componente no agrega ningún POST nuevo.
 */
import { useMemo } from 'react'

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { VectorDeRiesgo } from '@/components/VectorDeRiesgo'
import type { NombreDePerfil } from '@/lib/cartera/esquemaConcentracion'
import { useConcentracion } from '@/lib/cartera/hooks/useConcentracion'
import { useMapaRiesgo } from '@/lib/cartera/hooks/useMapaRiesgo'
import { vectorDeRiesgo } from '@/lib/cartera/riesgo'

export function SeccionRiesgo({
  posiciones,
  perfil,
}: {
  posiciones: { ticker: string; peso: number }[]
  perfil: NombreDePerfil
}) {
  const { porTicker } = useMapaRiesgo()
  const consulta = useConcentracion(posiciones, perfil)

  const ejes = useMemo(
    () => vectorDeRiesgo(posiciones, porTicker, consulta.data ?? null),
    [posiciones, porTicker, consulta.data],
  )

  // Mismo criterio que el resto de las secciones de `DiagnosticoCartera`: sin posiciones no hay
  // nada que medir.
  if (posiciones.length === 0) return null

  return (
    <section
      style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}
      aria-label="Vector de riesgo de la cartera cargada"
    >
      <div
        className="rotulo"
        style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase', marginBottom: 10 }}
      >
        Riesgo
      </div>

      {consulta.isPending && <EstadoCarga que="el vector de riesgo" />}
      {consulta.isError && <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />}
      {!consulta.isPending && !consulta.isError && <VectorDeRiesgo ejes={ejes} />}
    </section>
  )
}
