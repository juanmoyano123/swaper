/**
 * El gráfico de barras del calendario de doce meses — extraído de `DiagnosticoCartera.tsx` (F-030)
 * en F-036 para que `PlanDeRotacion` lo reuse tal cual sobre la cartera propuesta, en vez de
 * duplicar el render: una sola implementación de "así se ve la renta mes a mes" para toda la app.
 */

import { picoDeColumnas, type ColumnaCordillera } from '@/lib/cartera/renta'

export function Cordillera({
  titulo,
  columnas,
  alto,
  colorBarra,
  formatoMonto,
  leyenda,
}: {
  titulo: string
  columnas: ColumnaCordillera[]
  alto: number
  colorBarra: string
  formatoMonto: (valor: number) => string
  leyenda: string
}) {
  const pico = picoDeColumnas(columnas)

  return (
    <div style={{ background: 'var(--pan)', border: '1px solid var(--lin)', borderRadius: 4, padding: '12px 16px' }}>
      <div className="rotulo" style={{ fontSize: 10, letterSpacing: '0.13em', color: 'var(--ac)', textTransform: 'uppercase', marginBottom: 10 }}>
        {titulo}
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end', height: alto }}>
        {columnas.map((columna) => (
          <div
            key={columna.etiqueta}
            title={`${columna.nombre}: ${formatoMonto(columna.total)}`}
            style={{ flex: 1, minWidth: 0, height: alto, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}
          >
            <span className="mono" style={{ fontSize: 9.5, textAlign: 'center', color: columna.total === 0 ? 'var(--neg)' : 'var(--dim)', marginBottom: 3 }}>
              {columna.total === 0 ? '0' : formatoMonto(columna.total)}
            </span>
            <span
              style={{
                display: 'block',
                height: pico > 0 ? (columna.total / pico) * (alto - 22) : 0,
                background: colorBarra,
                borderRadius: '2px 2px 0 0',
              }}
            />
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
        {columnas.map((columna) => (
          <div key={columna.etiqueta} className="mono" style={{ flex: 1, minWidth: 0, textAlign: 'center', fontSize: 9, color: 'var(--dim)' }}>
            {columna.etiqueta}
          </div>
        ))}
      </div>

      <p style={{ margin: '8px 0 0', fontSize: 10.5, color: 'var(--dim)' }}>{leyenda}</p>
    </div>
  )
}
