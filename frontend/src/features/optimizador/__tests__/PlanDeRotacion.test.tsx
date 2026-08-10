/**
 * `PlanDeRotacion` — F-036, GWT-2 y GWT-3: el panel aparece con la primera aceptación y muestra la
 * lista de lo aceptado; deshacer es LIFO puro, sólo la última tiene botón, y deshacer la única hace
 * desaparecer el panel entero. El calendario y los seis ejes de la cartera propuesta se prueban en
 * `ComparacionCarteras.test.tsx` (F-037), no acá — este panel ya no los muestra.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import type { Candidata } from '@/lib/rotaciones/esquemaRotaciones'

import { PlanDeRotacion } from '../components/PlanDeRotacion'
import { PlanRotacionProvider, usePlanRotacionAcciones } from '../store/planRotacionStore'

function candidata(origenTicker: string, destinoTicker: string): Candidata {
  return {
    tipo: 'mejora_perfil',
    segmento: 'usd_hard',
    origen: { ticker: origenTicker, emisor: 'República Argentina', rendimiento: 0.11, duracion: 3.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 100_000 },
    destino: { ticker: destinoTicker, emisor: 'República Argentina', rendimiento: 0.112, duracion: 2.5, moneda_cupon: 'USD', ley: 'Ley N.Y.', calificacion: null, lamina: 1, frecuencia_cupon: 'semestral', volumen_usd: 300_000 },
    delta: { rendimiento_pp: 0.2, duracion: -1 },
    flags: { mismo_emisor: true, pasa_a_cable: false, mejora_ley: false, empeora_ley: false, mejora_volumen: true, posible_distress: false },
    premio_ley: null,
    riesgo_nota: 'mismo emisor — mismo riesgo crediticio',
    costo: null,
  }
}

function BotonAceptarDeTest({ candidata: c, texto }: { candidata: Candidata; texto: string }) {
  const acciones = usePlanRotacionAcciones()
  return (
    <button type="button" onClick={() => acciones.aceptar(c)}>
      {texto}
    </button>
  )
}

function renderizar() {
  return render(
    <PlanRotacionProvider posiciones={[{ ticker: 'AL30D', peso: 100 }]}>
      <BotonAceptarDeTest candidata={candidata('AL30D', 'GD30D')} texto="aceptar-1" />
      <BotonAceptarDeTest candidata={candidata('GD30D', 'AE38D')} texto="aceptar-2" />
      <PlanDeRotacion />
    </PlanRotacionProvider>,
  )
}

describe('PlanDeRotacion', () => {
  it('sin rotaciones aceptadas, no muestra nada', () => {
    renderizar()
    expect(screen.queryByLabelText('Cartera propuesta')).not.toBeInTheDocument()
  })

  it('al aceptar, aparece el panel con la rotación aceptada (GWT-2)', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))

    const panel = await screen.findByLabelText('Cartera propuesta')
    expect(panel).toHaveTextContent('1 rotación aceptada')
    expect(await screen.findByText(/AL30D.*GD30D/)).toBeInTheDocument()
    expect(await screen.findByRole('button', { name: 'Deshacer' })).toBeInTheDocument()
  })

  it('deshacer la única aceptada hace desaparecer el panel (GWT-3)', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))
    await screen.findByLabelText('Cartera propuesta')

    await usuario.click(screen.getByRole('button', { name: 'Deshacer' }))
    expect(screen.queryByLabelText('Cartera propuesta')).not.toBeInTheDocument()
  })

  it('con dos aceptadas, sólo la última tiene botón Deshacer', async () => {
    const usuario = userEvent.setup()
    renderizar()

    await usuario.click(screen.getByRole('button', { name: 'aceptar-1' }))
    await screen.findByLabelText('Cartera propuesta')
    await usuario.click(screen.getByRole('button', { name: 'aceptar-2' }))

    const panel = await screen.findByLabelText('Cartera propuesta')
    expect(panel).toHaveTextContent('2 rotaciones aceptadas')
    expect(screen.getAllByRole('button', { name: 'Deshacer' })).toHaveLength(1)
    expect(screen.getByText(/de la última a la primera/)).toBeInTheDocument()
  })
})
