/**
 * Lógica pura de `../lib/filtrosFci.ts` — facetado en cascada de los fondos comunes (23/08/2026).
 *
 * Espejo de `filtros.test.ts`, con los casos propios del dato de CAFCI: los códigos que no se
 * traducen, las dos grafías del "no aplica" que conviven como calificaciones distintas, y la unidad
 * de las variaciones (puntos porcentuales, no fracción).
 */

import { describe, expect, it } from 'vitest'

import {
  CALIFICACION_NO_INFORMADA,
  FILTROS_FCI_VACIOS,
  GERENTE_NO_INFORMADA,
  HORIZONTE_NO_INFORMADO,
  REGION_NO_INFORMADA,
  facetarFci,
  pasaFiltrosFci,
  type FiltrosFci,
} from '../lib/filtrosFci'
import type { FondoFci } from '@/lib/fci'

function fondo(extra: Partial<FondoFci> = {}): FondoFci {
  return {
    codigo_cafci: '1031',
    fondo: 'Gainvest Renta Variable - Clase A',
    codigo_cnv: '500',
    seccion: 'Renta Variable Peso Argentina',
    tipo_renta: 'renta_variable',
    naturaleza: 'variacion_cuotaparte',
    naturaleza_nombre: 'Variación de cuotaparte',
    moneda: 'ARS',
    region: 'Arg',
    horizonte: 'Lar',
    fecha_vcp: '2026-08-21',
    vcp: 1500.0,
    vcp_anterior: 1490.0,
    var_diaria_pct: 0.67,
    var_mes_pct: 5.2,
    var_anio_pct: 40.1,
    var_12m_pct: 55.3,
    cuotapartes: 100.0,
    cuotapartes_anterior: 99.0,
    patrimonio: 10_000_000.0,
    patrimonio_anterior: 9_900_000.0,
    market_share: 1.2,
    gerente: 'Gainvest S.A.',
    depositaria: 'Banco X',
    calificacion: 'EF-3',
    calificado: 'Si',
    tipo_dinero: 'No Aplica',
    comision_ingreso: 0,
    honorarios_adm_sg: 2.0,
    honorarios_adm_sd: 0.3,
    gastos_ord_gestion: 0.1,
    comision_rescate: 0,
    comision_transferencia: 0,
    honorarios_exito: 0,
    moneda_fondo: 'ARS',
    discrepancia_moneda: false,
    plazo_liq: 1,
    dias_para_rescatar: 1,
    minimo_inversion: 1000.0,
    advertencia_distribucion: 'Los rendimientos no consideran distribución de utilidades.',
    enlace_composicion_cnv: null,
    ...extra,
  }
}

/** Cuatro fondos con perfiles cruzados: dos gerentes, dos secciones, uno sin calificación y otro
 *  sin región. DELTA es el único en dólares y el único que sube más de 1% en el día. */
function fondos(): FondoFci[] {
  return [
    fondo({ codigo_cafci: '1', gerente: 'Gainvest S.A.', seccion: 'Renta Variable Peso Argentina', region: 'Arg', horizonte: 'Lar', calificacion: 'EF-3', var_diaria_pct: 0.67, moneda: 'ARS' }),
    fondo({ codigo_cafci: '2', gerente: 'Delta Asset Management S.A.', seccion: 'Renta Variable Dólar', region: 'Bra', horizonte: 'Cor', calificacion: 'A+c(arg)', var_diaria_pct: 1.4, moneda: 'USD' }),
    fondo({ codigo_cafci: '3', gerente: 'Gainvest S.A.', seccion: 'Renta Variable Peso Argentina', region: null, horizonte: 'Flex', calificacion: null, var_diaria_pct: 0.2, moneda: 'ARS' }),
    fondo({ codigo_cafci: '4', gerente: null, seccion: 'Renta Variable Peso Argentina', region: 'Arg', horizonte: 'Lar', calificacion: 'NA', var_diaria_pct: -0.5, moneda: 'ARS' }),
  ]
}

function facetar(parcial: Partial<FiltrosFci> = {}) {
  return facetarFci(fondos(), { ...FILTROS_FCI_VACIOS, ...parcial })
}

function pasa(f: FondoFci, parcial: Partial<FiltrosFci> = {}): boolean {
  return pasaFiltrosFci(f, { ...FILTROS_FCI_VACIOS, ...parcial })
}

