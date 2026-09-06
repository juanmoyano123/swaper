/**
 * Lógica pura de `../lib/filtrosRentaVariable.ts` — el mission control de diversificación de
 * CEDEARs (F-078, fase 2; dimensiones y buscador reescritos por F-079, fase 5).
 *
 * Cubre lo que este módulo decide y no hereda del motor genérico (que tiene su propio test en
 * `lib/__tests__/facetado.test.ts`): los centinelas de "sin dato", la jerarquía sector→rubro
 * específico, la unificación de país, la cascada de región, el colapso de caja del mercado sin
 * tocar los escalones de NASDAQ, el buscador de texto y sus sugerencias de preset, y el preset de
 * metales preciosos visto desde acá.
 */

import { describe, expect, it } from 'vitest'

import type { EspecieRentaVariable } from '@/lib/rentaVariable'

import {
  ESTRATEGIA_SIN_DATO,
  FILTROS_RV_VACIOS,
  MERCADO_SIN_DATO,
  PAIS_SIN_DATO,
  REGION_SIN_DATO,
  RUBRO_ESPECIFICO_SIN_DATO,
  SECTOR_SIN_DATO,
  coincideBusquedaRv,
  etiquetaDeValorRv,
  etiquetasDeRubroEspecifico,
  etiquetasDeSector,
  facetarRentaVariable,
  filtrosAlCambiarDeMoneda,
  foldTexto,
  formasCanonicasDeMercado,
  pasaFiltrosRv,
  presetsQueCoinciden,
  tituloOpcionRv,
  type EtiquetasRv,
  type FiltrosRentaVariable,
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
    nombre_largo: null,
    perfil_fuente: null,
    perfil_capturado_en: null,
    ...extra,
  }
}

function filtros(extra: Partial<FiltrosRentaVariable> = {}): FiltrosRentaVariable {
  return { ...FILTROS_RV_VACIOS, ...extra }
}

/** Los valores ofrecidos por una dimensión, sin el conteo, para comparar contra un array. */
function valoresDe(
  resultado: ReturnType<typeof facetarRentaVariable>,
  dimension: Parameters<typeof etiquetaDeValorRv>[0],
): string[] {
  return resultado.opciones.porDimension[dimension].map((o) => o.valor)
}

describe('facetarRentaVariable — cascada y leave-one-out', () => {
  const APPLE = especie({
    ticker: 'AAPL',
    pais: 'US',
    region: 'América del Norte',
    sector_codigo: '73',
    sic_codigo: '7372',
    mercado_origen: 'NASDAQ',
  })
  const VALE = especie({
    ticker: 'VALE',
    pais: 'BR',
    region: 'América Latina y el Caribe',
    sector_codigo: '10',
    sic_codigo: '1000',
    mercado_origen: 'NYSE',
  })
  const PBR = especie({
    ticker: 'PBR',
    pais: 'BR',
    region: 'América Latina y el Caribe',
    sector_codigo: '10',
    sic_codigo: '1311',
    mercado_origen: 'NYSE',
  })
  const UNIVERSO = [APPLE, VALE, PBR]

  it('elegir un sector acota las opciones de las otras dimensiones', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros({ sector: '73' }), 'ARS')
    expect(valoresDe(resultado, 'pais')).toEqual(['US'])
    expect(valoresDe(resultado, 'mercado')).toEqual(['NASDAQ'])
    expect(resultado.efectivos.sector).toBe('73')
  })

  it('elegir un sector acota los códigos SIC de rubro específico que quedan como opción', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros({ sector: '10' }), 'ARS')
    expect(valoresDe(resultado, 'rubroEspecifico').sort()).toEqual(['1000', '1311'])
  })

  it('la dimensión elegida no se acota a sí misma: conserva todas sus opciones', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros({ sector: '73' }), 'ARS')
    expect(valoresDe(resultado, 'sector').sort()).toEqual(['10', '73'])
  })

  it('los conteos son de especies bajo el resto de los filtros, con la propia dimensión neutralizada', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros(), 'ARS')
    expect(resultado.opciones.porDimension.pais).toEqual([
      { valor: 'BR', especies: 2 },
      { valor: 'US', especies: 1 },
    ])
    expect(resultado.opciones.totalPorDimension.pais).toBe(3)
  })

  it('una selección sin respaldo bajo el resto queda apagada y declarada, no aplicada en fantasma', () => {
    const resultado = facetarRentaVariable(
      UNIVERSO,
      // El sector 73 es de Estados Unidos: pedirlo junto a Brasil no deja nada en pie.
      filtros({ pais: 'BR', sector: '73' }),
      'ARS',
    )
    expect(resultado.efectivos.pais).toBe('BR')
    expect(resultado.efectivos.sector).toBeNull()
    expect(resultado.apagadas).toEqual([{ dimension: 'sector', valor: '73' }])
  })

  it('gana la dimensión más general: el orden del array es el orden de validación', () => {
    // País se valida antes que sector, así que ante una combinación imposible sobrevive país.
    const resultado = facetarRentaVariable(UNIVERSO, filtros({ pais: 'US', sector: '10' }), 'ARS')
    expect(resultado.efectivos.pais).toBe('US')
    expect(resultado.efectivos.sector).toBeNull()
  })

  it('la moneda es filtro base y acota los chips sin ser faceta', () => {
    const enDolares = especie({ ticker: 'AAPLD', moneda_cotizacion: 'USD', pais: 'US', region: 'América del Norte' })
    const resultado = facetarRentaVariable([...UNIVERSO, enDolares], filtros(), 'USD')
    expect(valoresDe(resultado, 'pais')).toEqual(['US'])
    expect(resultado.opciones.totalPorDimension.pais).toBe(1)
  })
})

