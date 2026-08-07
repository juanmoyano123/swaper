/**
 * El store del armador, aislado de la grilla — F-016.
 *
 * `alternarPapel` y `alternarMes` son las dos acciones sobre las que se apoya toda la pantalla: la
 * iluminación multi-mes de GWT-1/GWT-2 y la apertura/cierre del detalle de mes. Un arnés mínimo
 * alcanza para probarlas sin montar la grilla entera.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ArmadorProvider, useArmador, useArmadorAcciones } from '../store/carteraStore'

function Arnes() {
  const { pos, selMes } = useArmador()
  const { alternarPapel, alternarMes } = useArmadorAcciones()

  return (
    <div>
      <p data-testid="pos">{pos.map((p) => p.ticker).join(',')}</p>
      <p data-testid="selMes">{selMes === null ? 'ninguno' : String(selMes)}</p>
      <button type="button" onClick={() => alternarPapel('AL30')}>
        alternar AL30
      </button>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        alternar GD30
      </button>
      <button type="button" onClick={() => alternarMes(3)}>
        alternar mes 3
      </button>
      <button type="button" onClick={() => alternarMes(7)}>
        alternar mes 7
      </button>
    </div>
  )
}

function renderizar() {
  return render(
    <ArmadorProvider>
      <Arnes />
    </ArmadorProvider>,
  )
}

describe('alternarPapel', () => {
  it('agrega el papel si no está en la cartera', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))

    expect(screen.getByTestId('pos')).toHaveTextContent('AL30')
  })

  it('saca el papel si ya estaba', async () => {
    renderizar()

    const boton = screen.getByRole('button', { name: 'alternar AL30' })
    await userEvent.click(boton)
    await userEvent.click(boton)

    expect(screen.getByTestId('pos')).toHaveTextContent('')
  })

  it('mantiene el orden de incorporación con más de un papel', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar GD30' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))

    expect(screen.getByTestId('pos')).toHaveTextContent('GD30,AL30')
  })
})

describe('alternarMes', () => {
  it('selecciona el mes cuando no había ninguno activo', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar mes 3' }))

    expect(screen.getByTestId('selMes')).toHaveTextContent('3')
  })

  it('des-selecciona si se vuelve a clickear el mismo mes', async () => {
    renderizar()

    const boton = screen.getByRole('button', { name: 'alternar mes 3' })
    await userEvent.click(boton)
    await userEvent.click(boton)

    expect(screen.getByTestId('selMes')).toHaveTextContent('ninguno')
  })

  it('cambia de mes activo sin necesitar des-seleccionar primero', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar mes 3' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar mes 7' }))

    expect(screen.getByTestId('selMes')).toHaveTextContent('7')
  })
})
