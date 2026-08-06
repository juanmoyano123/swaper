import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/** Diagnóstico de una cartera existente y propuestas de rotación. */
export function OptimizadorPage() {
  return (
    <Pantalla
      titulo="Optimizador"
      bajada="Cargar una cartera existente, diagnosticarla por los seis ejes de riesgo y proponer rotaciones."
    >
      <Panel rotulo="Cartera del cliente">
        <EstadoVacio
          titulo="No hay ninguna cartera cargada."
          detalle="El ingreso de carteras lo construye F-028 y el diagnóstico por ejes de riesgo, F-030 en adelante."
        />
      </Panel>
    </Pantalla>
  )
}
