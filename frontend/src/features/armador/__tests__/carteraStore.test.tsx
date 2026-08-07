/**
 * El store del armador, aislado de la grilla — F-016, extendido por F-018 con peso y montoTotal.
 *
 * `alternarPapel` y `alternarMes` son las dos acciones sobre las que se apoya toda la pantalla: la
 * iluminación multi-mes de GWT-1/GWT-2 y la apertura/cierre del detalle de mes. Un arnés mínimo
 * alcanza para probarlas sin montar la grilla entera. F-018 agrega `fijarPeso`, `equiponderar` y
 * `vaciar` al mismo arnés, y expone el peso de cada posición para poder verificarlo.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ArmadorProvider, useArmador, useArmadorAcciones } from '../store/carteraStore'

function Arnes() {
  const { pos, selMes } = useArmador()
  const { alternarPapel, alternarMes, fijarPeso, equiponderar, vaciar } = useArmadorAcciones()

  return (
    <div>
      <p data-testid="pos">{pos.map((p) => p.ticker).join(',')}</p>
      <p data-testid="pesos">{pos.map((p) => `${p.ticker}:${p.peso}`).join(',')}</p>
      <p data-testid="selMes">{selMes === null ? 'ninguno' : String(selMes)}</p>
      <button type="button" onClick={() => alternarPapel('AL30')}>
        alternar AL30
      </button>
      <button type="button" onClick={() => alternarPapel('GD30')}>
        alternar GD30
      </button>
      <button type="button" onClick={() => alternarPapel('AE38')}>
        alternar AE38
      </button>
      <button type="button" onClick={() => alternarMes(3)}>
        alternar mes 3
      </button>
      <button type="button" onClick={() => alternarMes(7)}>
        alternar mes 7
      </button>
      <button type="button" onClick={() => fijarPeso('AL30', 60)}>
        fijar peso AL30 en 60
      </button>
      <button type="button" onClick={() => equiponderar()}>
        equiponderar
      </button>
      <button type="button" onClick={() => vaciar()}>
        vaciar
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

describe('alternarPapel — peso al agregar (F-018)', () => {
  it('asigna 100/(n+1) al agregar un papel nuevo, sin tocar el peso de los que ya estaban', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))
    expect(screen.getByTestId('pesos')).toHaveTextContent('AL30:100')

    await userEvent.click(screen.getByRole('button', { name: 'alternar GD30' }))
    // n=1 antes de agregar GD30: 100/2 = 50. AL30 sigue en 100, no se recalcula.
    expect(screen.getByTestId('pesos')).toHaveTextContent('AL30:100,GD30:50')

    await userEvent.click(screen.getByRole('button', { name: 'alternar AE38' }))
    // n=2 antes de agregar AE38: 100/3 = 33,3. Los otros dos siguen como estaban.
    expect(screen.getByTestId('pesos')).toHaveTextContent('AL30:100,GD30:50,AE38:33.3')
  })
})

describe('fijarPeso (F-018)', () => {
  it('pisa el peso pedido de esa posición y no toca las demás', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar GD30' }))
    // Antes: AL30:100,GD30:50.

    await userEvent.click(screen.getByRole('button', { name: 'fijar peso AL30 en 60' }))

    expect(screen.getByTestId('pesos')).toHaveTextContent('AL30:60,GD30:50')
  })
})

describe('equiponderar (F-018)', () => {
  it('reparte 100/n igual a todas las posiciones', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar GD30' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar AE38' }))
    await userEvent.click(screen.getByRole('button', { name: 'fijar peso AL30 en 60' }))

    await userEvent.click(screen.getByRole('button', { name: 'equiponderar' }))

    expect(screen.getByTestId('pesos')).toHaveTextContent('AL30:33.3,GD30:33.3,AE38:33.3')
  })
})

describe('vaciar (F-018)', () => {
  it('deja la cartera sin posiciones', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'alternar AL30' }))
    await userEvent.click(screen.getByRole('button', { name: 'alternar GD30' }))

    await userEvent.click(screen.getByRole('button', { name: 'vaciar' }))

    expect(screen.getByTestId('pos')).toHaveTextContent('')
  })
})
