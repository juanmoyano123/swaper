/**
 * El motor de la composición de renta variable — F-078, Fase 4. Sin red, sin store, sin React:
 * mismo criterio que `composicion.test.ts`, que cubre el equivalente de renta fija.
 *
 * Lo que estos tests defienden no es la aritmética —sumar y dividir no se rompe— sino las tres
 * decisiones de dominio: que el peso sea plata y no cantidad de papeles, que lo faltante sea un
 * tramo y nunca un reparto, y que las dos geografías (la curada y la que declara el nombre de un
 * fondo) no se mapeen una a la otra.
 */

import { describe, expect, it } from 'vitest'

import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import {
  composicionRvPor,
  cuantasSeMidieron,
  leyendaDelMontoRv,
  tituloDelEje,
} from '../lib/composicionRentaVariable'
import type { PosicionRvResuelta } from '../lib/resolverRentaVariable'

function especie(extra: Partial<EspecieRentaVariable> = {}): EspecieRentaVariable {
  const ticker = extra.ticker ?? 'AAPL'
  return {
    ticker,
    clase_activo: 'cedear',
    precio: 50,
    moneda_cotizacion: 'USD',
    cierre_anterior: 49,
    variacion: null,
    volumen: null,
    volumen_usd: null,
    px_bid: null,
    px_ask: null,
    operaciones: null,
    fuente: null,
    emision: ticker,
    sufijo_liquidacion: null,
    hermanas: [],
    no_identificado: false,
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    sic_codigo: null,
    sic_titulo: null,
    sic_oficina: null,
    division_cadena: null,
    sector_codigo: null,
    sector: null,
    sector_titulo: null,
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
    ...extra,
  }
}

/** Una posición ya resuelta a plata. `invertidoUsd` es lo único que la composición mira: el peso
 *  pedido no participa, a propósito. */
function posicion(ticker: string, invertidoUsd: number | null): PosicionRvResuelta {
  return {
    ticker,
    peso: 50,
    cantidad: invertidoUsd === null ? null : 1,
    invertido: invertidoUsd,
    invertidoUsd,
    pesoReal: null,
  }
}

function universo(...especies: EspecieRentaVariable[]): Map<string, EspecieRentaVariable> {
  return new Map(especies.map((e) => [e.ticker, e]))
}

describe('el peso es plata, no cantidad de papeles', () => {
  it('una posición de 9.000 y otra de 1.000 dan 90% y 10%, aunque sean una posición cada una', () => {
    const tramos = composicionRvPor(
      [posicion('AAPL', 9_000), posicion('VALE', 1_000)],
      universo(
        especie({ ticker: 'AAPL', sector_codigo: '73', sector: 'Servicios de software' }),
        especie({ ticker: 'VALE', sector_codigo: '10', sector: 'Minería metálica' }),
      ),
      'sector',
    )

    expect(tramos).toEqual([
      { nombre: 'Servicios de software', peso: 90, sinDato: undefined },
      { nombre: 'Minería metálica', peso: 10, sinDato: undefined },
    ])
  })

  it('dos posiciones del mismo sector se suman en un solo tramo', () => {
    const tramos = composicionRvPor(
      [posicion('AAPL', 3_000), posicion('MSFT', 1_000)],
      universo(
        especie({ ticker: 'AAPL', sector_codigo: '73', sector: 'Servicios de software' }),
        especie({ ticker: 'MSFT', sector_codigo: '73', sector: 'Servicios de software' }),
      ),
      'sector',
    )

    expect(tramos).toEqual([{ nombre: 'Servicios de software', peso: 100, sinDato: undefined }])
  })

  it('sin etiqueta ES curada, el tramo se nombra con el código crudo', () => {
    const tramos = composicionRvPor(
      [posicion('XYZ', 1_000)],
      universo(especie({ ticker: 'XYZ', sector_codigo: '99', sector: null })),
      'sector',
    )

    expect(tramos).toEqual([{ nombre: '99', peso: 100, sinDato: undefined }])
  })

  it('una posición que no se pudo valuar no aporta monto ni tramo: queda fuera del reparto', () => {
    // PAMP en pesos sin tipo de cambio, o una especie en `EXT`, que no se interpreta (regla 11).
    const posiciones = [posicion('AAPL', 1_000), posicion('PAMP', null)]
    const porTicker = universo(
      especie({ ticker: 'AAPL', sector_codigo: '73', sector: 'Servicios de software' }),
      especie({ ticker: 'PAMP', sector_codigo: '49', sector: 'Electricidad, gas y sanitarios' }),
    )

    expect(composicionRvPor(posiciones, porTicker, 'sector')).toEqual([
      { nombre: 'Servicios de software', peso: 100, sinDato: undefined },
    ])
    // Y se cuenta, para que la leyenda lo declare en vez de dejarlo pasar en silencio.
    expect(cuantasSeMidieron(posiciones, porTicker)).toBe(1)
  })

  it('sin ninguna posición valuable no devuelve tramos en cero: devuelve nada que repartir', () => {
    expect(
      composicionRvPor([posicion('AAPL', null)], universo(especie({ ticker: 'AAPL' })), 'sector'),
    ).toEqual([])
  })

  it('una posición que no está en el universo se excluye, igual que en renta fija', () => {
    expect(
      composicionRvPor([posicion('DESCONOCIDA', 1_000)], universo(especie()), 'moneda'),
    ).toEqual([])
  })
})

