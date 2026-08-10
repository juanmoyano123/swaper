/**
 * Columna lateral de KPIs — A9 del design system, Etapa 6 del rediseño del armador.
 *
 * Vive fija a la derecha (`ArmadorPage`, `position: sticky`) para no tener que scrollear hasta el
 * final de la página para saber cómo va la cartera. Todo lo que muestra sale de hooks que las
 * demás secciones ya usan (`useCarteraResuelta`, `useCalendarioCartera`, `rendimientosPorNaturaleza`,
 * `plazoPromedio`, `mixPedido`): no dispara ningún pedido propio, y un mismo número acá y en su
 * panel de origen nunca puede divergir porque es literalmente el mismo cálculo.
 *
 * **Los cuatro KPIs, en el orden del design system**: meses cubiertos, qué tan parejo, TIR
 * ponderada (sólo dólar-hard — regla 2: no se pondera con tasas de otra naturaleza) y duración +
 * mix RF/RV. **"Lo que falta" es sólo lo que se puede derivar de datos que ya están**: meses sin
 * cobertura de la selección y posiciones sin resolver. El chequeo contra un mandato (piso mensual,
 * "máx. 30% renta variable") queda para la feature Mandato — no implementada, sin datos de los que
 * partir; agregar el control sin esa fuente sería fabricar un estado (regla 1).
 */

