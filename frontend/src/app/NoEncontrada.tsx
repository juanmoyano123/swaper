/** Ruta inexistente. Existe para que una URL mal tipeada no termine en una pantalla en blanco. */

import { Link } from 'react-router-dom'

import { EstadoVacio } from '@/components/EstadoVacio'
import { Pantalla } from '@/components/Pantalla'

export function NoEncontrada() {
  return (
    <Pantalla titulo="Esa pantalla no existe">
      <EstadoVacio
        titulo="La dirección a la que entraste no corresponde a ninguna pantalla."
        detalle={<Link to="/monitor">Volver al monitor de mercado</Link>}
      />
    </Pantalla>
  )
}
