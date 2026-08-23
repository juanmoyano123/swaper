/**
 * Análisis de FCI: comparador, categorías y gestoras — F-067.
 *
 * Tres secciones detrás de pestañas locales, ninguna con recomendación ni ranking de "mejor
 * fondo" — sólo números duros agregados (dato curado por moneda, nunca una comparación cruzada).
 */

import { useState } from 'react'

import { Panel } from '@/components/Panel'
import { Pantalla } from '@/components/Pantalla'

import { Comparador } from './components/Comparador'
import { TablaCategorias } from './components/TablaCategorias'
import { TablaGestoras } from './components/TablaGestoras'

type Seccion = 'comparador' | 'categorias' | 'gestoras'

const NOMBRE_SECCION: Record<Seccion, string> = {
  comparador: 'Comparador',
  categorias: 'Categorías',
  gestoras: 'Gestoras',
}

const SECCIONES: Seccion[] = ['comparador', 'categorias', 'gestoras']

export function FciAnalisisPage() {
  const [seccion, setSeccion] = useState<Seccion>('comparador')

  return (
    <Pantalla
      titulo="Análisis de FCI"
      bajada="Comparar fondos, y ver el patrimonio agregado por categoría y por sociedad gerente."
    >
      <Panel rotulo="FCI">
        <nav aria-label="Sección de análisis" style={{ display: 'flex', gap: 2, borderBottom: '1px solid var(--lin)', marginBottom: 12 }}>
          {SECCIONES.map((s) => {
            const activa = s === seccion
            return (
              <button
                key={s}
                type="button"
                onClick={() => setSeccion(s)}
                aria-current={activa ? 'true' : undefined}
                style={{
                  font: '600 13px/1 inherit',
                  color: activa ? 'var(--tx)' : 'var(--dim)',
                  background: 'none',
                  border: 'none',
                  borderBottom: activa ? '3px solid var(--ac)' : '3px solid transparent',
                  padding: '9px 14px 8px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {NOMBRE_SECCION[s]}
              </button>
            )
          })}
        </nav>

        {seccion === 'comparador' && <Comparador />}
        {seccion === 'categorias' && <TablaCategorias />}
        {seccion === 'gestoras' && <TablaGestoras />}
      </Panel>
    </Pantalla>
  )
}
