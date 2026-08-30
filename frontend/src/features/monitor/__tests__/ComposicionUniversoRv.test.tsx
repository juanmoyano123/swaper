/**
 * `ComposicionUniversoRv` — cómo se reparte el universo filtrado (F-078, fase 2).
 *
 * Lo que se verifica acá es la unidad del porcentaje, que es la parte que se puede leer mal: pesa
 * por **cantidad de papeles**, no por plata, y las tres especies de un mismo CEDEAR cuentan una
 * sola vez. Y que el faltante sea un tramo propio y no un reparto.
 */

import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import { ComposicionUniversoRv } from '../components/ComposicionUniversoRv'

function especie(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  return {
    ticker: 'AAPL',
    clase_activo: 'cedear',
    precio: 1000,
    moneda_cotizacion: 'ARS',
    cierre_anterior: 990,
    variacion: 0.01,
    volumen: 1_000_000,
    volumen_usd: 1_000,
    px_bid: 999,
    px_ask: 1001,
    operaciones: 10,
    fuente: null,
    emision: null,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    sector_codigo: null,
    sector: null,
    rubro_especifico: null,
    estrategia_etf: null,
    ratio_conversion: null,
    mercado_origen: null,
    region_etf: null,
    etf_indice: null,
    etf_alcance: null,
    etf_pais: null,
    etf_region: null,
    etf_geo_fuente: null,
    etf_geo_verificado: null,
    pais: null,
    region: null,
    pais_fuente: null,
    pais_verificado: null,
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    ...extra,
  }
}

/** La sección de un eje, por su título. */
function eje(titulo: string): HTMLElement {
  return screen.getByRole('heading', { name: titulo, level: 4 }).closest('section') as HTMLElement
}

describe('agrupa por papel, no por especie', () => {
  // AAPL, AAPLC y AAPLD son el mismo CEDEAR de Apple liquidando en tres plazas: comparten
  // `emision`. Contarlas por separado le daría a Estados Unidos el triple de peso que a Vale.
  const APPLE = ['AAPL', 'AAPLC', 'AAPLD'].map((ticker) =>
    especie({ ticker, emision: 'AAPL', pais: 'US', region: 'América del Norte' }),
  )
  const VALE = especie({
    ticker: 'VALE',
    emision: 'VALE',
    pais: 'BR',
    region: 'América Latina y el Caribe',
  })

  it('las hermanas de un papel cuentan una sola vez', () => {
    render(<ComposicionUniversoRv especies={[...APPLE, VALE]} mercados={new Map()} />)

    const pais = eje('País')
    expect(within(pais).getByText('US').parentElement).toHaveTextContent('50,0%')
    expect(within(pais).getByText('BR').parentElement).toHaveTextContent('50,0%')
  })

  it('la leyenda declara la unidad: papeles, no monto invertido', () => {
    render(<ComposicionUniversoRv especies={[...APPLE, VALE]} mercados={new Map()} />)

    expect(screen.getByText(/2 papeles/)).toBeInTheDocument()
    expect(screen.getByText(/no por monto invertido/)).toBeInTheDocument()
  })
})

describe('el faltante es un tramo, no un reparto', () => {
  it('los papeles sin el dato van a su propio tramo, con su peso real', () => {
    render(
      <ComposicionUniversoRv
        especies={[
          especie({ ticker: 'AAPL', emision: 'AAPL', sector_codigo: '73', sector: 'Tecnología' }),
          especie({ ticker: 'GLD', emision: 'GLD' }),
        ]}
        mercados={new Map()}
      />,
    )

    const sector = eje('Sector')
    expect(within(sector).getByText('Tecnología').parentElement).toHaveTextContent('50,0%')
    expect(within(sector).getByText('(sin sector)').parentElement).toHaveTextContent('50,0%')
  })

  it('un eje sin ninguna fuente todavía se muestra al 100 % sin dato, no se esconde', () => {
    render(
      <ComposicionUniversoRv
        especies={[especie({ ticker: 'AAPL', emision: 'AAPL' })]}
        mercados={new Map()}
      />,
    )

    const pais = eje('País')
    expect(within(pais).getByText('(sin país)').parentElement).toHaveTextContent('100,0%')
  })
})

describe('los ejes leen el dato como la fuente lo declara', () => {
  it('región cae en cascada: la curada de la empresa y el token crudo del fondo son tramos distintos', () => {
    render(
      <ComposicionUniversoRv
        especies={[
          especie({ ticker: 'PBR', emision: 'PBR', pais: 'BR', region: 'América Latina y el Caribe' }),
          especie({ ticker: 'EWZ', emision: 'EWZ', region_etf: 'Brazil', estrategia_etf: 'geografico' }),
        ]}
        mercados={new Map()}
      />,
    )

    const region = eje('Región')
    expect(within(region).getByText('América Latina y el Caribe')).toBeInTheDocument()
    expect(within(region).getByText('Brazil')).toBeInTheDocument()
  })

  it('país unifica pais (empresa) y etf_pais (ETF mono-país curado) en el mismo tramo', () => {
    render(
      <ComposicionUniversoRv
        especies={[
          especie({ ticker: 'PBR', emision: 'PBR', pais: 'BR' }),
          especie({ ticker: 'EWZ', emision: 'EWZ', pais: null, etf_pais: 'BR' }),
        ]}
        mercados={new Map()}
      />,
    )

    const pais = eje('País')
    expect(within(pais).getByText('BR').parentElement).toHaveTextContent('100,0%')
  })

  it('sector sin etiqueta ES muestra el código crudo, no un tramo vacío', () => {
    render(
      <ComposicionUniversoRv
        especies={[especie({ ticker: 'B', emision: 'B', sector_codigo: '10', sector: null })]}
        mercados={new Map()}
      />,
    )

    const sector = eje('Sector')
    expect(within(sector).getByText('10').parentElement).toHaveTextContent('100,0%')
  })

  it('el mercado se agrupa por la forma canónica: dos variantes de caja son una sola barra', () => {
    render(
      <ComposicionUniversoRv
        especies={[
          especie({ ticker: 'A1', emision: 'A1', mercado_origen: 'NYSE Arca' }),
          especie({ ticker: 'A2', emision: 'A2', mercado_origen: 'NYSE ARCA' }),
        ]}
        mercados={new Map([['nyse arca', 'NYSE Arca']])}
      />,
    )

    const mercado = eje('Mercado')
    expect(within(mercado).getByText('NYSE Arca').parentElement).toHaveTextContent('100,0%')
    expect(within(mercado).queryByText('NYSE ARCA')).not.toBeInTheDocument()
  })
})
