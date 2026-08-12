/**
 * Seis barras paralelas — el vector de riesgo de F-031, nunca un radar: el área de un radar se
 * lee como puntaje (`claude-docs/progress/boceto.html:242-245`).
 *
 * Presentacional puro: no pide nada, no decide nada, sólo dibuja lo que `vectorDeRiesgo()` ya
 * calculó. **No existe acá ninguna suma, promedio ni color de "riesgo total"** — cada eje tiene su
 * propia escala, declarada eje por eje, y nunca se combinan (regla 7 del dominio, GWT-1).
 *
 * Escala de la barra superior, por eje:
 * - duración: `valor / 10` años, recortado a 1 (nunca desborda la barra).
 * - liquidez: `valor / 100` (ya es percentil).
 * - legislación: `valor / 100` (ya es peso en pp sobre el total).
 * - concentración: sin barra superior — se resuelve directo con los tramos con tope.
 * - crédito y moneda (compositivos, `valor: null`): sin barra superior — la fila entera es la
 *   composición de sus grupos, con `DistribucionBarras`.
 *
 * Color (Etapa 1 del rediseño del armador): las barras de este componente miden un valor contra
 * una escala, no reparten una composición — usan `--medida`, no la paleta categórica de
 * `DistribucionBarras`. El verde (`--ac`) queda para selección/interacción; acá una medición no
 * es "positivo" ni "elegido". Excedido sigue en `--neg`, sin dato en `--sd`.
 */

import { DistribucionBarras, type TramoDistribucion } from './DistribucionBarras'
import { fmtNumero, fmtPct, NO_APLICA, SIN_DATO } from '@/lib/fmt'
import type { EjeDeRiesgo, GrupoDeEje, TramoDeEje } from '@/lib/cartera/riesgo'

const ALTO_BARRA = 8

export function VectorDeRiesgo({ ejes }: { ejes: EjeDeRiesgo[] }) {
  return (
    <div role="list" aria-label="Vector de riesgo" style={{ display: 'grid', gap: 16 }}>
      {ejes.map((eje) => (
        <FilaEje key={eje.id} eje={eje} />
      ))}
    </div>
  )
}

