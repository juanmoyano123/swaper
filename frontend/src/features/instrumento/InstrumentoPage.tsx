import { useParams } from 'react-router-dom'

import { Pantalla } from '@/components/Pantalla'

import { FichaInstrumento } from './FichaInstrumento'

/**
 * La ficha como pantalla completa.
 *
 * Es lo que se ve al entrar por un link compartido o al recargar: sin pantalla de fondo no hay
 * sobre qué superponer el drawer. Abriéndola desde adentro de la aplicación se ve como panel
 * lateral, con el mismo contenido y la misma URL.
 */
export function InstrumentoPage() {
  const { ticker } = useParams<{ ticker: string }>()

  return (
    <Pantalla
      titulo={<span className="mono">{ticker}</span>}
      bajada="Condiciones de emisión, el mismo papel en las tres monedas y el cronograma de pagos."
    >
      <FichaInstrumento ticker={ticker} />
    </Pantalla>
  )
}