describe('pasaFiltrosFci', () => {
  it('sin filtros, todo pasa — incluidos los fondos con campos no informados', () => {
    expect(fondos().every((f) => pasa(f))).toBe(true)
  })

  it('un campo no informado contra un filtro activo no pasa; sin ese filtro se muestra igual', () => {
    const sinGerente = fondo({ gerente: null })
    expect(pasa(sinGerente, { gerente: 'Gainvest S.A.' })).toBe(false)
    expect(pasa(sinGerente)).toBe(true)
  })

  it('el centinela de gerente no informada selecciona exactamente los que no la declaran', () => {
    expect(pasa(fondo({ gerente: null }), { gerente: GERENTE_NO_INFORMADA })).toBe(true)
    expect(pasa(fondo({ gerente: 'Gainvest S.A.' }), { gerente: GERENTE_NO_INFORMADA })).toBe(false)
  })

  it('lo mismo para región y horizonte, que también pueden venir vacíos', () => {
    expect(pasa(fondo({ region: null }), { region: REGION_NO_INFORMADA })).toBe(true)
    expect(pasa(fondo({ region: 'Arg' }), { region: REGION_NO_INFORMADA })).toBe(false)
    expect(pasa(fondo({ horizonte: null }), { horizonte: HORIZONTE_NO_INFORMADO })).toBe(true)
    expect(pasa(fondo({ horizonte: 'Cor' }), { horizonte: HORIZONTE_NO_INFORMADO })).toBe(false)
  })

  it('el horizonte se compara verbatim: "Cor" no es "corto" (regla 11)', () => {
    expect(pasa(fondo({ horizonte: 'Cor' }), { horizonte: 'Cor' })).toBe(true)
    expect(pasa(fondo({ horizonte: 'Cor' }), { horizonte: 'corto' })).toBe(false)
  })

  it('"NA" y "N/A" son calificaciones distintas: la fuente las escribe distinto y no se unifican', () => {
    expect(pasa(fondo({ calificacion: 'NA' }), { calificaciones: ['NA'] })).toBe(true)
    expect(pasa(fondo({ calificacion: 'NA' }), { calificaciones: ['N/A'] })).toBe(false)
    expect(pasa(fondo({ calificacion: 'N/A' }), { calificaciones: ['NA'] })).toBe(false)
  })

  it('sin calificación informada sólo pasa si se pidió el centinela explícitamente', () => {
    const sinCalificacion = fondo({ calificacion: null })
    expect(pasa(sinCalificacion, { calificaciones: ['EF-3'] })).toBe(false)
    expect(pasa(sinCalificacion, { calificaciones: [CALIFICACION_NO_INFORMADA] })).toBe(true)
  })

  it('dos grafías de la misma gestora son dos gestoras distintas, no se normalizan', () => {
    expect(pasa(fondo({ gerente: 'Gainvest S.A.' }), { gerente: 'GAINVEST SA' })).toBe(false)
  })

  it('la moneda del fondo se compara contra el chip; nunca se mezclan dos', () => {
    expect(pasa(fondo({ moneda: 'USD' }), { moneda: 'USD' })).toBe(true)
    expect(pasa(fondo({ moneda: 'ARS' }), { moneda: 'USD' })).toBe(false)
  })

  it('las variaciones están en puntos porcentuales: 0,67 % pasa un mínimo de 0,5 y no uno de 1', () => {
    const f = fondo({ var_diaria_pct: 0.67 })
    expect(pasa(f, { varDiariaMin: '0.5' })).toBe(true)
    expect(pasa(f, { varDiariaMin: '1' })).toBe(false)
    expect(pasa(f, { varDiariaMax: '1' })).toBe(true)
    expect(pasa(f, { varDiariaMax: '0.5' })).toBe(false)
  })

  it('un rango vacío no filtra nada, ni siquiera a los que no publicaron la variación', () => {
    const sinVariacion = fondo({ var_mes_pct: null })
    expect(pasa(sinVariacion, { varMesMin: '' })).toBe(true)
    expect(pasa(sinVariacion, { varMesMin: '0' })).toBe(false)
  })

  it('los cuatro períodos filtran por separado: un mínimo de 12m no mira la variación del día', () => {
    const f = fondo({ var_diaria_pct: -5, var_12m_pct: 55.3 })
    expect(pasa(f, { var12mMin: '50' })).toBe(true)
    expect(pasa(f, { var12mMin: '60' })).toBe(false)
    expect(pasa(f, { varAnioMin: '0' })).toBe(true)
  })
})