describe('lo que no tiene el dato es un tramo propio, nunca repartido', () => {
  it.each([
    ['sector' as const, 'sector no informado'],
    ['pais' as const, 'país no informado'],
    ['region' as const, 'región no informada'],
    ['moneda' as const, 'moneda no informada'],
    ['mercado' as const, 'mercado no informado'],
  ])('en el eje %s el faltante se llama "%s" y pesa lo suyo', (eje, nombreEsperado) => {
    const tramos = composicionRvPor(
      [posicion('AAPL', 750), posicion('SINDATO', 250)],
      universo(
        especie({
          ticker: 'AAPL',
          sector_codigo: '73',
          sector: 'Servicios de software',
          pais: 'US',
          region: 'América del Norte',
          moneda_cotizacion: 'USD',
          mercado_origen: 'NASDAQ',
        }),
        // Todo en `null`: el papel sin clasificar, que es el 100% del universo en el eje de país
        // hasta que corra la siembra del curado.
        especie({ ticker: 'SINDATO', moneda_cotizacion: null }),
      ),
      eje,
    )

    const faltante = tramos.find((t) => t.sinDato === true)
    expect(faltante).toEqual({ nombre: nombreEsperado, peso: 25, sinDato: true })
    // Los tramos suman 100: el faltante está adentro del reparto como un tramo más, no afuera.
    expect(tramos.reduce((total, t) => total + t.peso, 0)).toBeCloseTo(100)
  })

  it('el faltante nunca se suma a una categoría conocida', () => {
    const tramos = composicionRvPor(
      [posicion('AAPL', 500), posicion('SINDATO', 500)],
      universo(
        especie({ ticker: 'AAPL', pais: 'US' }),
        especie({ ticker: 'SINDATO', pais: null }),
      ),
      'pais',
    )

    expect(tramos.find((t) => t.nombre === 'US')?.peso).toBe(50)
    expect(tramos).toHaveLength(2)
  })
})

