/**
 * `CurvaTirDuracion` vista desde la pantalla — F-023. Componente puro (recibe `candidatos` y
 * `cartera` ya resueltos, sin red): no hace falta `QueryClientProvider` ni mock de `fetch`, mismo
 * criterio que probar `CurvaSegmento` lo sería si tuviera test propio.
 *
 * `ResponsiveContainer` de recharts mide con `ResizeObserver`, que jsdom no implementa: se
 * polyfillea acá mismo, sólo para este archivo, en vez de tocar `src/test/setup.ts` (fuera de la
 * lista de archivos de esta feature).
 */

import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CurvaTirDuracion } from '../components/CurvaTirDuracion'
import type { Especie } from '../lib/schema'

beforeEach(() => {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  vi.stubGlobal('ResizeObserver', ResizeObserverMock)
  // `ResponsiveContainer` mide con `getBoundingClientRect()` antes de que el observer dispare;
  // jsdom la devuelve en cero, así que el gráfico nunca tendría ancho para dibujar sus puntos.
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    width: 600,
    height: 260,
    top: 0,
    left: 0,
    bottom: 260,
    right: 600,
    x: 0,
    y: 0,
    toJSON: () => {},
  })
})

/** recharts mide el ancho de cada texto con un `<span>` oculto y global
 *  (`#recharts_measurement_span`) que conserva el último texto medido entre renders: sin
 *  ignorarlo, un ticker o un rótulo de eje puede aparecer "duplicado" en la búsqueda. */
const SIN_MEDICION = { ignore: '#recharts_measurement_span' }

function especie(extra: Partial<Especie> = {}): Especie {
  return {
    ticker: 'GD30',
    emision: 'GD30',
    sufijo_liquidacion: null,
    clase_activo: 'bono_soberano',
    segmento: 'usd_hard',
    naturaleza: 'tir_usd',
    naturaleza_nombre: 'TIR en dólares (hard dollar)',
    rendimiento: 0.11,
    duracion: 3.2,
    vencimiento: '2030-07-09',
    ley: 'Ley N.Y.',
    moneda_cupon: 'USD',
    emisor: 'República Argentina',
    precio: 70,
    moneda_cotizacion: 'USD',
    volumen: 100_000,
    volumen_usd: 100_000,
    paridad: 0.98,
    lamina: 1,
    sector: 'Soberano',
    calificacion: null,
    dato_sano: true,
    hermanas: [],
    ...extra,
  }
}

describe('sin candidatos', () => {
  it('GIVEN el segmento sin universo THEN dice que no hay curva, sin dibujar un gráfico vacío', () => {
    render(<CurvaTirDuracion candidatos={[]} cartera={[]} naturaleza="tir_usd" />)

    expect(
      screen.getByText(/No hay especies de este segmento en el universo de hoy/),
    ).toBeInTheDocument()
  })
})

describe('candidatos sin rendimiento ni duración', () => {
  it('GIVEN ninguna especie del segmento tiene los dos datos THEN dice que no hay curva que dibujar', () => {
    render(
      <CurvaTirDuracion
        candidatos={[especie({ rendimiento: null }), especie({ ticker: 'AL30', duracion: null })]}
        cartera={[]}
        naturaleza="tir_usd"
      />,
    )

    expect(
      screen.getByText(/Ninguna especie de este segmento tiene rendimiento y duración a la vez/),
    ).toBeInTheDocument()
  })
})

describe('GWT-1/GWT-2: un segmento por gráfico, con la cartera marcada sobre la nube', () => {
  it('dibuja la nube y rotula por ticker las posiciones de la cartera', () => {
    render(
      <CurvaTirDuracion
        candidatos={[especie({ ticker: 'GD30' }), especie({ ticker: 'AL30', rendimiento: 0.09, duracion: 2 })]}
        cartera={[especie({ ticker: 'GD30' })]}
        naturaleza="tir_usd"
      />,
    )

    // El ticker de la posición de cartera se rotula sobre el punto.
    expect(screen.getByText('GD30', SIN_MEDICION)).toBeInTheDocument()
    // Sin exclusiones, no aparece ninguna leyenda de "sin dato".
    expect(screen.queryByText(/sin dato de rendimiento o duración/)).not.toBeInTheDocument()
  })

  it('declara la unidad del eje según la naturaleza, nunca dos naturalezas en el mismo par de ejes', () => {
    render(
      <CurvaTirDuracion
        candidatos={[especie({ segmento: 'cer', naturaleza: 'tasa_real_cer' })]}
        cartera={[]}
        naturaleza="tasa_real_cer"
      />,
    )

    expect(screen.getByText('Tasa real CER', SIN_MEDICION)).toBeInTheDocument()
  })
})

describe('posiciones sin dato, contadas y no marcadas', () => {
  it('GIVEN una posición de cartera sin rendimiento o duración en el segmento activo THEN no se marca en el scatter y se cuenta al pie', () => {
    render(
      <CurvaTirDuracion
        candidatos={[especie({ ticker: 'GD30' })]}
        cartera={[especie({ ticker: 'AL30', rendimiento: null })]}
        naturaleza="tir_usd"
      />,
    )

    expect(
      screen.getByText(/1 posición\(es\) de la cartera sin dato de rendimiento o duración/),
    ).toBeInTheDocument()
    expect(screen.queryByText('AL30', SIN_MEDICION)).not.toBeInTheDocument()
  })

  it('GIVEN candidatos del universo sin rendimiento o duración THEN se cuentan aparte de los de la cartera', () => {
    render(
      <CurvaTirDuracion
        candidatos={[especie({ ticker: 'GD30' }), especie({ ticker: 'AE38', rendimiento: null })]}
        cartera={[]}
        naturaleza="tir_usd"
      />,
    )

    expect(screen.getByText(/1 candidatos sin dato de rendimiento o duración/)).toBeInTheDocument()
  })
})
