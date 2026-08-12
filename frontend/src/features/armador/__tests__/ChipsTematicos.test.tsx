/**
 * `ChipsTematicos` — Tanda 13. Lo que se fija acá es que un clic precargue los filtros del preset y
 * que el chip se apague cuando los filtros dejan de describir lo que se ve.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ChipsTematicos } from '../components/ChipsTematicos'
import { ArmadorProvider, useArmador, useArmadorAcciones } from '../store/carteraStore'

function Arnes() {
  const { filtros, tematicaId } = useArmador()
  const { fijarFiltros } = useArmadorAcciones()
  return (
    <div>
      <ChipsTematicos />
      <p data-testid="sector">{filtros.sector ?? 'sin sector'}</p>
      <p data-testid="segmento">{filtros.segmento ?? 'sin segmento'}</p>
      <p data-testid="tirMin">{filtros.tirMin === '' ? 'sin tir' : filtros.tirMin}</p>
      <p data-testid="tematica">{tematicaId ?? 'ninguna'}</p>
      <button type="button" onClick={() => fijarFiltros({ ...filtros, tirMin: '8' })}>
        tocar un filtro a mano
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

describe('ChipsTematicos', () => {
  it('aplicar una temática precarga sus filtros de renta fija', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Energía' }))

    expect(screen.getByTestId('sector')).toHaveTextContent('O&G')
    expect(screen.getByTestId('tematica')).toHaveTextContent('energia')
  })

  it('limpia los filtros que había antes, para que el atajo dé siempre lo mismo', async () => {
    renderizar()

    // El default de fábrica trae TIR ≥ 6%: aplicar un preset parte de cero, no acumula.
    expect(screen.getByTestId('tirMin')).toHaveTextContent('6')

    await userEvent.click(screen.getByRole('button', { name: 'Energía' }))

    expect(screen.getByTestId('tirMin')).toHaveTextContent('sin tir')
  })

  it('cobertura inflación filtra por segmento CER, no por sector', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Cobertura inflación' }))

    expect(screen.getByTestId('segmento')).toHaveTextContent('cer')
    expect(screen.getByTestId('sector')).toHaveTextContent('sin sector')
  })

  it('tecnológicas no filtra la renta fija: el universo de bonos no tiene ese sector', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Tecnológicas' }))

    expect(screen.getByTestId('sector')).toHaveTextContent('sin sector')
    expect(screen.getByTestId('tematica')).toHaveTextContent('tecnologicas')
  })

  it('volver a clickear el chip prendido limpia los filtros', async () => {
    renderizar()

    const chip = screen.getByRole('button', { name: 'Energía' })
    await userEvent.click(chip)
    await userEvent.click(chip)

    expect(screen.getByTestId('sector')).toHaveTextContent('sin sector')
    expect(screen.getByTestId('tematica')).toHaveTextContent('ninguna')
  })

  it('el chip se apaga si se toca un filtro a mano, sin deshacer lo que dejó puesto', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Energía' }))
    expect(screen.getByRole('button', { name: 'Energía' })).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(screen.getByRole('button', { name: 'tocar un filtro a mano' }))

    // Apagado, porque la grilla ya no muestra sólo lo que el preset pedía…
    expect(screen.getByRole('button', { name: 'Energía' })).toHaveAttribute('aria-pressed', 'false')
    // …pero el sector que había dejado sigue puesto: apagar el chip no revierte nada.
    expect(screen.getByTestId('sector')).toHaveTextContent('O&G')
  })

  it('cambiar de temática reemplaza la anterior', async () => {
    renderizar()

    await userEvent.click(screen.getByRole('button', { name: 'Energía' }))
    await userEvent.click(screen.getByRole('button', { name: 'Financieras' }))

    expect(screen.getByTestId('sector')).toHaveTextContent('Financiera')
    expect(screen.getByRole('button', { name: 'Energía' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('cada chip explica en su tooltip qué precarga', () => {
    renderizar()

    expect(screen.getByRole('button', { name: 'Tecnológicas' })).toHaveAttribute(
      'title',
      expect.stringContaining('Sólo renta variable'),
    )
  })
})
