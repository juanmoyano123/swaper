import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { AlertasCalendario } from './components/AlertasCalendario'
import { CoberturaSeleccion } from './components/CoberturaSeleccion'
import { DetalleMes } from './components/DetalleMes'
import { GrillaDoceMeses } from './components/GrillaDoceMeses'
import { useCalendarioUniverso } from './hooks/useCalendarioUniverso'
import { ArmadorProvider } from './store/carteraStore'

/**
 * Armado de una cartera nueva a partir del mandato del cliente. Es el diseño Cordillera.
 *
 * F-016 invierte el orden habitual: el calendario es la entrada, no la salida. `ArmadorProvider`
 * envuelve sólo lo que depende de la selección en curso —F-017 y F-018 van a agregar más adentro
 * de este mismo provider, no al lado.
 */
export function ArmadorPage() {
  const consulta = useCalendarioUniverso()

  return (
    <Pantalla
      titulo="Armador"
      bajada="Elegir bonos de forma que los cupones caigan repartidos a lo largo del año."
    >
      <Panel rotulo="Cordillera">
        {consulta.isPending && <EstadoCarga que="la grilla de doce meses" />}
        {consulta.isError && (
          <EstadoError error={consulta.error} onRetry={() => void consulta.refetch()} />
        )}
        {consulta.data && (
          <ArmadorProvider>
            <CoberturaSeleccion meses={consulta.data.meses} />
            <GrillaDoceMeses meses={consulta.data.meses} />
            <DetalleMes meses={consulta.data.meses} />
            <AlertasCalendario alertas={consulta.data.alertas} />
          </ArmadorProvider>
        )}
      </Panel>
    </Pantalla>
  )
}
