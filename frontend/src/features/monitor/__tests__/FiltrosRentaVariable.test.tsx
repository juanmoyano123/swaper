/**
 * `FiltrosRentaVariable` — el mission control de diversificación de CEDEARs (F-078, fase 2),
 * rediseñado por F-079 (fase 5, 29/08/2026): buscador + presets arriba, seis `CampoSelect` en vez
 * de la pared de chips.
 *
 * Los inputs se arman con `facetarRentaVariable` de verdad en vez de a mano: lo que se prueba acá
 * es que la pantalla muestre lo que el facetado decidió, y un fixture inventado podría describir un
 * estado que el facetado nunca produce.
 */

import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { PRESETS_RV } from '@/lib/presetsRv'
import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import { FiltrosRentaVariable } from '../components/FiltrosRentaVariable'
import {
  FILTROS_RV_VACIOS,
  facetarRentaVariable,
  type FiltrosRentaVariable as TipoFiltros,
} from '../lib/filtrosRentaVariable'

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

/** Monta los filtros sobre un universo real, con el facetado ya corrido. */
function montar(
  especies: EspecieRentaVariable[],
  filtros: Partial<TipoFiltros> = {},
  onCambio: (f: TipoFiltros) => void = () => {},
) {
  const crudos = { ...FILTROS_RV_VACIOS, ...filtros }
  const { opciones, efectivos, apagadas, etiquetas } = facetarRentaVariable(especies, crudos, 'ARS')
  render(
    <FiltrosRentaVariable
      filtros={crudos}
      efectivos={efectivos}
      opciones={opciones}
      apagadas={apagadas}
      etiquetas={etiquetas}
      onCambio={onCambio}
    />,
  )
}

const APPLE = especie({ ticker: 'AAPL', pais: 'US', sector_codigo: '73', sector: 'Tecnología' })
const VALE = especie({ ticker: 'VALE', pais: 'BR', sector_codigo: '10', sector: 'Minería' })

describe('autoocultado con menos de dos opciones', () => {
  it('no dibuja el select de un eje que ofrece un solo valor: no hay nada que elegir', () => {
    montar([APPLE, especie({ ticker: 'MSFT', pais: 'US', sector_codigo: '73', sector: 'Tecnología' })])

    expect(screen.queryByRole('combobox', { name: 'País' })).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: 'Sector' })).not.toBeInTheDocument()
  })

  it('dibuja el select cuando hay dos o más opciones, con el conteo en cada una', () => {
    montar([APPLE, VALE])

    const pais = screen.getByRole('combobox', { name: 'País' })
    const opciones = within(pais)
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect(opciones).toEqual(['Todos (2)', 'BR (1)', 'US (1)'])
  })

  it('el valor elegido sale de lo que el facetado confirmó, no del filtro crudo', () => {
    montar([APPLE, VALE], { pais: 'BR' })

    const pais = screen.getByRole('combobox', { name: 'País' }) as HTMLSelectElement
    expect(pais.value).toBe('BR')
  })

  it('elegir una opción escribe la dimensión, y volver a "Todos" la limpia', async () => {
    const onCambio = vi.fn()
    montar([APPLE, VALE], {}, onCambio)

    const pais = screen.getByRole('combobox', { name: 'País' })
    await userEvent.selectOptions(pais, 'BR')
    expect(onCambio).toHaveBeenCalledWith(expect.objectContaining({ pais: 'BR' }))
  })
})

describe('las etiquetas de sector muestran la traducción curada o el código, nunca explotan', () => {
  it('con la etiqueta ES cargada, la opción la muestra en vez del código', () => {
    montar([APPLE, VALE])

    const sector = screen.getByRole('combobox', { name: 'Sector' })
    expect(within(sector).getByText('Tecnología (1)')).toBeInTheDocument()
  })

  it('sin curado, la opción muestra el código con un title que declara el hueco', () => {
    const sinCurar = especie({ ticker: 'B', sector_codigo: '10', sector: null })
    montar([APPLE, sinCurar])

    const sector = screen.getByRole('combobox', { name: 'Sector' })
    const opcion = within(sector).getByText('10 (1)')
    expect(opcion).toHaveAttribute('title', 'SIC major group 10 — sin traducción cargada')
  })
})