import { fmtMonto, fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import { unidadDeNaturaleza } from '@/components/SelectorSegmento'

import { useCalendarioCartera } from '../hooks/useCalendarioCartera'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { calcularRentaAnualPorMoneda, invertidoPorMoneda, type RentaAnualPorMoneda } from '../lib/renta'
import { mixPedido } from '../lib/mix'
import { plazoPromedio, rendimientosPorNaturaleza } from '../lib/rendimientos'
import type { MesDelCalendario } from '../lib/schema'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

export function ColumnaKpis({ meses }: { meses: MesDelCalendario[] }) {
  const { pos } = useArmador()
  const { alternarMes } = useArmadorAcciones()
  const { resueltas, porTicker, posicionesParaCalendario } = useCarteraResuelta()
  const calendario = useCalendarioCartera(posicionesParaCalendario)

  // Mismo criterio que `CoberturaSeleccion`: un mes sin_renta no es accionable (nadie en el
  // universo paga ahí), y por eso no entra acá — sólo los que sí tienen algo para elegir.
  const tickers = new Set(pos.map((p) => p.ticker))
  const mesesSinCobertura = meses
    .map((mes, indice) => ({ mes, indice }))
    .filter(
      ({ mes }) =>
        !mes.sin_renta && !mes.instrumentos.some((i) => tickers.has(i.ticker) && i.pct_renta > 0),
    )

  const posicionesSinResolver = resueltas.filter((r) => r.invertido === null)

  const naturalezas = rendimientosPorNaturaleza(resueltas, porTicker)
  const tirUsd = naturalezas.find((n) => n.naturaleza === 'tir_usd') ?? null
  const plazo = plazoPromedio(resueltas, porTicker)
  const mix = mixPedido(pos)

  let rentaUsd: RentaAnualPorMoneda | null = null
  if (calendario.data) {
    const invertidoMapa = invertidoPorMoneda(calendario.data.meses, resueltas)
    const rentaAnual = calendario.data.resumen.renta_anual ?? {}
    const porMoneda = calcularRentaAnualPorMoneda(calendario.data.meses, rentaAnual, invertidoMapa)
    rentaUsd = porMoneda.find((r) => r.moneda === 'usd') ?? null
  }

  return (
    <aside
      aria-label="Resumen de la cartera"
      className="columna-kpis"
      style={{
        display: 'grid',
        gap: 14,
        background: 'var(--pan)',
        border: '1px solid var(--lin)',
        borderRadius: 4,
        padding: '14px 16px',
      }}
    >
      <div>
        <div
          className="rotulo"
          style={{ fontSize: 10, letterSpacing: '0.13em', textTransform: 'uppercase' }}
        >
          Renta anual en dólares
        </div>
        <div className="mono" style={{ fontSize: 36, fontWeight: 600, lineHeight: 1.1, color: 'var(--pos)' }}>
          {rentaUsd?.pct !== null && rentaUsd?.pct !== undefined ? fmtPct(rentaUsd.pct) : SIN_DATO}
        </div>
        <p className="mono" style={{ margin: '2px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>
          {rentaUsd ? fmtMonto(rentaUsd.rentaAnual, 'usd') : SIN_DATO}
          {' / '}
          {rentaUsd?.invertido !== null && rentaUsd?.invertido !== undefined
            ? fmtMonto(rentaUsd.invertido, 'usd')
            : SIN_DATO}
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        <Kpi etiqueta="Meses cubiertos" valor={rentaUsd ? `${rentaUsd.mesesCubiertos}/12` : SIN_DATO} />
        <Kpi etiqueta="Parejo" valor={rentaUsd?.parejo !== null && rentaUsd?.parejo !== undefined ? fmtPct(rentaUsd.parejo * 100) : SIN_DATO} />
        <Kpi
          etiqueta="TIR ponderada (USD)"
          valor={tirUsd?.rendimientoPond !== null && tirUsd?.rendimientoPond !== undefined ? `${fmtPct(tirUsd.rendimientoPond * 100)} ${unidadDeNaturaleza('tir_usd')}` : SIN_DATO}
        />
        <Kpi
          etiqueta="Duración · Mix RF/RV"
          valor={
            (plazo.anios !== null ? `${fmtNumero(plazo.anios, 1)}a` : SIN_DATO) +
            (pos.length > 0 ? ` · ${fmtPct(mix.rf, 0)}/${fmtPct(mix.rv, 0)}` : '')
          }
        />
      </div>

      <div style={{ borderTop: '1px solid var(--lin)', paddingTop: 10 }}>
        <div
          className="rotulo"
          style={{ fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6 }}
        >
          Lo que falta
        </div>
        {mesesSinCobertura.length === 0 && posicionesSinResolver.length === 0 ? (
          <p style={{ margin: 0, fontSize: 11, color: 'var(--dim)' }}>Nada pendiente por ahora.</p>
        ) : (
          <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'grid', gap: 6 }}>
            {mesesSinCobertura.map(({ mes, indice }) => (
              <li key={mes.etiqueta}>
                <button
                  type="button"
                  onClick={() => alternarMes(indice)}
                  style={{
                    font: 'inherit',
                    fontSize: 11,
                    color: 'var(--neg)',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    textAlign: 'left',
                    textDecoration: 'underline',
                    textUnderlineOffset: 2,
                    cursor: 'pointer',
                  }}
                  title={`${mes.nombre}: sin papel de la cartera armada que pague este mes`}
                >
                  {/* `mes.etiqueta` (mm/aaaa) y no `mes.nombre` en el texto ni en el nombre
                      accesible: el nombre completo ("Noviembre 2026") es el mismo texto que usan
                      los botones de mes de la grilla más arriba, y ambigüedad aparte, un test que
                      busque "Noviembre 2026" sin más contexto encontraría los dos. El nombre
                      completo sigue disponible en el `title`, sin entrar al nombre accesible. */}
                  {mes.etiqueta} sin cobertura → abrí el mes
                </button>
              </li>
            ))}
            {posicionesSinResolver.length > 0 && (
              <li style={{ fontSize: 11, color: 'var(--ac2)' }}>
                {posicionesSinResolver.length} posición(es) sin precio o tipo de cambio: no se
                pudieron resolver.
              </li>
            )}
          </ul>
        )}
      </div>
    </aside>
  )
}

function Kpi({ etiqueta, valor }: { etiqueta: string; valor: string }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 13, color: 'var(--tx)' }}>
        {valor}
      </div>
      <div style={{ fontSize: 9, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {etiqueta}
      </div>
    </div>
  )
}
