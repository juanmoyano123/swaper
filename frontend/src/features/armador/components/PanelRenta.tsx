/**
 * F-021 — el panel de renta mensual y renta anual sobre lo invertido.
 *
 * Es el feedback en vivo que convierte al calendario en selector y no en consulta: cada vez que el
 * asesor agrega o saca un papel, `useCalendarioCartera` recalcula sobre `posicionesParaCalendario`
 * (de `useCarteraResuelta`, base común de la Tanda 9) y las tres piezas del panel se actualizan
 * juntas, sin recargar la pantalla.
 *
 * Dos cordilleras, dos escalas, dos totales — nunca uno mezclado (A2 dólares, A3 pesos), y una
 * tarjeta de renta anual por cada moneda de cobro presente (A9). Ver `lib/renta.ts` para el porqué
 * de cada número.
 *
 * **Fuera de alcance de esta pasada, por falta de dato en el store, no por diseño**: la línea de
 * piso mensual y el coloreado de montos contra ella (A1, mandato del cliente, no implementado
 * todavía), la silueta de la cartera original (`ghost`/"Leer cartera del cliente", no implementada)
 * y el modo de entrada de renta variable (`rvModo` — F-026 resuelve la renta variable aparte y no
 * cuelga de este calendario). Ninguno de los tres tiene una fuente de datos hoy; agregar el control
 * sin ella sería fabricar un estado, que es justo lo que la regla 1 del proyecto prohíbe.
 */

import { EstadoCarga } from '@/components/EstadoCarga'
import { EstadoError } from '@/components/EstadoError'
import { fmtCompacto, fmtMonto } from '@/lib/fmt'

import { useCalendarioCartera } from '../hooks/useCalendarioCartera'
import { useCarteraResuelta } from '../hooks/useCarteraResuelta'
import { calcularRentaAnualPorMoneda, columnasDeCordillera, invertidoPorMoneda } from '../lib/renta'

import { DetalleMesCartera } from './DetalleMesCartera'
import { PanelRentaAnual } from './PanelRentaAnual'
import { PanelRentaCordillera } from './PanelRentaCordillera'

export function PanelRenta() {
  const { posicionesParaCalendario, resueltas, tipoDeCambio } = useCarteraResuelta()
  const calendario = useCalendarioCartera(posicionesParaCalendario)

  if (posicionesParaCalendario.length === 0) {
    return (
      <div
        style={{
          padding: '10px 12px',
          border: '1px dashed var(--lin)',
          borderRadius: 4,
          fontSize: 12,
          color: 'var(--dim)',
        }}
      >
        Sin posiciones de renta fija con monto asignado todavía: agregá papeles y un monto total
        para ver la renta mensual y la renta anual sobre lo invertido.
      </div>
    )
  }

  if (calendario.isPending) return <EstadoCarga que="el calendario de la cartera" />
  if (calendario.isError) {
    return <EstadoError error={calendario.error} onRetry={() => void calendario.refetch()} />
  }
  if (!calendario.data) return null

  const { meses, resumen } = calendario.data
  const rentaAnual = resumen.renta_anual ?? {}
  const invertidoMapa = invertidoPorMoneda(meses, resueltas, tipoDeCambio)
  const porMoneda = calcularRentaAnualPorMoneda(meses, rentaAnual, invertidoMapa)

  const columnasUsd = columnasDeCordillera(meses, 'usd')
  const columnasArs = columnasDeCordillera(meses, 'ars')
  const hayPosicionesEnPesos = resumen.monedas.includes('ars')

  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <PanelRentaCordillera
        titulo="Cordillera en dólares"
        bajada="Tocá un mes para abrirlo y comparar los papeles que pagan ahí."
        columnas={columnasUsd}
        alto={290}
        colorBarra="var(--pos)"
        formatoMonto={(v) => fmtMonto(v, 'usd', 0)}
        leyenda="Renta (cupón) en dólares · ◆ amortización de capital, no es renta."
      />

      {hayPosicionesEnPesos ? (
        <PanelRentaCordillera
          titulo="Cordillera en pesos"
          columnas={columnasArs}
          alto={118}
          colorBarra="var(--ac2)"
          formatoMonto={(v) => `$ ${fmtCompacto(v)}`}
          leyenda="Escala propia, en pesos. Los cobros en pesos nunca se suman a los dólares ni se convierten para el total."
        />
      ) : (
        <div
          style={{
            background: 'var(--pan)',
            border: '1px dashed var(--lin)',
            borderRadius: 4,
            padding: '10px 16px',
            fontSize: 11.5,
            color: 'var(--dim)',
          }}
        >
          Sin posiciones que cobren en pesos en esta cartera: no hay cordillera en pesos que
          mostrar.
        </div>
      )}

      <DetalleMesCartera meses={meses} />

      <PanelRentaAnual datos={porMoneda} />
    </div>
  )
}
