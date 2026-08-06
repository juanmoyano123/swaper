/**
 * Las seis pantallas de la aplicación.
 *
 * Salen de `product-definition.md`, sección "Pantallas esenciales". El diseño Cordillera describe
 * su toggle Armado/Seguimiento sobre una sola ruta: ese toggle mapea a `/armador` y a la parte de
 * seguimiento de `/carteras`, y el drawer de ficha del prototipo, a `/instrumento/:ticker`.
 *
 * La definición vive separada del router para que los tests puedan montarla en memoria.
 */

import type { RouteObject } from 'react-router-dom'
import { Navigate } from 'react-router-dom'

import { ArmadorPage } from '@/features/armador/ArmadorPage'
import { LoginPage } from '@/features/auth/LoginPage'
import { CarterasPage } from '@/features/carteras/CarterasPage'
import { InstrumentoPage } from '@/features/instrumento/InstrumentoPage'
import { MonitorPage } from '@/features/monitor/MonitorPage'
import { OptimizadorPage } from '@/features/optimizador/OptimizadorPage'

import { AppLayout } from './AppLayout'
import { NoEncontrada } from './NoEncontrada'

export const rutas: RouteObject[] = [
  {
    path: '/',
    element: <AppLayout />,
    children: [
      // El monitor es la entrada diaria: se consulta el mercado mucho más seguido de lo que se
      // arma una cartera.
      { index: true, element: <Navigate to="/monitor" replace /> },
      { path: 'login', element: <LoginPage /> },
      { path: 'monitor', element: <MonitorPage /> },
      { path: 'armador', element: <ArmadorPage /> },
      { path: 'optimizador', element: <OptimizadorPage /> },
      { path: 'carteras', element: <CarterasPage /> },
      { path: 'instrumento/:ticker', element: <InstrumentoPage /> },
      { path: '*', element: <NoEncontrada /> },
    ],
  },
]
