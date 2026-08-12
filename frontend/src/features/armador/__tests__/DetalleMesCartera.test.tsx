/**
 * `DetalleMesCartera` — el detalle que se abre al clickear una columna de la cordillera de
 * `PanelRenta`. Componente puro sobre el store: sin red, `meses` llega por prop (los mismos que
 * `useCalendarioCartera` ya trajo), así que acá se prueba con fixtures directas, sin mockear
 * `fetch`.
 */

import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { DetalleMesCartera } from '../components/DetalleMesCartera'
import type { InstrumentoDelMes, MesDelCalendario } from '../lib/schema'
import { ArmadorProvider, useArmadorAcciones } from '../store/carteraStore'

function instrumento(extra: Partial<InstrumentoDelMes> = {}): InstrumentoDelMes {
  return {
    ticker: 'AL30',
    emision: 'AL30',
    fechas: ['2026-11-09'],
    pct_renta: 0.01,
    pct_amortizacion: 0,
    renta: 100,
    amortizacion: null,
    moneda: 'usd',
    rendimiento: 0.11,
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    vencimiento: '2030-07-09',
    ...extra,
  }
}

function mes(indice: number, instrumentos: InstrumentoDelMes[] = []): MesDelCalendario {
  return {
    anio: 2026,
    mes: indice + 1,
    etiqueta: `${String(indice + 1).padStart(2, '0')}/2026`,
    nombre: `Mes ${indice + 1}`,
    con_renta: instrumentos.filter((i) => i.pct_renta > 0).length,
    con_amortizacion: 0,
    sin_renta: instrumentos.length === 0,
    renta: null,
    amortizacion: null,
    instrumentos,
  }
}

function docesMeses(sobrescribir: Record<number, InstrumentoDelMes[]> = {}): MesDelCalendario[] {
  return Array.from({ length: 12 }, (_, indice) => mes(indice, sobrescribir[indice] ?? []))
}

function Arnes({ meses }: { meses: MesDelCalendario[] }) {
  const { alternarMes } = useArmadorAcciones()
  return (
    <div>
      <button type="button" onClick={() => alternarMes(2)}>
        abrir mes 3
      </button>
      <DetalleMesCartera meses={meses} />
    </div>
  )
}

function renderizar(meses: MesDelCalendario[]) {
  return render(
    <ArmadorProvider>
      <Arnes meses={meses} />
    </ArmadorProvider>,
  )
}

describe('sin mes seleccionado', () => {
  it('no muestra nada', () => {
    renderizar(docesMeses())
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })
})

describe('mes seleccionado sin pagos de la cartera', () => {
  it('lo declara en vez de mostrar un bloque vacío sin explicación', async () => {
    renderizar(docesMeses())

    await userEvent.click(screen.getByRole('button', { name: 'abrir mes 3' }))

    expect(await screen.findByText(/Ningún papel de la cartera cobra en Mes 3/)).toBeInTheDocument()
  })
})

describe('mes con un papel', () => {
  it('muestra ticker, fecha exacta, monto y el grupo de moneda declarado', async () => {
    renderizar(docesMeses({ 2: [instrumento({ fechas: ['2026-11-09'], renta: 250 })] }))

    await userEvent.click(screen.getByRole('button', { name: 'abrir mes 3' }))

    expect(await screen.findByText('Cobros en dólares (USD)')).toBeInTheDocument()
    expect(screen.getByText('AL30')).toBeInTheDocument()
    expect(screen.getByText('09/11/2026')).toBeInTheDocument()
    expect(screen.getByText('US$ 250')).toBeInTheDocument()
  })
})

describe('un papel que paga dos veces en el mes', () => {
  it('muestra un solo monto con las dos fechas y la leyenda de que no se parte el reparto', async () => {
    renderizar(docesMeses({ 2: [instrumento({ fechas: ['2026-11-09', '2026-11-20'], renta: 300 })] }))

    await userEvent.click(screen.getByRole('button', { name: 'abrir mes 3' }))

    expect(await screen.findByText('09/11/2026 · 20/11/2026')).toBeInTheDocument()
    expect(screen.getByText('US$ 300')).toBeInTheDocument()
    expect(screen.getByText(/la fuente no informa el reparto por fecha/)).toBeInTheDocument()
  })
})

describe('mes con papeles en dos monedas', () => {
  it('separa en dos grupos y nunca suma los montos entre monedas', async () => {
    renderizar(
      docesMeses({
        2: [
          instrumento({ ticker: 'AL30', moneda: 'usd', renta: 200 }),
          instrumento({ ticker: 'TX26', moneda: 'ars', renta: 50000 }),
        ],
      }),
    )

    await userEvent.click(screen.getByRole('button', { name: 'abrir mes 3' }))

    expect(await screen.findByText('Cobros en dólares (USD)')).toBeInTheDocument()
    expect(screen.getByText('Cobros en pesos (ARS)')).toBeInTheDocument()
    // No hay ningún nodo con la suma (200 + 50.000): cada grupo muestra sólo lo suyo.
    expect(screen.queryByText(/50\.200/)).not.toBeInTheDocument()
  })
})

describe('cerrar el detalle', () => {
  it('el botón × cierra el detalle', async () => {
    renderizar(docesMeses({ 2: [instrumento({ renta: 100 })] }))

    await userEvent.click(screen.getByRole('button', { name: 'abrir mes 3' }))
    expect(await screen.findByRole('region')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'cerrar detalle del mes' }))
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })
})