describe('facetarFci', () => {
  it('sin filtros ofrece todos los valores presentes, con los flags de no informado', () => {
    const { opciones } = facetar()
    expect(opciones.gerentes).toEqual(['Delta Asset Management S.A.', 'Gainvest S.A.'])
    expect(opciones.tieneGerenteNoInformada).toBe(true)
    expect(opciones.horizontes).toEqual(['Cor', 'Flex', 'Lar'])
    expect(opciones.regiones).toEqual(['Arg', 'Bra'])
    expect(opciones.tieneRegionNoInformada).toBe(true)
    expect(opciones.calificaciones).toEqual(['A+c(arg)', 'EF-3', 'NA'])
    expect(opciones.tieneCalificacionNoInformada).toBe(true)
  })

  it('elegir una gerente acota las demás dimensiones, pero no la propia', () => {
    const { opciones, efectivos } = facetar({ gerente: 'Gainvest S.A.' })
    expect(efectivos.gerente).toBe('Gainvest S.A.')
    expect(opciones.secciones).toEqual(['Renta Variable Peso Argentina'])
    expect(opciones.horizontes).toEqual(['Flex', 'Lar'])
    // El select de gerente sigue ofreciendo todo: si no, no habría cómo cambiar de idea.
    expect(opciones.gerentes).toEqual(['Delta Asset Management S.A.', 'Gainvest S.A.'])
  })

  it('la cascada es bidireccional: elegir sección acota los gerentes ofrecidos', () => {
    const { opciones } = facetar({ seccion: 'Renta Variable Dólar' })
    expect(opciones.gerentes).toEqual(['Delta Asset Management S.A.'])
    expect(opciones.tieneGerenteNoInformada).toBe(false)
  })

  it('la moneda es una faceta más: elegir USD deja sólo los gerentes con fondos en dólares', () => {
    const { opciones, efectivos } = facetar({ moneda: 'USD' })
    expect(efectivos.moneda).toBe('USD')
    expect(opciones.gerentes).toEqual(['Delta Asset Management S.A.'])
  })

  it('un rango de variación acota las dimensiones discretas (aplica antes que las facetas)', () => {
    const { opciones } = facetar({ varDiariaMin: '1' })
    expect(opciones.gerentes).toEqual(['Delta Asset Management S.A.'])
    expect(opciones.secciones).toEqual(['Renta Variable Dólar'])
  })

  it('una selección sin respaldo se apaga y se declara, sin envenenar a las demás', () => {
    const { efectivos, apagadas, opciones } = facetar({
      seccion: 'Renta Variable Dólar',
      gerente: 'Gainvest S.A.',
    })
    expect(efectivos.seccion).toBe('Renta Variable Dólar')
    expect(efectivos.gerente).toBeNull()
    expect(apagadas).toEqual([{ dimension: 'gerente', valor: 'Gainvest S.A.' }])
    // La sección, que sí tiene respaldo, sigue acotando normalmente.
    expect(opciones.horizontes).toEqual(['Cor'])
  })

  it('ante dos selecciones incompatibles gana la más general, no se apagan las dos', () => {
    const { efectivos } = facetar({ moneda: 'ARS', seccion: 'Renta Variable Dólar' })
    expect(efectivos.moneda).toBe('ARS')
    expect(efectivos.seccion).toBeNull()
  })

  it('el multiselect de calificación conserva los valores con respaldo', () => {
    const { efectivos } = facetar({ calificaciones: ['EF-3', 'A+c(arg)'] })
    expect(efectivos.calificaciones.sort()).toEqual(['A+c(arg)', 'EF-3'])
  })

  it('el centinela de calificación filtra como un valor más del multiselect', () => {
    const { efectivos } = facetar({ calificaciones: [CALIFICACION_NO_INFORMADA] })
    expect(efectivos.calificaciones).toEqual([CALIFICACION_NO_INFORMADA])
  })

  it('la moneda puede quedar en null a la salida: quien llama la resuelve, nunca filtra con null', () => {
    const { efectivos } = facetar()
    expect(efectivos.moneda).toBeNull()
  })
})
