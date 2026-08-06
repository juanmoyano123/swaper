/** Raíz de la aplicación: providers, red de contención y router. */

import { QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { BrowserRouter } from 'react-router-dom'

import { ErrorBoundary } from './ErrorBoundary'
import { AppRoutes } from './rutas'
import { crearQueryClient } from './queryClient'

export function App() {
  // El cliente se crea una sola vez por montaje y no en el módulo: así cada test levanta el suyo
  // y no hereda la caché del anterior.
  const [queryClient] = useState(crearQueryClient)

  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  )
}
