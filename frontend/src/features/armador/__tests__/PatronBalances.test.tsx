/**
 * `PatronBalances` en aislamiento — F-027. La integración con `BloqueRentaVariable` (de dónde
 * sale el `calendario` de cada tarjeta) se cubre en `BloqueRentaVariable.test.tsx`.
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PatronBalances } from '../components/PatronBalances'
import type { CalendarioBalances } from '../lib/esquemaBalances'

function calendario(extra: Partial<CalendarioBalances> = {}): CalendarioBalances {
  return {
    papel: 'AAPL',
    fuente: 'SEC EDGAR',
    disponible: true,
    motivo_ausente: null,
    solo_anual: false,
    nota_solo_anual: null,
    cik: '320193',
    ventana: { desde: '2024-01-01', hasta: '2026-08-01' },
    meses: [
      { mes: 2, presentaciones: 1, formularios: ['10-K'] },
      { mes: 5, presentaciones: 1, formularios: ['10-Q'] },
      { mes: 8, presentaciones: 1, formularios: ['10-Q'] },
      { mes: 11, presentaciones: 1, formularios: ['10-Q'] },
    ],
    capturado_en: '2026-08-16T00:00:00Z',
    ...extra,
  }
}

describe('con un patrón disponible', () => {
  it('declara en el nombre accesible en cuántos de los doce meses presenta, y la ventana medida', () => {
    render(<PatronBalances calendario={calendario()} cargando={false} />)

    expect(
      screen.getByRole('img', {
        name: /presenta en 4 de 12 meses.*SEC EDGAR.*2024-01-01.*2026-08-01/,
      }),
    ).toBeInTheDocument()
  })

  it('sin solo_anual no muestra la nota de emisor privado extranjero', () => {
    render(<PatronBalances calendario={calendario()} cargando={false} />)
    expect(screen.queryByText('sólo patrón anual')).not.toBeInTheDocument()
  })
})

describe('un emisor privado extranjero (solo_anual)', () => {
  it('muestra la nota, sin perder el patrón anual detectado', () => {
    render(
      <PatronBalances
        calendario={calendario({
          solo_anual: true,
          nota_solo_anual: 'Esta empresa reporta ante la SEC como emisor privado extranjero.',
          meses: [{ mes: 3, presentaciones: 1, formularios: ['20-F'] }],
        })}
        cargando={false}
      />,
    )

    expect(screen.getByText('sólo patrón anual')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /presenta en 1 de 12 meses/ })).toBeInTheDocument()
  })
})

describe('sin patrón detectable', () => {
  it('declara el motivo en vez de inventar un patrón, con las celdas vacías', () => {
    render(
      <PatronBalances
        calendario={calendario({
          disponible: false,
          motivo_ausente: 'la SEC no lista este papel: no tiene CIK asociado',
          cik: null,
          ventana: null,
          meses: [],
        })}
        cargando={false}
      />,
    )

    expect(screen.getByText('s/d')).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: /no tiene CIK asociado/ }),
    ).toBeInTheDocument()
  })
})

describe('sin calendario todavía', () => {
  it('mientras carga, lo dice en vez de mostrar celdas vacías engañosas', () => {
    render(<PatronBalances calendario={undefined} cargando={true} />)
    expect(screen.getByText('buscando patrón…')).toBeInTheDocument()
  })

  it('si no se pidió nada (no es CEDEAR), declara sin dato', () => {
    render(<PatronBalances calendario={undefined} cargando={false} />)
    expect(screen.getByText('s/d')).toBeInTheDocument()
  })
})
