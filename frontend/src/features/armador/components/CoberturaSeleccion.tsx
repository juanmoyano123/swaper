/**
 * La fila de cobertura de los doce meses según la cartera seleccionada — GWT-3.
 *
 * **Dos faltantes distintos, y no se pueden pintar igual.** Un mes "sin cobertura" (rojo, `—`) es
 * uno donde ningún papel de la selección actual paga: es accionable, el asesor puede ir a ese mes
 * en la grilla y elegir algo. Un mes `sin_renta` es otra cosa — nadie en el universo entero paga
 * ahí, así que no hay ningún papel que agregar para cubrirlo. Marcarlos igual haría pasar "no
 * elegiste bien" por "no hay nada para elegir", y son problemas que se resuelven distinto.
 */

import type { MesDelCalendario } from '../lib/schema'
import { useArmador } from '../store/carteraStore'

export function CoberturaSeleccion({ meses }: { meses: MesDelCalendario[] }) {
  const { pos } = useArmador()
  const tickers = new Set(pos.map((p) => p.ticker))

  const cubierto = (mes: MesDelCalendario) =>
    mes.instrumentos.some((i) => tickers.has(i.ticker) && i.pct_renta > 0)

  return (
    <div
      role="row"
      aria-label="Cobertura de la cartera seleccionada"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${meses.length}, minmax(0, 1fr))`,
        gap: 8,
        marginBottom: 6,
      }}
    >
      {meses.map((mes) => {
        const cubreEsteMes = cubierto(mes)
        const estado = mes.sin_renta ? 'sin_renta' : cubreEsteMes ? 'cubierto' : 'sin_cobertura'
        return (
          <div
            key={mes.etiqueta}
            role="cell"
            aria-label={`cobertura de ${mes.nombre}: ${estado}`}
            className="mono"
            style={{
              textAlign: 'center',
              fontSize: 11,
              padding: '2px 0',
              color:
                estado === 'sin_renta' ? 'var(--dim)' : estado === 'cubierto' ? 'var(--pos)' : 'var(--neg)',
            }}
            title={
              estado === 'sin_renta'
                ? 'ningún papel del universo paga este mes'
                : estado === 'cubierto'
                  ? 'cubierto por la selección actual'
                  : 'sin papel de la cartera armada que pague este mes'
            }
          >
            {estado === 'sin_renta' ? '·' : estado === 'cubierto' ? '✓' : '—'}
          </div>
        )
      })}
    </div>
  )
}
