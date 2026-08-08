/**
 * Una cordillera de doce columnas para **una sola moneda de cobro** — A2 (dólares) y A3 (pesos)
 * del design system son dos instancias de este mismo componente, con su propio alto, color y
 * escala. Nunca comparten eje: cada una arma su propio `pico` a partir de sus propias columnas, así
 * que un mes de US$ 400 y un mes de $ 400.000 no terminan con la misma altura de barra por
 * casualidad (regla 3 del proyecto).
 *
 * Clic en una columna alterna el mes seleccionado del store, igual que la grilla de F-016 —
 * seleccionar desde acá o desde ahí es la misma acción sobre el mismo estado.
 */

import type { ColumnaCordillera } from '../lib/renta'
import { picoDeColumnas } from '../lib/renta'
import { useArmador, useArmadorAcciones } from '../store/carteraStore'

const ALTURA_ETIQUETA = 22

export function PanelRentaCordillera({
  titulo,
  bajada,
  columnas,
  alto,
  colorBarra,
  formatoMonto,
  leyenda,
}: {
  titulo: string
  bajada?: string
  columnas: ColumnaCordillera[]
  /** Alto del área de gráfico en px — 290 en A2, 118 en A3. */
  alto: number
  colorBarra: string
  formatoMonto: (valor: number) => string
  leyenda: string
}) {
  const { selMes } = useArmador()
  const { alternarMes } = useArmadorAcciones()
  const pico = picoDeColumnas(columnas)
  const alturaBarra = alto - ALTURA_ETIQUETA

  return (
    <div style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}>
      <header style={{ marginBottom: 10 }}>
        <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase' }}>
          {titulo}
        </div>
        {bajada && <p style={{ margin: '2px 0 0', fontSize: 11.5, color: 'var(--dim)', textWrap: 'pretty' }}>{bajada}</p>}
      </header>

      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', height: alto }}>
        {columnas.map((columna) => {
          const seleccionada = selMes === columna.indice
          const etiquetaColor = columna.total === 0 ? 'var(--neg)' : 'var(--tx)'

          return (
            <button
              key={columna.etiqueta}
              type="button"
              onClick={() => alternarMes(columna.indice)}
              aria-pressed={seleccionada}
              aria-label={`${columna.nombre}: ${formatoMonto(columna.total)}`}
              title={`${columna.nombre}: ${formatoMonto(columna.total)}`}
              style={{
                flex: 1,
                minWidth: 0,
                height: alto,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'flex-end',
                alignItems: 'stretch',
                background: seleccionada ? 'var(--sel)' : 'transparent',
                border: 'none',
                borderRadius: 4,
                padding: 0,
                cursor: 'pointer',
                font: 'inherit',
              }}
            >
              <span
                className="mono"
                style={{ fontSize: 11.5, textAlign: 'center', color: etiquetaColor, marginBottom: 3 }}
              >
                {columna.total === 0 ? '—' : formatoMonto(columna.total)}
              </span>
              <span
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  borderTopLeftRadius: 4,
                  borderTopRightRadius: 4,
                  overflow: 'hidden',
                }}
              >
                {columna.segmentos.map((segmento, indice) => (
                  <span
                    key={segmento.ticker}
                    style={{
                      display: 'block',
                      height: pico > 0 ? (segmento.monto / pico) * alturaBarra : 0,
                      background: colorBarra,
                      borderTop: indice === 0 ? 'none' : '1px solid rgba(0,0,0,.35)',
                    }}
                  />
                ))}
              </span>
            </button>
          )
        })}
      </div>

      <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
        {columnas.map((columna) => {
          const seleccionada = selMes === columna.indice
          return (
            <div key={columna.etiqueta} style={{ flex: 1, minWidth: 0, textAlign: 'center' }}>
              <div
                className="mono"
                style={{
                  fontSize: 10,
                  fontWeight: seleccionada ? 700 : 400,
                  color: seleccionada ? 'var(--ac)' : 'var(--dim)',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {columna.etiqueta}
              </div>
              {columna.amortizacion > 0 && (
                <span
                  title={`Amortización: ${formatoMonto(columna.amortizacion)}`}
                  style={{
                    display: 'inline-block',
                    width: 6,
                    height: 6,
                    marginTop: 3,
                    background: 'var(--ac2)',
                    transform: 'rotate(45deg)',
                  }}
                />
              )}
            </div>
          )
        })}
      </div>

      <p style={{ margin: '10px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>{leyenda}</p>
    </div>
  )
}
