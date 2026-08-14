/**
 * `contarPorCredito` y `SelectorCredito` en aislamiento, sin fetch mockeado — los GWT de flujo
 * completo con la tabla real están en `features/monitor/__tests__/MonitorPage.test.tsx`.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SelectorCredito, contarPorCredito } from '../SelectorCredito'

describe('contarPorCredito', () => {
  it('cuenta cada crédito reconocido en el orden soberano, subsoberano, ON', () => {
    const { disponibles, otras } = contarPorCredito([
      { clase_activo: 'on_corporativo' },
      { clase_activo: 'bono_soberano' },
      { clase_activo: 'bono_soberano' },
      { clase_activo: 'bono_subsoberano' },
    ])

    expect(disponibles).toEqual([
      { credito: 'bono_soberano', especies: 2 },
      { credito: 'bono_subsoberano', especies: 1 },
      { credito: 'on_corporativo', especies: 1 },
    ])
    expect(otras).toBe(0)
  })

  it('omite créditos sin ninguna especie', () => {
    const { disponibles } = contarPorCredito([{ clase_activo: 'bono_soberano' }])
    expect(disponibles).toEqual([{ credito: 'bono_soberano', especies: 1 }])
  })

  it('una clase de activo que no es ninguna de las tres cae en "otras", no en disponibles', () => {
    const { disponibles, otras } = contarPorCredito([
      { clase_activo: 'bono_soberano' },
      { clase_activo: 'clase_inventada' },
      { clase_activo: 'clase_inventada' },
    ])
    expect(disponibles).toEqual([{ credito: 'bono_soberano', especies: 1 }])
    expect(otras).toBe(2)
  })

  it('la suma de disponibles + otras cuadra con el total de especies', () => {
    const especies = [
      { clase_activo: 'bono_soberano' },
      { clase_activo: 'on_corporativo' },
      { clase_activo: 'clase_inventada' },
    ]
    const { disponibles, otras } = contarPorCredito(especies)
    const sumaDisponibles = disponibles.reduce((acc, d) => acc + d.especies, 0)
    expect(sumaDisponibles + otras).toBe(especies.length)
  })
})

describe('SelectorCredito', () => {
  it('con un solo crédito real y sin "otras" no se dibuja nada', () => {
    const { container } = render(
      <SelectorCredito
        total={3}
        disponibles={[{ credito: 'bono_soberano', especies: 3 }]}
        otras={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('con dos créditos muestra Todos primero y cada chip con su conteo', () => {
    render(
      <SelectorCredito
        total={4}
        disponibles={[
          { credito: 'bono_soberano', especies: 3 },
          { credito: 'on_corporativo', especies: 1 },
        ]}
        otras={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )

    const radiogroup = screen.getByRole('radiogroup', { name: 'Crédito' })
    const radios = within(radiogroup).getAllByRole('radio')
    expect(radios.map((r) => r.textContent)).toEqual(['Todos 4', 'Soberanos 3', 'ONs 1'])
    expect(radios[0]).toHaveAttribute('aria-checked', 'true')
    expect(screen.queryByRole('radio', { name: /Subsoberanos/ })).not.toBeInTheDocument()
  })

  it('la nota de "otras" sólo aparece cuando hay alguna', () => {
    const { rerender } = render(
      <SelectorCredito
        total={2}
        disponibles={[{ credito: 'bono_soberano', especies: 1 }]}
        otras={1}
        activo={null}
        onCambio={vi.fn()}
      />,
    )
    expect(screen.getByText(/1 especies con otra clase de activo sólo se ven en Todos/)).toBeInTheDocument()

    rerender(
      <SelectorCredito
        total={4}
        disponibles={[
          { credito: 'bono_soberano', especies: 3 },
          { credito: 'on_corporativo', especies: 1 },
        ]}
        otras={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )
    expect(screen.queryByText(/sólo se ven en Todos/)).not.toBeInTheDocument()
  })

  it('clickear un chip llama a onCambio con el crédito, y "Todos" con null', async () => {
    const onCambio = vi.fn()
    render(
      <SelectorCredito
        total={4}
        disponibles={[
          { credito: 'bono_soberano', especies: 3 },
          { credito: 'on_corporativo', especies: 1 },
        ]}
        otras={0}
        activo="bono_soberano"
        onCambio={onCambio}
      />,
    )

    await userEvent.click(screen.getByRole('radio', { name: /^ONs/ }))
    expect(onCambio).toHaveBeenCalledWith('on_corporativo')

    await userEvent.click(screen.getByRole('radio', { name: /^Todos/ }))
    expect(onCambio).toHaveBeenCalledWith(null)
  })
})
