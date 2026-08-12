/**
 * `BadgeClase` — Tanda 13. Lo que se fija acá es que las cinco clases conocidas se rotulen con su
 * sigla, y sobre todo que una clase que no está en la tabla se muestre tal cual viene en vez de
 * caer en la categoría más parecida (regla 11 del dominio).
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BadgeClase, rotuloDeClase } from '../components/BadgeClase'

describe('rotuloDeClase', () => {
  it.each([
    ['bono_soberano', 'SOB'],
    ['bono_subsoberano', 'SUB'],
    ['on_corporativo', 'ON'],
    ['accion', 'ACC'],
    ['cedear', 'CEDEAR'],
  ])('%s se rotula %s', (clase, sigla) => {
    expect(rotuloDeClase(clase).sigla).toBe(sigla)
  })

  it('distingue soberano de subsoberano: son créditos distintos', () => {
    expect(rotuloDeClase('bono_soberano').sigla).not.toBe(rotuloDeClase('bono_subsoberano').sigla)
  })

  it('una clase desconocida se muestra literal y sin color, no se traduce a la más parecida', () => {
    const rotulo = rotuloDeClase('fideicomiso_financiero')

    expect(rotulo.sigla).toBe('fideicomiso_financiero')
    expect(rotulo.color).toBe('var(--dim)')
  })
})

describe('BadgeClase', () => {
  it('dibuja la sigla de la clase', () => {
    render(<BadgeClase claseActivo="on_corporativo" />)

    expect(screen.getByText('ON')).toBeInTheDocument()
  })

  it('explica la sigla en el title — nadie tiene por qué saber que SUB es subsoberano', () => {
    render(<BadgeClase claseActivo="bono_subsoberano" />)

    expect(screen.getByText('SUB')).toHaveAttribute('title', 'Bono subsoberano')
  })

  it('sin clase no dibuja nada: un "s/d" al lado de cada ticker sería ruido', () => {
    const { container } = render(<BadgeClase claseActivo={undefined} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('con clase null tampoco dibuja', () => {
    const { container } = render(<BadgeClase claseActivo={null} />)

    expect(container).toBeEmptyDOMElement()
  })
})