describe('centinelas de sin dato', () => {
  const CON_SECTOR = especie({ ticker: 'AAPL', sector_codigo: '73', sic_codigo: '7372' })
  const SIN_SECTOR = especie({ ticker: 'GLD' })
  const UNIVERSO = [CON_SECTOR, SIN_SECTOR]

  it('cada dimensión ofrece su centinela como una opción más', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros(), 'ARS')
    expect(valoresDe(resultado, 'sector')).toContain(SECTOR_SIN_DATO)
    expect(valoresDe(resultado, 'rubroEspecifico')).toContain(RUBRO_ESPECIFICO_SIN_DATO)
    expect(valoresDe(resultado, 'pais')).toEqual([PAIS_SIN_DATO])
    expect(valoresDe(resultado, 'region')).toEqual([REGION_SIN_DATO])
    expect(valoresDe(resultado, 'mercado')).toEqual([MERCADO_SIN_DATO])
    expect(valoresDe(resultado, 'estrategiaEtf')).toEqual([ESTRATEGIA_SIN_DATO])
  })

  it('el centinela va último, después de las opciones con dato', () => {
    const resultado = facetarRentaVariable(UNIVERSO, filtros(), 'ARS')
    expect(valoresDe(resultado, 'sector')).toEqual(['73', SECTOR_SIN_DATO])
  })

  it('filtrar hacia el hueco trae exactamente los papeles a los que les falta el dato', () => {
    expect(pasaFiltrosRv(SIN_SECTOR, filtros({ sector: SECTOR_SIN_DATO }), 'ARS')).toBe(true)
    expect(pasaFiltrosRv(CON_SECTOR, filtros({ sector: SECTOR_SIN_DATO }), 'ARS')).toBe(false)
  })

  it('un dato faltante nunca cumple un filtro activo de esa dimensión', () => {
    expect(pasaFiltrosRv(SIN_SECTOR, filtros({ sector: '73' }), 'ARS')).toBe(false)
    expect(pasaFiltrosRv(SIN_SECTOR, filtros({ pais: 'US' }), 'ARS')).toBe(false)
    expect(pasaFiltrosRv(SIN_SECTOR, filtros({ mercado: 'NYSE' }), 'ARS')).toBe(false)
    // Sin el filtro, el papel sin dato se sigue mostrando: el faltante se declara, no se esconde.
    expect(pasaFiltrosRv(SIN_SECTOR, filtros(), 'ARS')).toBe(true)
  })

  it('el centinela se lee en pantalla como el hueco que es, no como "otros"', () => {
    expect(etiquetaDeValorRv('pais', PAIS_SIN_DATO)).toBe('(sin país)')
    expect(etiquetaDeValorRv('sector', SECTOR_SIN_DATO)).toBe('(sin sector)')
    expect(etiquetaDeValorRv('rubroEspecifico', RUBRO_ESPECIFICO_SIN_DATO)).toBe('(sin rubro específico)')
    expect(etiquetaDeValorRv('estrategiaEtf', ESTRATEGIA_SIN_DATO)).toBe('(sin estrategia)')
    // Un valor real de la fuente no se traduce (regla 11); una clave propia nuestra sí se lee.
    expect(etiquetaDeValorRv('pais', 'US')).toBe('US')
    expect(etiquetaDeValorRv('region', 'Brazil')).toBe('Brazil')
    expect(etiquetaDeValorRv('estrategiaEtf', 'activo_fisico')).toBe('activo físico')
  })
})