describe('el buscador filtra y sugiere presets', () => {
  it('escribir en el buscador escribe la búsqueda', async () => {
    const onCambio = vi.fn()
    montar([APPLE, VALE], {}, onCambio)

    const buscador = screen.getByRole('textbox', { name: 'Buscar en renta variable' })
    await userEvent.type(buscador, 'o')
    expect(onCambio).toHaveBeenCalledWith(expect.objectContaining({ busqueda: 'o' }))
  })

  it('un texto que matchea un preset ofrece la sugerencia', () => {
    montar([APPLE, VALE], { busqueda: 'oro' })

    expect(screen.getByText('¿Buscabas?')).toBeInTheDocument()
    expect(
      within(screen.getByRole('group', { name: 'Sugerencias de temáticas para la búsqueda' })).getByRole(
        'button',
        { name: 'Metales preciosos' },
      ),
    ).toBeInTheDocument()
  })

  it('elegir la sugerencia activa el preset y limpia la búsqueda', async () => {
    const onCambio = vi.fn()
    montar([APPLE, VALE], { busqueda: 'oro' }, onCambio)

    const sugerencia = within(
      screen.getByRole('group', { name: 'Sugerencias de temáticas para la búsqueda' }),
    ).getByRole('button', { name: 'Metales preciosos' })
    await userEvent.click(sugerencia)
    expect(onCambio).toHaveBeenCalledWith(
      expect.objectContaining({ presetId: 'metales-preciosos', busqueda: '' }),
    )
  })

  it('sin match, no hay línea de sugerencias', () => {
    montar([APPLE, VALE], { busqueda: 'xyzxyz' })
    expect(screen.queryByText('¿Buscabas?')).not.toBeInTheDocument()
  })

  it('el preset ya activo no se sugiere de nuevo', () => {
    montar([APPLE, VALE], { busqueda: 'oro', presetId: 'metales-preciosos' })
    expect(screen.queryByText('¿Buscabas?')).not.toBeInTheDocument()
  })
})

describe('lo que el facetado apagó se declara en pantalla', () => {
  it('nombra la dimensión y el valor que quedaron sin respaldo', () => {
    // El sector 73 (Tecnología) es de Estados Unidos: pedirlo junto a Brasil no deja nada en pie.
    montar([APPLE, VALE], { pais: 'BR', sector: '73' })

    expect(screen.getByText(/no se aplica/)).toHaveTextContent('Sector «Tecnología»')
  })
})

describe('los presets llevan su definición encima', () => {
  it('muestra cada preset con su nota entera como tooltip', () => {
    montar([APPLE, VALE])

    for (const preset of PRESETS_RV) {
      expect(screen.getByRole('button', { name: preset.etiqueta })).toHaveAttribute(
        'title',
        preset.nota,
      )
    }
  })

  it('la nota de metales preciosos dice qué deja afuera, no sólo qué trae', () => {
    montar([APPLE, VALE])

    const metales = screen.getByRole('button', { name: 'Metales preciosos' })
    const nota = metales.getAttribute('title') ?? ''
    expect(nota).toContain('Deja afuera')
    expect(nota).toContain('Hecla')
  })

  it('el preset activo se marca y el segundo clic lo saca', async () => {
    const onCambio = vi.fn()
    montar([APPLE, VALE], { presetId: 'cripto' }, onCambio)

    const cripto = screen.getByRole('button', { name: 'Cripto' })
    expect(cripto).toHaveAttribute('aria-pressed', 'true')

    await userEvent.click(cripto)
    expect(onCambio).toHaveBeenCalledWith(expect.objectContaining({ presetId: null }))
  })
})
