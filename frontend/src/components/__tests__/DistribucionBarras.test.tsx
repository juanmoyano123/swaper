/**
 * `DistribucionBarras` — color por índice de tramo (Etapa 1 del rediseño del armador). Antes de
 * esta etapa todos los tramos, de cualquier distribución, se pintaban con el mismo `--ac`; ahora
 * cada posición del array toma un color estable de la paleta categórica, y sólo `sinDato` se
 * distingue con `--sd`.
 */

import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DistribucionBarras } from '../DistribucionBarras'

describe('color por índice de tramo', () => {
  it('pinta cada tramo con un color distinto de la paleta categórica, no todos con --ac', () => {
    render(
      <DistribucionBarras
        titulo="Sector"
        tramos={[
          { nombre: 'Energía', peso: 40 },
          { nombre: 'Financiero', peso: 35 },
          { nombre: 'Consumo', peso: 25 },
        ]}
      />,
    )

    const barras = document.querySelectorAll('li > div[aria-hidden] > div')
    expect(barras).toHaveLength(3)
    expect(barras[0]).toHaveStyle({ background: 'var(--cat1)' })
    expect(barras[1]).toHaveStyle({ background: 'var(--cat2)' })
    expect(barras[2]).toHaveStyle({ background: 'var(--cat3)' })
    // Ninguno quedó en el verde de selección/renta.
    for (const barra of barras) {
      expect(barra).not.toHaveStyle({ background: 'var(--ac)' })
    }
  })

  it('un tramo sin dato se pinta en --sd, no en un color de la paleta', () => {
    render(
      <DistribucionBarras
        titulo="Ley"
        tramos={[
          { nombre: 'Ley argentina', peso: 60 },
          { nombre: 'sin ley informada', peso: 40, sinDato: true },
        ]}
      />,
    )

    const barras = document.querySelectorAll('li > div[aria-hidden] > div')
    expect(barras[0]).toHaveStyle({ background: 'var(--cat1)' })
    expect(barras[1]).toHaveStyle({ background: 'var(--sd)' })
  })

  it('con más de seis tramos, el color se repite ciclando la paleta', () => {
    const tramos = Array.from({ length: 7 }, (_, i) => ({ nombre: `Tramo ${i}`, peso: 1 }))
    render(<DistribucionBarras titulo="Emisor" tramos={tramos} />)

    const barras = document.querySelectorAll('li > div[aria-hidden] > div')
    expect(barras[0]).toHaveStyle({ background: 'var(--cat1)' })
    expect(barras[6]).toHaveStyle({ background: 'var(--cat1)' })
  })
})
