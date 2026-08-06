import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

import { IngresoCarteraPanel } from '@/features/cartera-ingreso/components/IngresoCarteraPanel'

/** Diagnóstico de una cartera existente y propuestas de rotación. */
export function OptimizadorPage() {
  return (
    <Pantalla
      titulo="Optimizador"
      bajada="Cargar una cartera existente, diagnosticarla por los seis ejes de riesgo y proponer rotaciones."
    >
      <Panel rotulo="Cartera del cliente">
        {/* F-028: las tres vías de ingreso. El diagnóstico por ejes de riesgo lo agrega F-030 en
            adelante, una vez que F-029 resuelva estos tickers contra el universo. */}
        <IngresoCarteraPanel />
      </Panel>
    </Pantalla>
  )
}
