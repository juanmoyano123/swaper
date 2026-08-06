/**
 * Barra fija de 52 px, común a todas las pantallas.
 *
 * Del diseño Cordillera se toma lo que F-003 puede sostener de verdad: marca, navegación,
 * indicador de conexión y botón de tema. El selector de cliente, el monto y el conmutador de
 * moneda pertenecen al armador y aparecen cuando esa feature exista — ponerlos ahora sería
 * interfaz muerta que no hace nada al tocarla.
 */

import { NavLink } from 'react-router-dom'

import { EstadoBackend } from '@/features/salud/EstadoBackend'
import { useTema } from '@/lib/theme'

const SECCIONES = [
  { a: '/monitor', texto: 'Monitor' },
  { a: '/armador', texto: 'Armador' },
  { a: '/optimizador', texto: 'Optimizador' },
  { a: '/carteras', texto: 'Mis carteras' },
] as const

export function BarraSuperior() {
  const { tema, alternar } = useTema()

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 40,
        height: 52,
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        padding: '0 18px',
        background: 'var(--pan)',
        borderBottom: '1px solid var(--lin)',
      }}
    >
      <NavLink
        to="/monitor"
        style={{ display: 'flex', alignItems: 'baseline', gap: 6, textDecoration: 'none' }}
      >
        <span style={{ fontSize: 17, fontWeight: 700, letterSpacing: '-0.01em', color: 'var(--tx)' }}>
          10-Swaper
        </span>
      </NavLink>

      <nav style={{ display: 'flex', gap: 6 }}>
        {SECCIONES.map((seccion) => (
          <NavLink
            key={seccion.a}
            to={seccion.a}
            style={({ isActive }) => ({
              fontSize: 12,
              padding: '6px 14px',
              borderRadius: 3,
              textDecoration: 'none',
              border: `1px solid ${isActive ? 'var(--ac)' : 'var(--lin)'}`,
              background: isActive ? 'var(--ac)' : 'transparent',
              color: isActive ? 'var(--bg)' : 'var(--dim)',
            })}
          >
            {seccion.texto}
          </NavLink>
        ))}
      </nav>

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 10 }}>
        <EstadoBackend />
        <button
          type="button"
          onClick={alternar}
          aria-label={tema === 'dark' ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro'}
          style={{
            font: 'inherit',
            fontSize: 13,
            width: 28,
            height: 26,
            borderRadius: 3,
            border: '1px solid var(--lin)',
            background: 'transparent',
            color: 'var(--dim)',
            cursor: 'pointer',
          }}
        >
          {tema === 'dark' ? '☾' : '☀'}
        </button>
      </div>
    </header>
  )
}
