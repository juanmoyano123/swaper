/**
 * `contarPorSubtipo` y `SelectorSubtipoSoberano` en aislamiento — los GWT de flujo completo (que el
 * chip sólo aparezca dentro de Soberanos y que cambiar el crédito lo apague) están en
 * `features/monitor/__tests__/MonitorPage.test.tsx`.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { SIN_SUBCLASE, SelectorSubtipoSoberano, contarPorSubtipo } from '../SelectorSubtipoSoberano'

describe('contarPorSubtipo', () => {
  it('cuenta en el orden letra, bonar, global, bopreal y deja el faltante al final', () => {
    const { disponibles, otros } = contarPorSubtipo([
      { subtipo: 'global' },
      { subtipo: null },
      { subtipo: 'letra' },
      { subtipo: 'bopreal' },
      { subtipo: 'letra' },
      { subtipo: 'bonar' },
    ])

    expect(disponibles).toEqual([
      { subtipo: 'letra', especies: 2 },
      { subtipo: 'bonar', especies: 1 },
      { subtipo: 'global', especies: 1 },
      { subtipo: 'bopreal', especies: 1 },
      { subtipo: SIN_SUBCLASE, especies: 1 },
    ])
    expect(otros).toBe(0)
  })

  it('omite los subtipos sin ninguna especie', () => {
    const { disponibles } = contarPorSubtipo([{ subtipo: 'letra' }, { subtipo: 'letra' }])
    expect(disponibles).toEqual([{ subtipo: 'letra', especies: 2 }])
  })

  it('agrupa los null bajo "sin subclase" en vez de descartarlos', () => {
    const { disponibles } = contarPorSubtipo([{ subtipo: null }, { subtipo: null }])
    expect(disponibles).toEqual([{ subtipo: SIN_SUBCLASE, especies: 2 }])
  })

  it('un subtipo que el vocabulario no cubre cae en "otros" y no se pierde del total', () => {
    const especies = [{ subtipo: 'letra' }, { subtipo: 'subtipo_futuro' }]
    const { disponibles, otros } = contarPorSubtipo(especies)

    expect(disponibles).toEqual([{ subtipo: 'letra', especies: 1 }])
    expect(otros).toBe(1)
    const sumaDisponibles = disponibles.reduce((acc, d) => acc + d.especies, 0)
    expect(sumaDisponibles + otros).toBe(especies.length)
  })
})

describe('SelectorSubtipoSoberano', () => {
  it('con una sola subclase y sin "otros" no se dibuja nada', () => {
    const { container } = render(
      <SelectorSubtipoSoberano
        total={5}
        disponibles={[{ subtipo: 'letra', especies: 5 }]}
        otros={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('muestra Todos primero y cada chip con su etiqueta en plural y su conteo', () => {
    render(
      <SelectorSubtipoSoberano
        total={9}
        disponibles={[
          { subtipo: 'letra', especies: 4 },
          { subtipo: 'bonar', especies: 2 },
          { subtipo: 'global', especies: 1 },
          { subtipo: 'bopreal', especies: 1 },
          { subtipo: SIN_SUBCLASE, especies: 1 },
        ]}
        otros={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )

    const radiogroup = screen.getByRole('radiogroup', { name: 'Subtipo soberano' })
    const radios = within(radiogroup).getAllByRole('radio')
    expect(radios.map((r) => r.textContent)).toEqual([
      'Todos 9',
      'Letras 4',
      'Bonares 2',
      'Globales 1',
      'Bopreales 1',
      '(sin subclase) 1',
    ])
    expect(radios[0]).toHaveAttribute('aria-checked', 'true')
  })

  it('el detalle del chip Bopreales nombra al BCRA y aclara que no cambia la concentración', () => {
    render(
      <SelectorSubtipoSoberano
        total={2}
        disponibles={[
          { subtipo: 'letra', especies: 1 },
          { subtipo: 'bopreal', especies: 1 },
        ]}
        otros={0}
        activo={null}
        onCambio={vi.fn()}
      />,
    )

    const chip = screen.getByRole('radio', { name: /Bopreales/ })
    expect(chip).toHaveAttribute('title', expect.stringContaining('BCRA'))
    expect(chip).toHaveAttribute('title', expect.stringContaining('clave soberana'))
  })

  it('clickear un chip llama a onCambio con el subtipo, y "Todos" con null', async () => {
    const onCambio = vi.fn()
    render(
      <SelectorSubtipoSoberano
        total={3}
        disponibles={[
          { subtipo: 'letra', especies: 2 },
          { subtipo: 'bonar', especies: 1 },
        ]}
        otros={0}
        activo="letra"
        onCambio={onCambio}
      />,
    )

    await userEvent.click(screen.getByRole('radio', { name: /Bonares/ }))
    expect(onCambio).toHaveBeenCalledWith('bonar')

    await userEvent.click(screen.getByRole('radio', { name: /Todos/ }))
    expect(onCambio).toHaveBeenCalledWith(null)
  })

  it('la nota de "otros" declara los subtipos que ningún chip cubre', () => {
    render(
      <SelectorSubtipoSoberano
        total={3}
        disponibles={[{ subtipo: 'letra', especies: 2 }]}
        otros={1}
        activo={null}
        onCambio={vi.fn()}
      />,
    )
    expect(screen.getByText(/1 especies con otro subtipo sólo se ven en Todos/)).toBeInTheDocument()
  })
})
