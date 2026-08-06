import { useParams } from 'react-router-dom'

import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'
import { Panel } from '@/components/Panel'

/**
 * Ficha de un instrumento: condiciones de emisión, las tres especies y el flujo de fondos.
 *
 * Tiene URL propia para poder compartir el link de un papel. F-039 la convierte en el drawer
 * lateral del diseño, sin cambiar la ruta.
 */
export function InstrumentoPage() {
  const { ticker } = useParams<{ ticker: string }>()

  return (
    <Pantalla
      titulo={<span className="mono">{ticker}</span>}
      bajada="Condiciones de emisión, el mismo papel en las tres monedas y el cronograma de pagos."
    >
      <Panel rotulo="Ficha">
        <EstadoVacio
          titulo="No hay datos de este instrumento todavía."
          detalle="La ficha completa la construye F-039 y se alimenta del universo consolidado que puebla la ingesta."
        />
      </Panel>
    </Pantalla>
  )
}
