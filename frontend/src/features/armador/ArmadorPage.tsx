import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/** Armado de una cartera nueva a partir del mandato del cliente. Es el diseño Cordillera. */
export function ArmadorPage() {
  return (
    <Pantalla
      titulo="Armador"
      bajada="Elegir bonos de forma que los cupones caigan repartidos a lo largo del año."
    >
      <Panel rotulo="Cordillera">
        <EstadoVacio
          titulo="El calendario de cobros todavía no se puede dibujar."
          detalle="El armador lo construyen F-016 a F-018 sobre el diseño Cordillera, y necesita el universo poblado y el calendario de cupones de la ingesta."
        />
      </Panel>
    </Pantalla>
  )
}