describe('el eje geográfico es dual: región curada y región de ETF no se mapean', () => {
  it('la subregión M49 de una empresa y la geografía que declara un fondo son dos tramos', () => {
    const tramos = composicionRvPor(
      [posicion('VALE', 500), posicion('EWZ', 500)],
      universo(
        // Empresa brasileña: la región sale del país curado, por el estándar M49.
        especie({ ticker: 'VALE', pais: 'BR', region: 'América Latina y el Caribe' }),
        // ETF de Brasil: la región la declara su propio nombre, y llega tal cual está escrita.
        especie({ ticker: 'EWZ', region_etf: 'Brazil', estrategia_etf: 'geografico' }),
      ),
      'region',
    )

    // Dos tramos y no uno: unificarlos exigiría afirmar que "Brazil" es "América Latina y el
    // Caribe", equivalencia que nadie publicó (regla 11).
    expect(tramos.map((t) => t.nombre).sort()).toEqual([
      'América Latina y el Caribe',
      'Brazil (fondo)',
    ])
    expect(tramos.every((t) => t.sinDato === undefined)).toBe(true)
  })

  it('el sufijo distingue el vocabulario del fondo sin traducirlo: el valor de la fuente queda entero', () => {
    // `EAFE` (Europe, Australasia and Far East) directamente no tiene una subregión M49 que le
    // corresponda: no hay a qué mapearlo aunque se quisiera.
    const tramos = composicionRvPor(
      [posicion('EFA', 1_000)],
      universo(especie({ ticker: 'EFA', region_etf: 'EAFE' })),
      'region',
    )

    expect(tramos).toEqual([{ nombre: 'EAFE (fondo)', peso: 100, sinDato: undefined }])
  })

  it('un papel sin país curado y sin fondo cae en "región no informada", no en la del ETF de al lado', () => {
    const tramos = composicionRvPor(
      [posicion('EWZ', 500), posicion('PBR', 500)],
      universo(
        especie({ ticker: 'EWZ', region_etf: 'Brazil' }),
        // Petrobras es brasileña, pero el curado todavía no llegó a esa fila: no se completa por
        // analogía con el ETF de Brasil que está al lado en la cartera (regla 1).
        especie({ ticker: 'PBR' }),
      ),
      'region',
    )

    expect(tramos).toEqual([
      { nombre: 'Brazil (fondo)', peso: 50, sinDato: undefined },
      { nombre: 'región no informada', peso: 50, sinDato: true },
    ])
  })
})

describe('cada eje lee la fuente tal como la fuente la escribe', () => {
  it('el país es el código ISO, sin traducir a nombre de país', () => {
    const tramos = composicionRvPor(
      [posicion('AAPL', 1_000)],
      universo(especie({ ticker: 'AAPL', pais: 'US' })),
      'pais',
    )
    expect(tramos[0].nombre).toBe('US')
  })

  it('EXT se muestra como EXT: es un código propietario que BYMA no documenta', () => {
    const tramos = composicionRvPor(
      [posicion('AAPLC', 400), posicion('AAPL', 600)],
      universo(
        especie({ ticker: 'AAPLC', moneda_cotizacion: 'EXT' }),
        especie({ ticker: 'AAPL', moneda_cotizacion: 'ARS' }),
      ),
      'moneda',
    )

    expect(tramos).toEqual([
      { nombre: 'ARS', peso: 60, sinDato: undefined },
      // Ni "cable", ni "dólar", ni "sin dato": `EXT` es un valor que la fuente declara, sólo que
      // no dice qué significa. Se muestra, no se interpreta ni se esconde.
      { nombre: 'EXT', peso: 40, sinDato: undefined },
    ])
  })

  it('el mercado agrupa sin distinguir mayúsculas: la fuente escribe el mismo mercado de dos maneras', () => {
    const tramos = composicionRvPor(
      [posicion('A', 300), posicion('B', 300), posicion('C', 400)],
      universo(
        especie({ ticker: 'A', mercado_origen: 'NYSE Arca' }),
        especie({ ticker: 'B', mercado_origen: 'NYSE ARCA' }),
        especie({ ticker: 'C', mercado_origen: 'NASDAQ' }),
      ),
      'mercado',
    )

    // Un solo tramo con el 60%: partirlo en dos mostraría una diversificación de mercado que no
    // existe. La grafía que se muestra es la primera en orden alfabético — determinística, sin
    // depender del orden en que llegaron las posiciones.
    expect(tramos).toEqual([
      { nombre: 'NYSE ARCA', peso: 60, sinDato: undefined },
      { nombre: 'NASDAQ', peso: 40, sinDato: undefined },
    ])
  })

  it('cada eje nombra su fuente en el título', () => {
    expect(tituloDelEje('pais')).toContain('ISO 3166-1')
    expect(tituloDelEje('sector')).toContain('SIC')
  })
})

