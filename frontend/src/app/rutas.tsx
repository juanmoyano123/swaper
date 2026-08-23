/**
 * Las seis pantallas de la aplicación.
 *
 * Salen de `product-definition.md`, sección "Pantallas esenciales". El toggle Armado/Seguimiento
 * del diseño Cordillera mapea a `/armador` y a la parte de seguimiento de `/carteras`; el drawer de
 * ficha del prototipo, a `/instrumento/:ticker`.
 *
 * Esa última ruta se ve de dos formas y por eso hay dos árboles de rutas acá abajo. Cuando se llega
 * desde adentro de la aplicación, la navegación guarda la ubicación anterior en `state.fondo`: el
 * primer árbol sigue renderizando la pantalla de fondo —con su estado y su scroll intactos— y el
 * segundo superpone el drawer. Cuando se entra por un link compartido no hay `state.fondo`, así que
 * el primer árbol matchea la ficha y la muestra como página completa.
 *
 * Es también el motivo de usar `<BrowserRouter>` en lugar de `createBrowserRouter`: pasarle una
 * `location` distinta a `<Routes>` es lo que hace posible este doble render.
 */

import { Navigate, Route, Routes, useLocation } from 'react-router-dom'

import { ArmadorPage } from '@/features/armador/ArmadorPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { RequiereSesion } from '@/features/auth/RequiereSesion'
import { CarteraGuardadaPage } from '@/features/carteras/CarteraGuardadaPage'
import { CarterasPage } from '@/features/carteras/CarterasPage'
import { FichaFciDrawer } from '@/features/instrumento/FichaFciDrawer'
import { FichaFciPage } from '@/features/instrumento/FichaFciPage'
import { InstrumentoDrawer } from '@/features/instrumento/InstrumentoDrawer'
import { InstrumentoPage } from '@/features/instrumento/InstrumentoPage'
import { MonitorPage } from '@/features/monitor/MonitorPage'
import { OptimizadorPage } from '@/features/optimizador/OptimizadorPage'

import { AppLayout } from './AppLayout'
import { NoEncontrada } from './NoEncontrada'

type EstadoDeNavegacion = { fondo?: Location } | null

export function AppRoutes() {
  const location = useLocation()
  const fondo = (location.state as EstadoDeNavegacion)?.fondo

  return (
    <>
      <Routes location={fondo ?? location}>
        {/* Fuera del layout: la pantalla de ingreso no tiene barra superior ni chip de estado. */}
        <Route path="/login" element={<LoginPage />} />

        <Route
          path="/"
          element={
            <RequiereSesion>
              <AppLayout />
            </RequiereSesion>
          }
        >
          {/* El monitor es la entrada diaria: se consulta el mercado mucho más seguido de lo que
              se arma una cartera. */}
          <Route index element={<Navigate to="/monitor" replace />} />
          <Route path="monitor" element={<MonitorPage />} />
          <Route path="armador" element={<ArmadorPage />} />
          <Route path="optimizador" element={<OptimizadorPage />} />
          <Route path="carteras" element={<CarterasPage />} />
          <Route path="carteras/:id" element={<CarteraGuardadaPage />} />
          <Route path="instrumento/:ticker" element={<InstrumentoPage />} />
          <Route path="fci/:codigoCafci" element={<FichaFciPage />} />
          <Route path="*" element={<NoEncontrada />} />
        </Route>
      </Routes>

      {fondo && (
        <Routes>
          <Route path="/instrumento/:ticker" element={<InstrumentoDrawer />} />
          <Route path="/fci/:codigoCafci" element={<FichaFciDrawer />} />
        </Routes>
      )}
    </>
  )
}
