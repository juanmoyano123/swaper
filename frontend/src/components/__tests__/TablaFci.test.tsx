/**
 * `TablaFci` — F-057. Los casos límite medidos contra la planilla real de CAFCI: centinelas de
 * plazo, USB sin traducir, discrepancia de moneda declarada y calificación ausente.
 */

import { render, screen } from '@testing-library/react'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'

import { TablaFci } from '../TablaFci'
import type { FondoFci, PlanillaFci } from '@/lib/fci'

beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 520 })
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 900 })
})

afterAll(() => {
  Reflect.deleteProperty(HTMLElement.prototype, 'offsetHeight')
  Reflect.deleteProperty(HTMLElement.prototype, 'offsetWidth')
})

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
    tipo_dinero: 'Ahorro',
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
    ...extra,
  }
}

const PLANILLA: PlanillaFci = {
  fecha_planilla: '2026-08-21',
  fecha_cierre_anterior: '2026-08-20',
  fecha_base_mes: '2026-07-31',
  fecha_base_anio: '2025-12-30',
  fecha_base_12m: '2025-07-31',
  total_filas: 1,
  capturado_en: '2026-08-21T12:00:00Z',
  advertencia_distribucion: 'Los rendimientos no consideran distribución de utilidades.',
}

describe('TablaFci', () => {
  it('sin fondos, declara que no hay filas en vez de mostrar una grilla vacía', () => {
    render(<TablaFci fondos={[]} etiqueta="FCI renta variable" planilla={PLANILLA} onAbrirFondo={vi.fn()} />)
    expect(screen.getByText(/No hay FCI renta variable en la planilla de hoy/)).toBeInTheDocument()
  })

  it('un fondo con moneda USB se muestra tal cual, sin traducir', () => {
    render(
      <TablaFci
        fondos={[fondo({ moneda: 'USB' })]}
        etiqueta="FCI renta variable"
        planilla={PLANILLA}
        onAbrirFondo={vi.fn()}
      />,
    )
    expect(screen.getByText('USB')).toBeInTheDocument()
  })

  it('un plazo centinela (9999) no se traduce a "no aplica": la celda de rescate queda vacía', () => {
    render(
      <TablaFci
        fondos={[fondo({ plazo_liq: 9999, dias_para_rescatar: null })]}
        etiqueta="FCI renta variable"
        planilla={PLANILLA}
        onAbrirFondo={vi.fn()}
      />,
    )
    expect(screen.getByTitle('Plazo Liq. crudo: 9999')).toHaveTextContent('s/d')
  })

  it('una calificación ausente se muestra como "no informada", nunca vacía', () => {
    render(
      <TablaFci
        fondos={[fondo({ calificacion: null })]}
        etiqueta="FCI renta variable"
        planilla={PLANILLA}
        onAbrirFondo={vi.fn()}
      />,
    )
    expect(screen.getByText('no informada')).toBeInTheDocument()
  })

  it('la discrepancia entre moneda de sección y moneda de fondo se declara con un ícono, no se resuelve', () => {
    render(
      <TablaFci
        fondos={[fondo({ discrepancia_moneda: true, moneda: 'ARS', moneda_fondo: 'USD' })]}
        etiqueta="FCI renta variable"
        planilla={PLANILLA}
        onAbrirFondo={vi.fn()}
      />,
    )
    expect(screen.getByTitle('Moneda de sección ARS, moneda de fondo USD')).toBeInTheDocument()
  })

  it('la advertencia de la fuente sobre distribución de utilidades se muestra junto a las variaciones', () => {
    render(<TablaFci fondos={[fondo()]} etiqueta="FCI renta variable" planilla={PLANILLA} onAbrirFondo={vi.fn()} />)
    expect(screen.getByText(PLANILLA.advertencia_distribucion)).toBeInTheDocument()
  })

  it('clickear una fila abre la ficha de ese fondo por su código CAFCI', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const onAbrirFondo = vi.fn()
    render(
      <TablaFci fondos={[fondo({ codigo_cafci: '1031' })]} etiqueta="FCI renta variable" planilla={PLANILLA} onAbrirFondo={onAbrirFondo} />,
    )
    await userEvent.click(screen.getByText('Gainvest Renta Variable - Clase A'))
    expect(onAbrirFondo).toHaveBeenCalledWith('1031')
  })
})
