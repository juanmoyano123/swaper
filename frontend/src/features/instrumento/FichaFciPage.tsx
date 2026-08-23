import { useParams } from 'react-router-dom'

import { Pantalla } from '@/components/Pantalla'

import { FichaFciContenido } from './FichaFciContenido'

/** La ficha de un FCI como pantalla completa — al entrar por link compartido o al recargar. */
export function FichaFciPage() {
  const { codigoCafci } = useParams<{ codigoCafci: string }>()

  return (
    <Pantalla titulo="Fondo común" bajada="Costos, sociedad gerente y depositaria, y los códigos de la fuente.">
      <FichaFciContenido codigoCafci={codigoCafci ?? null} />
    </Pantalla>
  )
}