function etiquetasVacias(): EtiquetasRv {
  return { sector: new Map(), rubroEspecifico: new Map(), sicTitulos: new Map(), sectorTitulos: new Map() }
}

describe('sector y rubro específico: código en la faceta, etiqueta en pantalla (regla 11)', () => {
  it('sin ES ni título OSHA (código en un hueco del Manual), sector se muestra por su propio código', () => {
    // 18 es uno de los huecos que el SIC Manual de OSHA no define (ver `app/externos/sic.py`).
    const enHueco = especie({ ticker: 'B', sector_codigo: '18', sector: null, sector_titulo: null })
    const { etiquetas, sectorTitulos } = etiquetasDeSector([enHueco])
    expect(etiquetaDeValorRv('sector', '18', { ...etiquetasVacias(), sector: etiquetas, sectorTitulos })).toBe('18')
  })

  it('sin ES cargado pero con título OSHA, sector se muestra por el nombre oficial en inglés', () => {
    const barrick = especie({ ticker: 'B', sector_codigo: '10', sector: null, sector_titulo: 'Metal Mining' })
    const { etiquetas, sectorTitulos } = etiquetasDeSector([barrick])
    expect(etiquetaDeValorRv('sector', '10', { ...etiquetasVacias(), sector: etiquetas, sectorTitulos })).toBe(
      'Metal Mining',
    )
  })

  it('con la etiqueta ES cargada en alguna especie del universo, se muestra esa etiqueta por sobre el título OSHA', () => {
    const conEtiqueta = especie({ ticker: 'B', sector_codigo: '10', sector: 'Minería metálica', sector_titulo: 'Metal Mining' })
    const sinEtiqueta = especie({ ticker: 'B2', sector_codigo: '10', sector: null, sector_titulo: 'Metal Mining' })
    const { etiquetas, sectorTitulos } = etiquetasDeSector([sinEtiqueta, conEtiqueta])
    expect(etiquetaDeValorRv('sector', '10', { ...etiquetasVacias(), sector: etiquetas, sectorTitulos })).toBe(
      'Minería metálica',
    )
  })

  it('rubro específico sin ES cargado cae al título en inglés de la SEC, no explota', () => {
    const oro = especie({ ticker: 'B', sic_codigo: '1040', rubro_especifico: null, sic_titulo: 'Gold and Silver Ores' })
    const { etiquetas } = etiquetasDeRubroEspecifico([oro])
    expect(etiquetaDeValorRv('rubroEspecifico', '1040', { ...etiquetasVacias(), rubroEspecifico: etiquetas })).toBe(
      'Gold and Silver Ores',
    )
  })

  it('el título de la opción sin ES ni título OSHA nombra el hueco, no lo esconde', () => {
    expect(tituloOpcionRv('sector', '18', etiquetasVacias())).toBe('SIC major group 18 — sin traducción cargada')
  })

  it('el título de la opción de sector nombra la fuente OSHA cuando no hay ES pero sí título', () => {
    const barrick = especie({ ticker: 'B', sector_codigo: '73', sector: null, sector_titulo: 'Business Services' })
    const { sectorTitulos } = etiquetasDeSector([barrick])
    expect(tituloOpcionRv('sector', '73', { ...etiquetasVacias(), sectorTitulos })).toBe(
      'SIC major group 73 — Business Services (OSHA)',
    )
  })

  it('el título de rubro específico siempre nombra la fuente SEC, tenga o no etiqueta ES', () => {
    const oro = especie({ ticker: 'B', sic_codigo: '1040', rubro_especifico: 'Oro y plata', sic_titulo: 'Gold and Silver Ores' })
    const { sicTitulos } = etiquetasDeRubroEspecifico([oro])
    expect(tituloOpcionRv('rubroEspecifico', '1040', { ...etiquetasVacias(), sicTitulos })).toBe(
      'SIC 1040 — Gold and Silver Ores (SEC)',
    )
  })
})

