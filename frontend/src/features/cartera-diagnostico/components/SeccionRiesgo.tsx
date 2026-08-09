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
import { useEspeciesUniverso } from '@/lib/cartera/hooks/useEspeciesUniverso'
import { vectorDeRiesgo, type EspecieRiesgo } from '@/lib/cartera/riesgo'

export function SeccionRiesgo({
  posiciones,
  perfil,
}: {
  posiciones: { ticker: string; peso: number }[]
  perfil: NombreDePerfil
}) {
  const especiesUniverso = useEspeciesUniverso()
  const consulta = useConcentracion(posiciones, perfil)

  const porTicker = useMemo(() => {
    const mapa = new Map<string, EspecieRiesgo>()
    for (const especie of especiesUniverso.data ?? []) {
      mapa.set(especie.ticker, {
        ticker: especie.ticker,
        segmento: especie.segmento,
        naturaleza: especie.naturaleza,
        naturaleza_nombre: especie.naturaleza_nombre,
        clase_activo: especie.clase_activo,
        duracion: especie.duracion,
        ley: especie.ley,
        volumen_usd: especie.volumen_usd,
        calificacion: especie.calificacion,
        dato_sano: especie.dato_sano,
      })
    }
    return mapa
  }, [especiesUniverso.data])

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
