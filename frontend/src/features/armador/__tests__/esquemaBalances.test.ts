import { describe, expect, it } from 'vitest'

import { esquemaRespuestaBalances } from '../lib/esquemaBalances'

function calendarioValido(extra: Record<string, unknown> = {}) {
  return {
    papel: 'AAPL',
    fuente: 'SEC EDGAR',
    disponible: true,
    motivo_ausente: null,
    solo_anual: false,
    nota_solo_anual: null,
    cik: '320193',
    ventana: { desde: '2024-01-01', hasta: '2026-08-01' },
    meses: [{ mes: 2, presentaciones: 1, formularios: ['10-K'] }],
    capturado_en: '2026-08-16T00:00:00Z',
    ...extra,
  }
}

describe('esquemaRespuestaBalances', () => {
  it('acepta un calendario disponible con la forma real del backend', () => {
    const resultado = esquemaRespuestaBalances.safeParse({ calendarios: [calendarioValido()] })
    expect(resultado.success).toBe(true)
  })

  it('acepta un calendario declarado ausente, con ventana y cik en null', () => {
    const ausente = calendarioValido({
      disponible: false,
      motivo_ausente: 'la SEC no lista este papel: no tiene CIK asociado',
      cik: null,
      ventana: null,
      meses: [],
    })
    const resultado = esquemaRespuestaBalances.safeParse({ calendarios: [ausente] })
    expect(resultado.success).toBe(true)
  })

  it('rechaza un contrato roto (falta un campo obligatorio)', () => {
    const { fuente: _fuente, ...sinFuente } = calendarioValido()
    const resultado = esquemaRespuestaBalances.safeParse({ calendarios: [sinFuente] })
    expect(resultado.success).toBe(false)
  })

  it('rechaza un mes fuera de 1..12', () => {
    const roto = calendarioValido({ meses: [{ mes: 13, presentaciones: 1, formularios: [] }] })
    const resultado = esquemaRespuestaBalances.safeParse({ calendarios: [roto] })
    expect(resultado.success).toBe(false)
  })
})