describe('mercado: caja sí, escalones de NASDAQ no', () => {
  // Medido el 28/08/2026 sobre `perfil_renta_variable`: la fuente escribe "NYSE Arca" en 81
  // papeles y "NYSE ARCA" en 12.
  const ARCA_FRECUENTE = [
    especie({ ticker: 'A1', mercado_origen: 'NYSE Arca' }),
    especie({ ticker: 'A2', mercado_origen: 'NYSE Arca' }),
    especie({ ticker: 'A3', mercado_origen: 'NYSE ARCA' }),
  ]

  it('colapsa las variantes de caja y muestra la forma más frecuente', () => {
    const resultado = facetarRentaVariable(ARCA_FRECUENTE, filtros(), 'ARS')
    expect(resultado.opciones.porDimension.mercado).toEqual([
      { valor: 'NYSE Arca', especies: 3 },
    ])
  })

  it('la forma canónica es la de la fuente, no una capitalización nuestra', () => {
    const canonicas = formasCanonicasDeMercado([
      { mercado_origen: 'NYSE ARCA' },
      { mercado_origen: 'NYSE ARCA' },
      { mercado_origen: 'NYSE Arca' },
    ])
    expect(canonicas.get('nyse arca')).toBe('NYSE ARCA')
  })

  it('filtrar por una variante trae también la otra: es el mismo mercado escrito distinto', () => {
    const filtro = filtros({ mercado: 'NYSE Arca' })
    expect(pasaFiltrosRv(ARCA_FRECUENTE[2], filtro, 'ARS')).toBe(true)
    expect(pasaFiltrosRv(ARCA_FRECUENTE[0], filtros({ mercado: 'NYSE ARCA' }), 'ARS')).toBe(true)
  })

  it('no colapsa los escalones de NASDAQ: la fuente los distingue y son mercados distintos', () => {
    const tiers = [
      especie({ ticker: 'N1', mercado_origen: 'NASDAQ' }),
      especie({ ticker: 'N2', mercado_origen: 'NASDAQ GS' }),
      especie({ ticker: 'N3', mercado_origen: 'NASDAQ GM' }),
      especie({ ticker: 'N4', mercado_origen: 'NASDAQ CM' }),
    ]
    const resultado = facetarRentaVariable(tiers, filtros(), 'ARS')
    expect(valoresDe(resultado, 'mercado').sort()).toEqual([
      'NASDAQ',
      'NASDAQ CM',
      'NASDAQ GM',
      'NASDAQ GS',
    ])
    expect(pasaFiltrosRv(tiers[1], filtros({ mercado: 'NASDAQ' }), 'ARS')).toBe(false)
  })
})

describe('país: pais ?? etf_pais, dos curados del mismo vocabulario', () => {
  it('una empresa aporta su país curado', () => {
    const petrobras = especie({ ticker: 'PBR', pais: 'BR' })
    expect(pasaFiltrosRv(petrobras, filtros({ pais: 'BR' }), 'ARS')).toBe(true)
  })

  it('un ETF mono-país aporta etf_pais cuando no hay país de empresa', () => {
    const ewz = especie({ ticker: 'EWZ', pais: null, etf_pais: 'BR' })
    expect(pasaFiltrosRv(ewz, filtros({ pais: 'BR' }), 'ARS')).toBe(true)
  })

  it('el país de empresa gana si por algún motivo hubiera los dos', () => {
    const raro = especie({ ticker: 'X', pais: 'US', etf_pais: 'BR' })
    expect(pasaFiltrosRv(raro, filtros({ pais: 'US' }), 'ARS')).toBe(true)
    expect(pasaFiltrosRv(raro, filtros({ pais: 'BR' }), 'ARS')).toBe(false)
  })

  it('sin ninguno de los dos, cae en el centinela', () => {
    const gld = especie({ ticker: 'GLD' })
    expect(pasaFiltrosRv(gld, filtros({ pais: PAIS_SIN_DATO }), 'ARS')).toBe(true)
  })
})