describe('país y región desde F-079 unifican la empresa con el ETF mono-país curado', () => {
  it('el país de una empresa y el `etf_pais` de un fondo mono-país se agrupan bajo el mismo código', () => {
    const tramos = composicionRvPor(
      [posicion('VALE', 500), posicion('EWZS', 500)],
      universo(
        especie({ ticker: 'VALE', pais: 'BR' }),
        // Un ETF mono-país curado (F-079, D3): no tiene `pais` (no es una empresa), tiene `etf_pais`.
        especie({ ticker: 'EWZS', pais: null, etf_pais: 'BR', etf_indice: 'algo' }),
      ),
      'pais',
    )

    expect(tramos).toEqual([{ nombre: 'BR', peso: 100, sinDato: undefined }])
  })

  it('la región de un ETF mono-país (`etf_region`) se agrupa con la de una empresa: mismo M49', () => {
    const tramos = composicionRvPor(
      [posicion('VALE', 500), posicion('EWZS', 500)],
      universo(
        especie({ ticker: 'VALE', region: 'América Latina y el Caribe' }),
        especie({ ticker: 'EWZS', region: null, etf_region: 'América Latina y el Caribe' }),
      ),
      'region',
    )

    expect(tramos).toEqual([{ nombre: 'América Latina y el Caribe', peso: 100, sinDato: undefined }])
  })

  it('el alcance curado del índice (`etf_alcance`) es su propio tramo, distinto de la M49', () => {
    const tramos = composicionRvPor(
      [posicion('ACWI', 1_000)],
      universo(
        especie({ ticker: 'ACWI', region: null, etf_region: null, etf_alcance: 'Mercados globales' }),
      ),
      'region',
    )

    expect(tramos).toEqual([{ nombre: 'Mercados globales', peso: 100, sinDato: undefined }])
  })
})

describe('los tramos vienen ordenados por peso, y el empate no salta entre renders', () => {
  it('de mayor a menor', () => {
    const tramos = composicionRvPor(
      [posicion('A', 100), posicion('B', 700), posicion('C', 200)],
      universo(
        especie({ ticker: 'A', pais: 'AR' }),
        especie({ ticker: 'B', pais: 'US' }),
        especie({ ticker: 'C', pais: 'BR' }),
      ),
      'pais',
    )
    expect(tramos.map((t) => t.nombre)).toEqual(['US', 'BR', 'AR'])
  })

  it('con pesos iguales desempata alfabéticamente, no por orden de llegada', () => {
    // Una cartera equiponderada empata siempre, y `DistribucionBarras` colorea por índice: sin un
    // desempate estable el color de cada país saltaría entre renders.
    const tramos = composicionRvPor(
      [posicion('Z', 500), posicion('A', 500)],
      universo(especie({ ticker: 'Z', pais: 'ZA' }), especie({ ticker: 'A', pais: 'AR' })),
      'pais',
    )
    expect(tramos.map((t) => t.nombre)).toEqual(['AR', 'ZA'])
  })
})

describe('leyendaDelMontoRv declara sobre qué se midió', () => {
  it('todas medidas: dice que es plata invertida y no ponderación pedida', () => {
    expect(leyendaDelMontoRv(3, 3)).toMatch(/efectivamente invertido en las 3 posiciones/)
    expect(leyendaDelMontoRv(3, 3)).toMatch(/no sobre la ponderación pedida/)
  })

  it('ninguna medida: dice que no hay monto que repartir, no que la cartera esté en cero', () => {
    expect(leyendaDelMontoRv(0, 2)).toMatch(/Ninguna de las 2 posiciones/)
    expect(leyendaDelMontoRv(0, 2)).toMatch(/no hay monto que repartir/)
  })

  it('parcial: nombra cuántas quedaron afuera y aclara que no van en cero', () => {
    expect(leyendaDelMontoRv(2, 5)).toMatch(/en 2 de 5 posiciones/)
    expect(leyendaDelMontoRv(2, 5)).toMatch(/las otras 3/)
    expect(leyendaDelMontoRv(2, 5)).toMatch(/no en cero/)
  })
})
