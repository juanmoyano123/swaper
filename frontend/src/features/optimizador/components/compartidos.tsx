/**
 * Piezas que comparten las dos secciones del optimizador: F-033 ("mantener la TIR y bajar el
 * riesgo") y F-034 ("subir la TIR declarando la contrapartida").
 *
 * Las filas de propuesta de cada modo son distintas por diseño —una muestra el eje elegido, la otra
 * todas las contrapartidas—, pero el formato de un valor de eje, el costo de rotar y el recuento de
 * lo descartado tienen que leerse igual en las dos: si "p40" significara una cosa arriba y otra
 * abajo, el asesor tendría que aprender dos vocabularios en la misma pantalla.
 */

import { fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import type { EjeDeRiesgo } from '@/lib/cartera/riesgo'
import { BANDA_RENDIMIENTO_PP } from '@/lib/rotaciones/bajarRiesgo'
import { NOMBRES_EJE, type DescarteCandidata } from '@/lib/rotaciones/ejes'
import type { CostoRotacion } from '@/lib/rotaciones/esquemaRotaciones'

export const MOTIVO_LABEL: Record<DescarteCandidata['motivo'], string> = {
  empeora: 'empeora este eje',
  sin_dato: 'sin dato para medirlo',
  sin_criterio_medible: 'sin criterio medible (distinto emisor)',
  fuera_de_banda: `el rendimiento se mueve más de ${fmtPct(BANDA_RENDIMIENTO_PP, 1)}`,
}

/** Un valor de eje en su unidad. `null` es `s/d`: el eje existe pero no se pudo medir. */
export function formatoValor(valor: number | null, unidad: EjeDeRiesgo['unidad']): string {
  if (valor === null) return SIN_DATO
  if (unidad === 'años') return `${fmtNumero(valor, 1)} años`
  if (unidad === 'percentil') return `p${fmtNumero(valor, 0)}`
  return fmtPct(valor, 1)
}

/**
 * El costo real de rotar — F-035, primera vez en pantalla.
 *
 * Tres estados, y la diferencia entre ellos es la feature: con las dos patas cotizando se muestra
 * el costo y en cuánto tiempo lo paga la mejora; sin alguna punta viva **no se muestra un costo**,
 * se declara que no es verificable y se nombra el único piso que sí se conoce (el arancel, que es
 * una constante del broker y no un dato de mercado). Un spread ausente contado como cero haría que
 * una rotación cara se leyera como barata — regla 1: el hueco no se rellena.
 */
export function NotaCosto({ costo }: { costo: CostoRotacion | null }) {
  const estilo = { margin: 0, fontSize: 10.5 } as const

  if (costo === null) {
    return (
      <p className="mono" style={{ ...estilo, color: 'var(--sd)' }}>
        Costo de rotar: {SIN_DATO}
      </p>
    )
  }

  if (!costo.verificable || costo.total_pct === null) {
    return (
      <p className="mono" style={{ ...estilo, color: 'var(--sd)' }}>
        Costo de rotar no verificable: falta punta de mercado en alguna pata. Piso conocido: arancel{' '}
        {fmtPct(costo.arancel_pct_por_pata, 2)} por pata.
      </p>
    )
  }

  return (
    <p className="mono" style={{ ...estilo, color: costo.elevado === true ? 'var(--neg)' : 'var(--sd)' }}>
      Costo de rotar {fmtPct(costo.total_pct, 2)} (arancel {fmtPct(costo.arancel_pct_por_pata, 2)} por pata + spread de
      las dos patas)
      {costo.payback_meses !== null && ` · lo paga en ${fmtNumero(costo.payback_meses, 1)} meses`}
      {costo.elevado === true && ' · costo elevado'}
    </p>
  )
}

/** Qué se descartó y por qué: lo que no se muestra se cuenta, nunca desaparece en silencio. */
export function ResumenDescartes({ descartes, encabezado }: { descartes: DescarteCandidata[]; encabezado?: string }) {
  if (descartes.length === 0) return null

  const porMotivo = new Map<string, number>()
  for (const d of descartes) {
    const clave = `${NOMBRES_EJE[d.eje]} — ${MOTIVO_LABEL[d.motivo]}`
    porMotivo.set(clave, (porMotivo.get(clave) ?? 0) + 1)
  }

  return (
    <div style={{ display: 'grid', gap: 4 }}>
      <p style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)' }}>
        {encabezado ??
          `${descartes.length} candidata${descartes.length === 1 ? '' : 's'} descartada${descartes.length === 1 ? '' : 's'}:`}
      </p>
      <ul style={{ margin: 0, padding: '0 0 0 16px', fontSize: 10.5, color: 'var(--dim)' }}>
        {[...porMotivo.entries()].map(([clave, cantidad]) => (
          <li key={clave}>
            {cantidad} por {clave.toLowerCase()}
          </li>
        ))}
      </ul>
    </div>
  )
}