describe('región: cascada de cuatro niveles, ya no dual', () => {
  it('nivel 1 — region curada de la empresa gana sobre todo lo demás', () => {
    const especieRara = especie({
      ticker: 'X',
      region: 'América Latina y el Caribe',
      etf_region: 'América del Norte',
      etf_alcance: 'Mercados emergentes',
      region_etf: 'Brazil',
    })
    expect(pasaFiltrosRv(especieRara, filtros({ region: 'América Latina y el Caribe' }), 'ARS')).toBe(true)
    expect(pasaFiltrosRv(especieRara, filtros({ region: 'Brazil' }), 'ARS')).toBe(false)
  })

  it('nivel 2 — etf_region (ETF mono-país curado) cuando no hay region de empresa', () => {
    const etfMonoPais = especie({ ticker: 'EWZ', region: null, etf_region: 'América Latina y el Caribe', etf_alcance: 'x', region_etf: 'Brazil' })
    expect(pasaFiltrosRv(etfMonoPais, filtros({ region: 'América Latina y el Caribe' }), 'ARS')).toBe(true)
  })

  it('nivel 3 — etf_alcance (ETF multi-país curado) cuando no hay región curada', () => {
    const etfMultiPais = especie({ ticker: 'EEM', region: null, etf_region: null, etf_alcance: 'Mercados emergentes', region_etf: 'Emerging' })
    expect(pasaFiltrosRv(etfMultiPais, filtros({ region: 'Mercados emergentes' }), 'ARS')).toBe(true)
  })

  it('nivel 4 — region_etf, el token crudo, sólo si nada de lo anterior está curado', () => {
    const sinCurar = especie({ ticker: 'EFA', region: null, etf_region: null, etf_alcance: null, region_etf: 'EAFE' })
    expect(pasaFiltrosRv(sinCurar, filtros({ region: 'EAFE' }), 'ARS')).toBe(true)
  })

  it('«Brazil» no arrastra a la empresa brasileña curada: mapear una a la otra sería traducir', () => {
    const petrobras = especie({ ticker: 'PBR', region: 'América Latina y el Caribe' })
    expect(pasaFiltrosRv(petrobras, filtros({ region: 'Brazil' }), 'ARS')).toBe(false)
  })
})

describe('preset de metales preciosos, visto desde el monitor', () => {
  const METALES = filtros({ presetId: 'metales-preciosos' })

  it('un ETF de activo físico sin SIC entra por la estrategia', () => {
    const gld = especie({
      ticker: 'GLD',
      nombre_largo: 'ETF SPDR GOLD TRUST',
      estrategia_etf: 'activo_fisico',
      sic_codigo: null,
    })
    expect(pasaFiltrosRv(gld, METALES, 'ARS')).toBe(true)
  })

  it('una minera con SIC 1040 y sin estrategia entra por el código: es unión, no intersección', () => {
    const barrick = especie({
      ticker: 'B',
      nombre_largo: 'BARRICK MINING CORP',
      sic_codigo: '1040',
      sic_titulo: 'Gold and Silver Ores',
      estrategia_etf: null,
    })
    expect(pasaFiltrosRv(barrick, METALES, 'ARS')).toBe(true)
  })

  it('una petrolera no entra: ni el código ni la estrategia ni el nombre nombran el metal', () => {
    const xom = especie({
      ticker: 'XOM',
      nombre_largo: 'EXXON MOBIL CORP',
      sic_codigo: '2911',
      sector_codigo: '29',
    })
    expect(pasaFiltrosRv(xom, METALES, 'ARS')).toBe(false)
  })

  it('«Goldman» no matchea «gold»: la comparación es por palabra entera', () => {
    const gs = especie({
      ticker: 'GS',
      nombre_largo: 'GOLDMAN SACHS GROUP INC',
      sic_codigo: '6199',
      sector_codigo: '61',
    })
    expect(pasaFiltrosRv(gs, METALES, 'ARS')).toBe(false)
  })

  it('el preset es filtro base: acota los chips sin poder quedar apagado', () => {
    const gld = especie({ ticker: 'GLD', nombre_largo: 'ETF SPDR GOLD TRUST', estrategia_etf: 'activo_fisico' })
    const xom = especie({ ticker: 'XOM', nombre_largo: 'EXXON MOBIL CORP', sector_codigo: '29' })
    const resultado = facetarRentaVariable([gld, xom], METALES, 'ARS')
    expect(valoresDe(resultado, 'estrategiaEtf')).toEqual(['activo_fisico'])
    expect(resultado.efectivos.presetId).toBe('metales-preciosos')
  })

  it('un preset que no existe no vacía la pantalla: no filtra nada', () => {
    const xom = especie({ ticker: 'XOM', nombre_largo: 'EXXON MOBIL CORP' })
    expect(pasaFiltrosRv(xom, filtros({ presetId: 'preset-que-no-existe' }), 'ARS')).toBe(true)
  })
})

describe('foldTexto normaliza acentos y mayúsculas', () => {
  it('quita acentos y baja a minúsculas', () => {
    expect(foldTexto('Farmacéutica')).toBe('farmaceutica')
    expect(foldTexto('MINERÍA')).toBe('mineria')
  })
})

