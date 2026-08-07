/**
 * Estructura que envuelve a todas las pantallas: barra superior fija, barra de estado del dato y
 * el contenido debajo.
 *
 * La de F-013 vive acá y no en cada pantalla por lo que dice su GWT-1: tiene que estar visible en
 * cualquier pantalla de la aplicación, sin navegar a ninguna parte. Montarla en el layout además
 * hace que no se desmonte al cambiar de sección, así que las seis comparten una sola consulta.
 */

import { Outlet } from 'react-router-dom'

import { BarraEstadoDato } from '@/features/estado-dato/components/BarraEstadoDato'

import { BarraSuperior } from './BarraSuperior'

export function AppLayout() {
  return (
    <>
      <BarraSuperior />
      <BarraEstadoDato />
      <main>
        <Outlet />
      </main>
    </>
  )
}
