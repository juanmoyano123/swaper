/** Estructura que envuelve a todas las pantallas: barra superior fija y el contenido debajo. */

import { Outlet } from 'react-router-dom'

import { BarraSuperior } from './BarraSuperior'

export function AppLayout() {
  return (
    <>
      <BarraSuperior />
      {/*
        Acá monta F-013 la barra de estado del dato —hora del último refresh, demora declarada de
        la fuente, instrumentos descartados por sanidad y cobertura de campos—. Es transversal a
        todas las pantallas y por eso vive en el layout y no en cada una.
      */}
      <main>
        <Outlet />
      </main>
    </>
  )
}