describe('coincideBusquedaRv — el buscador de texto', () => {
  it('un texto vacío no filtra nada', () => {
    expect(coincideBusquedaRv(especie({ ticker: 'AAPL' }), '')).toBe(true)
  })

  it('matchea por ticker', () => {
    expect(coincideBusquedaRv(especie({ ticker: 'AAPL' }), 'aapl')).toBe(true)
  })

  it('matchea por nombre largo, sin distinguir acentos', () => {
    const especieFarma = especie({ ticker: 'PFE', nombre_largo: 'Pfizer Inc' })
    expect(coincideBusquedaRv(especieFarma, foldTexto('pfizer'))).toBe(true)
  })

  it('matchea por la etiqueta ES de sector o de rubro específico si la especie las trae cargadas', () => {
    const farma = especie({ ticker: 'PFE', sector: 'Farmacéuticas y salud' })
    expect(coincideBusquedaRv(farma, foldTexto('farmaceuticas'))).toBe(true)
  })

  it('matchea por el título SIC en inglés cuando no hay curado ES', () => {
    const minera = especie({ ticker: 'B', sic_titulo: 'Gold and Silver Ores', sector: null, rubro_especifico: null })
    expect(coincideBusquedaRv(minera, foldTexto('silver'))).toBe(true)
  })

  it('no matchea lo que la especie no declara', () => {
    const especieVacia = especie({ ticker: 'XOM', nombre_largo: 'EXXON MOBIL CORP' })
    expect(coincideBusquedaRv(especieVacia, foldTexto('oro'))).toBe(false)
  })
})

describe('presetsQueCoinciden — buscar "oro" encuentra el preset de metales preciosos', () => {
  it('un texto vacío no sugiere ningún preset', () => {
    expect(presetsQueCoinciden('')).toEqual([])
  })

  it('"oro" matchea metales-preciosos por palabrasEnNombre', () => {
    const ids = presetsQueCoinciden(foldTexto('oro')).map((p) => p.id)
    expect(ids).toContain('metales-preciosos')
  })

  it('la etiqueta del preset también matchea', () => {
    const ids = presetsQueCoinciden(foldTexto('cripto')).map((p) => p.id)
    expect(ids).toContain('cripto')
  })

  it('un texto sin ningún preset relacionado no sugiere nada', () => {
    expect(presetsQueCoinciden(foldTexto('xyzxyz'))).toEqual([])
  })
})

describe('el buscador es filtro base: acota la tabla y los conteos de los selects', () => {
  it('un texto que sólo matchea un papel deja sólo ése bajo el resto de los filtros', () => {
    const universo = [
      especie({ ticker: 'AAPL', nombre_largo: 'Apple Inc', pais: 'US' }),
      especie({ ticker: 'VALE', nombre_largo: 'Vale SA', pais: 'BR' }),
    ]
    const resultado = facetarRentaVariable(universo, filtros({ busqueda: 'apple' }), 'ARS')
    expect(resultado.opciones.totalPorDimension.pais).toBe(1)
    expect(pasaFiltrosRv(universo[0], filtros({ busqueda: 'apple' }), 'ARS')).toBe(true)
    expect(pasaFiltrosRv(universo[1], filtros({ busqueda: 'apple' }), 'ARS')).toBe(false)
  })
})

describe('qué sobrevive al cambio de moneda', () => {
  it('limpia las facetas: un recorte por país o sector describe otro subconjunto en otra moneda', () => {
    const quedan = filtrosAlCambiarDeMoneda(
      filtros({ pais: 'US', sector: '73', mercado: 'NASDAQ' }),
    )
    expect(quedan.pais).toBeNull()
    expect(quedan.sector).toBeNull()
    expect(quedan.mercado).toBeNull()
  })

  it('deja en pie el preset temático y la búsqueda: la intención no depende de en qué denominación liquida', () => {
    const quedan = filtrosAlCambiarDeMoneda(
      filtros({ presetId: 'metales-preciosos', pais: 'US', busqueda: 'oro' }),
    )
    expect(quedan.presetId).toBe('metales-preciosos')
    expect(quedan.busqueda).toBe('oro')
    expect(quedan.pais).toBeNull()
  })

  it('sin preset ni búsqueda no inventa ninguno', () => {
    expect(filtrosAlCambiarDeMoneda(filtros({ region: 'Brazil' }))).toEqual(FILTROS_RV_VACIOS)
  })
})
