import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/** Carteras guardadas del asesor y seguimiento de las ya vendidas. */
export function CarterasPage() {
  return (
    <Pantalla
      titulo="Mis carteras"
      bajada="Las carteras guardadas, para reabrirlas y revaluarlas, y el seguimiento de las ya vendidas."
    >
      <Panel rotulo="Guardadas">
        <EstadoVacio
          titulo="Todavía no hay carteras guardadas."
          detalle="El guardado y la reapertura los construye F-041, y requieren la sesión del asesor que trae F-014."
        />
      </Panel>
    </Pantalla>
  )
}
