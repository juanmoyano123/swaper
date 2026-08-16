/**
 * Las doce celdas del patrón de presentación de balances de un CEDEAR — F-027.
 *
 * No extiende `MiniCalendario` (`components/`, usado por F-016/F-038): aquel dibuja una ventana
 * rodante de meses (índice 0 = el primer mes de la ventana, no necesariamente enero), y éste
 * dibuja el año calendario fijo (índice 0 = enero) — mezclar los dos ejes en un componente
 * invitaría al error de leer una celda con el mes equivocado.
 *
 * Tres estados, nunca un patrón inventado en ninguno: cargando, ausente con su motivo declarado
 * (`SIN_DATO` de fondo), y disponible con la frecuencia medida por mes. `solo_anual` — emisor
 * privado extranjero, sin trimestral clasificable — se marca aparte y no como un patrón completo.
 */

import { SIN_DATO } from '@/lib/fmt'

import type { CalendarioBalances } from '../lib/esquemaBalances'

const ESTILO_CELDA_BASE = {
  width: 7,
  height: 12,
  borderRadius: 2,
} as const

export function PatronBalances({
  calendario,
  cargando,
}: {
  /** `undefined`: todavía no llegó (o no se pidió — no es CEDEAR, o sin CIK resuelto). */
  calendario: CalendarioBalances | undefined
  cargando: boolean
}) {
  if (calendario === undefined) {
    return (
      <span style={{ fontSize: 10, color: 'var(--dim)' }}>
        {cargando ? 'buscando patrón…' : SIN_DATO}
      </span>
    )
  }

  if (!calendario.disponible) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <CeldasVacias motivo={calendario.motivo_ausente} />
        <span style={{ fontSize: 10, color: 'var(--dim)' }}>{SIN_DATO}</span>
      </div>
    )
  }

  const porMes = new Map(calendario.meses.map((m) => [m.mes, m]))
  const ventanaTexto = calendario.ventana ? `${calendario.ventana.desde} a ${calendario.ventana.hasta}` : 's/d'
  const etiqueta = `Balances: presenta en ${calendario.meses.length} de 12 meses, patrón histórico de SEC EDGAR, ventana medida ${ventanaTexto}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <div role="img" aria-label={etiqueta} title={etiqueta} style={{ display: 'flex', gap: 2 }}>
        {Array.from({ length: 12 }, (_, i) => {
          const mes = i + 1
          const dato = porMes.get(mes)
          return (
            <span
              key={mes}
              style={{
                ...ESTILO_CELDA_BASE,
                background: dato ? 'var(--pos)' : 'transparent',
                border: dato ? '1px solid transparent' : '1px solid var(--lin)',
              }}
            />
          )
        })}
      </div>
      {calendario.solo_anual && calendario.nota_solo_anual && (
        <span
          style={{ fontSize: 9.5, color: 'var(--ac2)' }}
          title={calendario.nota_solo_anual}
        >
          sólo patrón anual
        </span>
      )}
    </div>
  )
}

function CeldasVacias({ motivo }: { motivo: string | null }) {
  const etiqueta = `Calendario de balances: ${motivo ?? 'sin dato'}`
  return (
    <div role="img" aria-label={etiqueta} title={etiqueta} style={{ display: 'flex', gap: 2 }}>
      {Array.from({ length: 12 }, (_, i) => (
        // eslint-disable-next-line react/no-array-index-key -- la posición ES la identidad: celda i = mes i
        <span key={i} style={{ ...ESTILO_CELDA_BASE, border: '1px solid var(--lin)' }} />
      ))}
    </div>
  )
}
