/**
 * `CampoSelect` — F-079, Fase 4. El select compacto compartido que reemplaza las cuatro copias
 * locales de `estiloInput`/`estiloSelectPicker`. Lo que importa acá es el contrato: el rótulo
 * asocia el control (nombre accesible sin `id`), `opciones` es exactamente lo que se dibuja (sin
 * agregar un "todos" por su cuenta), y `onChange`/`disabled`/`title` viajan tal cual al `<select>`.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { CampoSelect } from '../CampoSelect'

describe('CampoSelect', () => {
  it('renderiza el rótulo y las opciones tal como se pasan, sin agregar ninguna propia', () => {
    render(
      <CampoSelect
        etiqueta="Sector"
        valor=""
        onChange={vi.fn()}
        opciones={[
          { valor: '', texto: 'todos' },
          { valor: '73', texto: 'Software' },
          { valor: '28', texto: 'Químicos' },
        ]}
      />,
    )

    const select = screen.getByLabelText('Sector')
    const opciones = Array.from(select.children).map((o) => o.textContent)
    expect(opciones).toEqual(['todos', 'Software', 'Químicos'])
  })

  it('no antepone un "todos": una lista de valores fijos sin esa opción no la gana de regalo', () => {
    render(
      <CampoSelect
        etiqueta="Perfil"
        valor="moderado"
        onChange={vi.fn()}
        opciones={[
          { valor: 'conservador', texto: 'conservador' },
          { valor: 'moderado', texto: 'moderado' },
          { valor: 'agresivo', texto: 'agresivo' },
        ]}
      />,
    )

    const select = screen.getByLabelText('Perfil')
    expect(Array.from(select.children).map((o) => o.textContent)).toEqual([
      'conservador',
      'moderado',
      'agresivo',
    ])
  })

  it('dispara onChange con el valor elegido', async () => {
    const onChange = vi.fn()
    render(
      <CampoSelect
        etiqueta="Sector"
        valor=""
        onChange={onChange}
        opciones={[
          { valor: '', texto: 'todos' },
          { valor: '73', texto: 'Software' },
        ]}
      />,
    )

    await userEvent.selectOptions(screen.getByLabelText('Sector'), '73')

    expect(onChange).toHaveBeenCalledWith('73')
  })

  it('el valor controlado se refleja en el select', () => {
    render(
      <CampoSelect
        etiqueta="Sector"
        valor="73"
        onChange={vi.fn()}
        opciones={[
          { valor: '', texto: 'todos' },
          { valor: '73', texto: 'Software' },
        ]}
      />,
    )

    expect(screen.getByLabelText('Sector')).toHaveValue('73')
  })

  it('el title viaja al select, para el tooltip de la fuente', () => {
    render(
      <CampoSelect
        etiqueta="Sector"
        valor=""
        onChange={vi.fn()}
        opciones={[{ valor: '', texto: 'todos' }]}
        title="SIC 73 — Services-Prepackaged Software (SEC)"
      />,
    )

    expect(screen.getByLabelText('Sector')).toHaveAttribute(
      'title',
      'SIC 73 — Services-Prepackaged Software (SEC)',
    )
  })

  it('disabled se propaga al control', () => {
    render(
      <CampoSelect
        etiqueta="Sector"
        valor=""
        onChange={vi.fn()}
        opciones={[{ valor: '', texto: 'todos' }]}
        disabled
      />,
    )

    expect(screen.getByLabelText('Sector')).toBeDisabled()
  })
})