function FilaEje({ eje }: { eje: EjeDeRiesgo }) {
  return (
    <div role="listitem" aria-label={eje.nombre} style={{ display: 'grid', gap: 5 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
        <span style={{ color: 'var(--tx)' }}>{eje.nombre}</span>
        <span className="mono" style={{ color: 'var(--tx)' }}>
          {formatoValor(eje)}
        </span>
      </div>

      <CuerpoEje eje={eje} />

      <p className="mono" style={{ margin: 0, fontSize: 10, color: 'var(--sd)' }}>
        {textoCobertura(eje)}
      </p>
      {eje.cobertura.notas.map((nota) => (
        <p key={nota} style={{ margin: 0, fontSize: 10.5, color: 'var(--dim)', textWrap: 'pretty' }}>
          {nota}
        </p>
      ))}
    </div>
  )
}

function formatoValor(eje: EjeDeRiesgo): string {
  // `unidad: null` es "no aplica" (el eje es compositivo por diseño, nunca va a tener escalar),
  // distinto de `valor: null` con unidad conocida, que es "no se pudo medir" (SIN_DATO).
  if (eje.unidad === null) return NO_APLICA
  if (eje.valor === null) return SIN_DATO
  if (eje.unidad === 'años') return `${fmtNumero(eje.valor, 1)} años`
  if (eje.unidad === 'percentil') return `p${fmtNumero(eje.valor, 0)}`
  return fmtPct(eje.valor, 1) // 'pp'
}

function textoCobertura(eje: EjeDeRiesgo): string {
  const { conDato, posiciones } = eje.cobertura
  if (posiciones === 0) return 'sin posiciones'
  return `${conDato} de ${posiciones} con dato (${fmtPct(posiciones > 0 ? (conDato / posiciones) * 100 : null, 0)})`
}

function CuerpoEje({ eje }: { eje: EjeDeRiesgo }) {
  switch (eje.id) {
    case 'duracion':
      return <BarraSimple valor={eje.valor} escala={10} />
    case 'liquidez':
      return (
        <>
          <BarraSimple valor={eje.valor} escala={100} />
          {eje.grupos.map((grupo) => (
            <GrupoPercentiles key={grupo.titulo} grupo={grupo} />
          ))}
        </>
      )
    case 'legislacion':
      return (
        <>
          <BarraSimple valor={eje.valor} escala={100} />
          {eje.grupos.map((grupo) => (
            <DistribucionBarras key={grupo.titulo} titulo={grupo.titulo} tramos={aTramosDistribucion(grupo.tramos)} />
          ))}
        </>
      )
    case 'concentracion':
      return (
        <div style={{ display: 'grid', gap: 6 }}>
          {eje.grupos.flatMap((grupo) => grupo.tramos).map((tramo) => (
            <TramoConTope key={tramo.nombre} tramo={tramo} />
          ))}
        </div>
      )
    case 'credito':
    case 'moneda':
      return (
        <div style={{ display: 'grid', gap: 10 }}>
          {eje.grupos.map((grupo) => (
            <DistribucionBarras key={grupo.titulo} titulo={grupo.titulo} tramos={aTramosDistribucion(grupo.tramos)} />
          ))}
        </div>
      )
    default:
      return null
  }
}

function aTramosDistribucion(tramos: TramoDeEje[]): TramoDistribucion[] {
  return tramos.map((t) => ({ nombre: t.nombre, peso: t.valor, sinDato: t.sinDato }))
}

/** Una barra 0–100% contra una escala propia del eje, recortada a 1 (nunca desborda). */
function BarraSimple({ valor, escala }: { valor: number | null; escala: number }) {
  const fraccion = valor === null ? 0 : Math.min(1, Math.max(0, valor / escala))
  return (
    <div aria-hidden style={{ height: ALTO_BARRA, background: 'var(--pan2)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ width: `${fraccion * 100}%`, height: '100%', background: valor === null ? 'var(--sd)' : 'var(--medida)' }} />
    </div>
  )
}

/** Percentiles por segmento: cada barra es 0–100 de forma independiente, nunca apilada como
 *  parte de un todo — sumar percentiles entre segmentos no significa nada (a diferencia de los
 *  pesos en pp de `DistribucionBarras`, que sí son partes de un total). */
function GrupoPercentiles({ grupo }: { grupo: GrupoDeEje }) {
  if (grupo.tramos.length === 0) return null
  return (
    <div style={{ display: 'grid', gap: 5 }}>
      <h4 style={{ margin: 0, fontSize: 10, color: 'var(--dim)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {grupo.titulo}
      </h4>
      {grupo.tramos.map((tramo) => (
        <div key={tramo.nombre} style={{ display: 'grid', gap: 2 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11 }}>
            <span style={{ color: tramo.sinDato ? 'var(--sd)' : 'var(--tx)' }}>{tramo.nombre}</span>
            <span className="mono" style={{ color: tramo.sinDato ? 'var(--sd)' : 'var(--tx)' }}>
              {tramo.sinDato ? SIN_DATO : `p${fmtNumero(tramo.valor, 0)}`}
            </span>
          </div>
          <div aria-hidden style={{ height: 6, background: 'var(--pan2)', borderRadius: 2, overflow: 'hidden' }}>
            <div
              style={{
                width: `${Math.min(100, Math.max(0, tramo.valor))}%`,
                height: '100%',
                background: tramo.sinDato ? 'var(--sd)' : 'var(--medida)',
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Mismo lenguaje visual que `FilaDeTope` de `PanelConcentracion.tsx`: línea vertical marcando el
 *  tope, para los tramos del eje concentración que lo tienen. */
function TramoConTope({ tramo }: { tramo: TramoDeEje }) {
  const tope = tramo.tope
  const escala = Math.max(tramo.valor, tope ?? 0, 1) * 1.08
  const excedido = tope !== null && tramo.valor > tope
  const color = tramo.sinDato ? 'var(--sd)' : excedido ? 'var(--neg)' : 'var(--medida)'

  return (
    <div style={{ display: 'grid', gap: 2 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11.5 }}>
        <span style={{ color: excedido ? 'var(--neg)' : tramo.sinDato ? 'var(--sd)' : 'var(--tx)' }}>{tramo.nombre}</span>
        <span className="mono" style={{ color, whiteSpace: 'nowrap' }}>
          {fmtPct(tramo.valor, 1)}
          {tope !== null && <> / {fmtPct(tope, 0)}</>}
        </span>
      </div>
      <div aria-hidden style={{ position: 'relative', height: 8, background: 'var(--pan2)', borderRadius: 2 }}>
        <div style={{ width: `${Math.min(100, (tramo.valor / escala) * 100)}%`, height: '100%', background: color, borderRadius: 2 }} />
        {tope !== null && (
          <div
            style={{
              position: 'absolute',
              top: -1,
              bottom: -1,
              left: `${(tope / escala) * 100}%`,
              width: 1,
              background: 'var(--dim)',
            }}
          />
        )}
      </div>
    </div>
  )
}
