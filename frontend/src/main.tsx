import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import { App } from './app/App'
import './index.css'

const contenedor = document.getElementById('root')
if (!contenedor) throw new Error('Falta el elemento #root en index.html')

createRoot(contenedor).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
