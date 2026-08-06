import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/** Pantalla de entrada: el universo por segmento, para consultar sin armar nada. */
export function MonitorPage() {
  return (
    <Pantalla
      titulo="Monitor de mercado"
      bajada="El universo por segmento, con filtros y orden, para consultar sin armar una cartera."
    >
      <Panel rotulo="Universo">
        <EstadoVacio
          titulo="Todavía no hay instrumentos para mostrar."
          detalle="La grilla del universo la construye F-038, y los datos llegan cuando corra la primera ingesta de mercado (F-004 a F-007)."
        />
      </Panel>
    </Pantalla>
  )
}
