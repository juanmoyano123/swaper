/**
 * Piezas que comparten las dos secciones del optimizador: F-033 ("mantener la TIR y bajar el
 * riesgo") y F-034 ("subir la TIR declarando la contrapartida"), más lo que suma F-036 (aceptar,
 * descartar, efecto sobre el calendario) a las dos.
 *
 * Las filas de propuesta de cada modo son distintas por diseño —una muestra el eje elegido, la otra
 * todas las contrapartidas—, pero el formato de un valor de eje, el costo de rotar, el recuento de
 * lo descartado y ahora la decisión tienen que leerse igual en las dos: si "p40" significara una
 * cosa arriba y otra abajo, el asesor tendría que aprender dos vocabularios en la misma pantalla.
 */

import { fmtNumero, fmtPct, SIN_DATO } from '@/lib/fmt'
import type { EjeDeRiesgo } from '@/lib/cartera/riesgo'
import { BANDA_RENDIMIENTO_PP } from '@/lib/rotaciones/bajarRiesgo'
import { claveCandidata, NOMBRES_EJE, type DescarteCandidata } from '@/lib/rotaciones/ejes'
import type { Candidata, CostoRotacion } from '@/lib/rotaciones/esquemaRotaciones'
import { useEfectoCalendario } from '@/lib/rotaciones/hooks/useEfectoCalendario'
import type { PosicionConMonto } from '@/lib/rotaciones/plan'

import { usePlanRotacionAcciones } from '../store/planRotacionStore'

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
 * se declara que no es verificable y se nombra el único piso que sí se conoce (el arancel). Un
 * spread ausente contado como cero haría que una rotación cara se leyera como barata — regla 1: el
 * hueco no se rellena.
 *
 * **El arancel no es un dato de mercado, ni siquiera un valor publicado por el bróker**: es un
 * parámetro asumido del motor (`ARANCEL_POR_PATA` en `rotaciones/constantes.py`, heredado del
 * default de un flag de CLI). Por eso se rotula "estimado" en vez de mostrarse como si fuera una
 * medición — a diferencia del spread, que sí sale de una punta viva del mercado.
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
        Costo de rotar no verificable: falta punta de mercado en alguna pata. Piso conocido: arancel
        estimado {fmtPct(costo.arancel_pct_por_pata, 2)} por pata.
      </p>
    )
  }

  return (
    <p className="mono" style={{ ...estilo, color: costo.elevado === true ? 'var(--neg)' : 'var(--sd)' }}>
      Costo de rotar {fmtPct(costo.total_pct, 2)} (arancel estimado{' '}
      <span title="Parámetro asumido por el motor, no un dato de mercado ni publicado por el bróker: no varía por cuenta ni por volumen. Se declara como estimado y no como medido.">
        {fmtPct(costo.arancel_pct_por_pata, 2)}
      </span>{' '}
      por pata + spread de las dos patas)
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

/**
 * Aceptar y descartar una rotación — GWT-2 y GWT-4 de F-036. Los dos botones viven en la fila y
 * despachan directo al plan (`usePlanRotacionAcciones`); no hay callback que subir por props porque
 * la decisión es sobre esa candidata puntual, no sobre la sección que la muestra.
 *
 * `deshabilitado` es sólo para Aceptar: descartar una candidata que no se puede convertir a monto
 * siempre es posible (es sacarla de la vista), pero aceptarla dejaría el monto de esa posición sin
 * poder calcularse — se explica por qué en el `title`, nunca se aceptan en silencio.
 */
export function BotonesDecision({
  candidata,
  deshabilitado = false,
  motivoDeshabilitado = null,
}: {
  candidata: Candidata
  deshabilitado?: boolean
  motivoDeshabilitado?: string | null
}) {
  const acciones = usePlanRotacionAcciones()
  const base = { font: 'inherit', fontSize: 11, padding: '4px 10px', borderRadius: 3 } as const

  return (
    <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
      <button
        type="button"
        onClick={() => acciones.aceptar(candidata)}
        disabled={deshabilitado}
        title={deshabilitado ? (motivoDeshabilitado ?? undefined) : undefined}
        style={{
          ...base,
          cursor: deshabilitado ? 'not-allowed' : 'pointer',
          border: '1px solid var(--ac)',
          background: deshabilitado ? 'var(--pan2)' : 'var(--ac)',
          color: deshabilitado ? 'var(--dim)' : '#08120c',
        }}
      >
        Aceptar
      </button>
      <button
        type="button"
        onClick={() => acciones.descartar(claveCandidata(candidata))}
        style={{ ...base, cursor: 'pointer', border: '1px solid var(--lin)', background: 'transparent', color: 'var(--dim)' }}
      >
        Descartar
      </button>
    </div>
  )
}

/**
 * GWT-1 de F-036: "declara qué mes del calendario se llena y qué mes se vacía si se acepta". Pide
 * el efecto con `useEfectoCalendario` y lo traduce a una sola línea, agrupada por moneda —nunca se
 * suman entre sí (regla 3)— y con el motivo nombrado cuando no es calculable (regla 1).
 *
 * `montos` vacío significa que la pantalla todavía no tiene con qué convertir la cartera a plata
 * (tests que no lo pasan, o una cartera cuya valuación no terminó): en ese caso no se muestra nada
 * en vez de declarar un efecto a medias.
 */
export function EfectoCalendarioNota({
  candidata,
  montos,
  monedaDe,
  tipoDeCambio,
}: {
  candidata: Candidata
  montos: PosicionConMonto[]
  monedaDe: (ticker: string) => 'usd' | 'ars' | null
  tipoDeCambio: number | null
}) {
  const { cargando, error, efecto } = useEfectoCalendario(montos, candidata, monedaDe, tipoDeCambio)
  const estilo = { margin: 0, fontSize: 10.5, color: 'var(--sd)' } as const

  if (montos.length === 0) return null
  if (cargando) {
    return (
      <p className="mono" style={estilo}>
        Efecto sobre el calendario: calculando…
      </p>
    )
  }
  if (error || !efecto) {
    return (
      <p className="mono" style={estilo}>
        Efecto sobre el calendario: {SIN_DATO}
      </p>
    )
  }

  return (
    <p className="mono" style={estilo}>
      {textoEfectoCalendario(efecto)}
    </p>
  )
}

function textoEfectoCalendario(efecto: {
  calculable: boolean
  motivoNoCalculable: string | null
  seLlenan: { nombre: string; moneda: string }[]
  seVacian: { nombre: string; moneda: string }[]
  mesesQueCambian: number
}): string {
  if (!efecto.calculable) return efecto.motivoNoCalculable ?? 'Efecto sobre el calendario no calculable.'

  const partes = [
    ...efecto.seLlenan.map((m) => `se llena ${m.nombre} (${m.moneda.toUpperCase()})`),
    ...efecto.seVacian.map((m) => `se vacía ${m.nombre} (${m.moneda.toUpperCase()})`),
  ]

  if (partes.length === 0) {
    return efecto.mesesQueCambian > 0
      ? `No cambia qué meses cobran renta (cambia el monto en ${efecto.mesesQueCambian} ${efecto.mesesQueCambian === 1 ? 'mes' : 'meses'}).`
      : 'No cambia qué meses cobran renta.'
  }

  return `Si se acepta: ${partes.join(' · ')}.`
}
